# -*- coding: utf-8 -*-
import asyncio
import datetime
import time
import random
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional

from astrbot.api.all import *
from astrbot.api.star import Star, Context, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.message_components import Record, Poke
from astrbot.api import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

from .voice_manager import VoiceManager
from .scheduler import VoiceScheduler
from .sentiment_analyzer import SentimentAnalyzer, AnalysisResult

@register(
    "echo_of_theresia",
    "riceshowerX",
    "3.0.1",
    "明日方舟特雷西娅角色语音插件（v3.0.1 修复版）"
)
class TheresiaVoicePlugin(Star):

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self._init_default_config()

        self.plugin_root = Path(__file__).parent.resolve()

        # === 核心状态管理 (线程安全) ===
        self.session_state: Dict[str, Dict[str, Any]] = {}
        self.state_lock = threading.Lock()
        self.MAX_CACHE_SIZE = 500

        # === 初始化各模块 ===
        self.voice_manager = VoiceManager(self)
        self.voice_manager.load_voices()
        self.scheduler = VoiceScheduler(self, self.voice_manager)
        # 初始化 v3.1 情感引擎
        self.analyzer = SentimentAnalyzer(data_dir=self.plugin_root / "data")

    async def on_load(self):
        if self.config.get("enabled", True):
            asyncio.create_task(self.scheduler.start())
        logger.info("[Echo of Theresia] 核心逻辑已装载 (v3.0.1 Hotfix)")

    async def on_unload(self):
        await self.scheduler.stop()

    # ==================== 配置 ====================

    def _init_default_config(self):
        self.config.setdefault("enabled", True)
        self.config.setdefault("command.keywords", ["特雷西娅", "特蕾西娅", "Theresia", "殿下", "皇女"])
        self.config.setdefault("command.prefix", "/theresia")
        self.config.setdefault("voice.default_tag", "")

        # 功能开关
        self.config.setdefault("features.sanity_mode", True)
        self.config.setdefault("features.emotion_detect", True)
        
        # 阈值设置
        self.config.setdefault("params.base_cooldown", 15)      
        self.config.setdefault("params.mood_duration", 120)     

        self.config.setdefault("sanity.night_start", 1)
        self.config.setdefault("sanity.night_end", 6)

        # 定时任务
        self.config.setdefault("schedule.enabled", False)
        self.config.setdefault("schedule.time", "08:00")

    def _save_config(self):
        try:
            if hasattr(self.config, "save_config"):
                self.config.save_config()
        except Exception:
            pass

    # ==================== 状态管理 (线程安全) ====================

    def _get_session_state(self, session_id: str) -> Dict[str, Any]:
        with self.state_lock:
            now = time.time()
            
            if session_id not in self.session_state:
                if len(self.session_state) >= self.MAX_CACHE_SIZE:
                    keys_to_remove = list(self.session_state.keys())[:50]
                    for k in keys_to_remove:
                        del self.session_state[k]
                
                self.session_state[session_id] = {
                    "last_tag": None,
                    "last_trigger": 0,
                    "mood_tag": None,    
                    "mood_expiry": 0     
                }
            
            return self.session_state[session_id]

    def _update_session_state(self, session_id: str, updates: Dict[str, Any]):
        with self.state_lock:
            if session_id in self.session_state:
                self.session_state[session_id].update(updates)

    # ==================== 安全发送语音 ====================

    async def safe_yield_voice(self, event: AstrMessageEvent, rel_path: str | None):
        if not rel_path:
            if event.message_str and event.message_str.strip().startswith("/"):
                yield event.plain_result("特雷西娅似乎没有找到这段语音呢~")
            return

        abs_path = (self.plugin_root / rel_path).resolve()
        if not abs_path.exists():
            logger.warning(f"[Echo] 文件缺失: {rel_path}")
            return

        try:
            yield event.chain_result([Record(file=str(abs_path))])
        except Exception as e:
            logger.error(f"[Echo] 发送失败: {e} | session={event.session_id}")

    # ==================== 核心决策算法 ====================

    def make_decision(self, *, base_tag: str, analysis: AnalysisResult, is_late_night: bool, session_state: dict) -> tuple[Optional[str], dict]:
        """
        基于 v3.1 情感引擎结果的决策逻辑
        """
        now = time.time()
        candidates = []
        
        current_tag = analysis.tag
        current_score = analysis.score
        
        mood_tag = session_state.get("mood_tag")
        mood_expiry = session_state.get("mood_expiry", 0)
        has_strong_mood = (mood_tag is not None) and (now < mood_expiry)

        # 候选池构建
        if current_tag:
            candidates.append(current_tag)
            if analysis.intensity in ["severe", "extreme"]:
                candidates.append(current_tag)
        
        if analysis.mixed_emotions:
            for mix_tag, _ in analysis.mixed_emotions:
                candidates.append(mix_tag)

        if has_strong_mood:
            if analysis.intensity != "extreme":
                candidates.append(mood_tag)

        if is_late_night:
            if current_tag in {"comfort", "dont_cry", "company"}:
                candidates.append(current_tag)
            else:
                candidates.append("sanity")

        if base_tag:
            candidates.append(base_tag)

        # 去重
        candidates = list(set(candidates))
        if not candidates:
            # === [修复点 1] ===
            # 这里必须返回 tuple，否则解包会报错 (TypeError)
            return None, {}

        # 动态权重计算
        weights = []
        for tag in candidates:
            w = 1.0
            if tag == current_tag:
                w += current_score * 0.8
            if tag == mood_tag and has_strong_mood:
                w += 2.5
            if tag == session_state["last_tag"]:
                w *= 0.05
            weights.append(w)

        final_tag = random.choices(candidates, weights=weights, k=1)[0]
        
        # 更新状态
        updates = {}
        if current_tag and analysis.intensity in ["moderate", "severe", "extreme"]:
            updates["mood_tag"] = current_tag
            updates["mood_expiry"] = now + self.config.get("params.mood_duration", 120)
        
        if final_tag == "sanity":
            updates["mood_expiry"] = 0
            
        return final_tag, updates

    # ==================== 戳一戳触发 ====================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def poke_trigger(self, event: AiocqhttpMessageEvent):
        raw_message = getattr(event.message_obj, "raw_message", None)
        if (not raw_message or not event.message_obj.message or 
            not isinstance(event.message_obj.message[0], Poke)):
            return

        target_id = raw_message.get("target_id", 0)
        self_id = raw_message.get("self_id", 0)
        if target_id != self_id:
            return

        fake_event = AstrMessageEvent(
            session_id=str(event.get_group_id() or event.get_sender_id()),
            message_str="[戳一戳]",
            message_obj=event.message_obj, 
            platform_meta=event.platform_meta
        )
        
        self.analyzer.analyze("[戳一戳]", user_id=fake_event.session_id)
        
        rel_path = self.voice_manager.get_voice("poke") or self.voice_manager.get_voice(None)
        async for msg in self.safe_yield_voice(fake_event, rel_path):
            yield msg

    # ==================== 文本关键词触发 ====================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def keyword_trigger(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True):
            return

        text = (event.message_str or "").strip()
        if not text: return
        text_lower = text.lower()

        # === [修复点 2] ===
        # 增强指令过滤，同时支持 / 和 ／
        prefix = self.config.get("command.prefix", "/theresia").lower()
        if text_lower.startswith(prefix) or text_lower.startswith(prefix.replace("/", "／")): 
            return

        # 关键词检测
        keywords = [str(k).lower() for k in self.config.get("command.keywords", [])]
        if not any(k in text_lower for k in keywords):
            return

        state = self._get_session_state(event.session_id)
        now = time.time()
        last_time = state["last_trigger"]

        # 情感分析
        analysis_result = AnalysisResult(None, 0, 0, 0, "mild", {}, [], 0)
        if self.config.get("features.emotion_detect", True):
            analysis_result = self.analyzer.get_analysis_details(
                text, 
                user_id=event.session_id
            )

        # 自适应冷却
        base_cd = self.config.get("params.base_cooldown", 15)
        if analysis_result.intensity == "extreme":
            actual_cd = 0
        elif analysis_result.intensity == "severe":
            actual_cd = 3
        elif analysis_result.intensity == "moderate":
            actual_cd = base_cd * 0.5
        else:
            actual_cd = base_cd
            
        if now - last_time < actual_cd:
            return 

        # 决策
        hour = datetime.datetime.now().hour
        night_start = int(self.config.get("sanity.night_start", 1))
        night_end = int(self.config.get("sanity.night_end", 5))
        is_late_night = night_start <= hour < night_end
        
        final_tag, state_updates = self.make_decision(
            base_tag=self.config.get("voice.default_tag", ""),
            analysis=analysis_result,
            is_late_night=is_late_night,
            session_state=state
        )

        # 如果没有合适的tag（且没有默认语音），则不回复，防止发送随机语音造成的困惑
        # 但如果设定了 default_tag 或者 VoiceManager 能兜底，此处 final_tag 应该不为 None
        # 如果 VoiceManager.get_voice(None) 返回随机语音，这里会执行
        
        state_updates["last_trigger"] = now
        state_updates["last_tag"] = final_tag
        self._update_session_state(event.session_id, state_updates)

        async for msg in self.send_voice_by_tag(event, final_tag):
            yield msg

    async def send_voice_by_tag(self, event: AstrMessageEvent, tag: str | None):
        rel_path = self.voice_manager.get_voice(tag or None)
        if not rel_path and tag:
            rel_path = self.voice_manager.get_voice(None)

        if rel_path:
            async for msg in self.safe_yield_voice(event, rel_path):
                yield msg

    # ==================== 指令系统 ====================

    @filter.command("theresia")
    async def main_command(self, event: AstrMessageEvent, action: str = None, payload: str = None):
        action = (action or "").lower().strip()

        if not action:
            yield event.plain_result("Echo of Theresia v3.0.1 (Fix) 已就绪~\n发送 /theresia help 查看指令。")
            return

        if action == "help":
            yield event.plain_result(self._help_text())

        elif action == "enable":
            self.config["enabled"] = True
            self._save_config()
            asyncio.create_task(self.scheduler.start())
            yield event.plain_result("特雷西娅语音插件已启用♪")

        elif action == "disable":
            self.config["enabled"] = False
            self._save_config()
            asyncio.create_task(self.scheduler.stop())
            yield event.plain_result("特雷西娅语音插件已禁用。")

        elif action == "voice":
            tag = (payload or self.config.get("voice.default_tag", "")).strip() or None
            async for msg in self.send_voice_by_tag(event, tag):
                yield msg

        elif action == "analyze":
            if not payload:
                yield event.plain_result("请在指令后输入要分析的文本。")
                return
            res = self.analyzer.get_analysis_details(payload, user_id=event.session_id)
            info = (
                f"Tag: {res.tag}\n"
                f"Score: {res.score:.2f}\n"
                f"Intensity: {res.intensity}\n"
                f"Mixed: {res.mixed_emotions}\n"
                f"Context: {res.context_influence:.2f}"
            )
            yield event.plain_result(info)

        elif action == "reset_context":
            if event.session_id in self.analyzer.context_memory:
                del self.analyzer.context_memory[event.session_id]
                self.analyzer._save_context_async(event.session_id)
            yield event.plain_result("上下文记忆已重置。")

        elif action == "tags":
            tags = self.voice_manager.get_tags()
            lines = ["【可用语音标签】"] + [
                f"• {t}: {self.voice_manager.get_voice_count(t)} 条" for t in tags
            ]
            yield event.plain_result("\n".join(lines))
        
        else:
            yield event.plain_result(f"未知指令: {action}")

    def _help_text(self):
        return (
            "【Echo of Theresia v3.0.1】\n"
            "/theresia help\n"
            "/theresia enable/disable\n"
            "/theresia voice [标签]\n"
            "/theresia analyze [文本]\n"
            "/theresia reset_context\n"
            "/theresia tags"
        )