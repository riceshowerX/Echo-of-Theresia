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
from .sentiment_analyzer import SentimentAnalyzer, AnalysisResult  # 确保导入了 AnalysisResult

@register(
    "echo_of_theresia",
    "riceshowerX",
    "3.0.0",
    "明日方舟特雷西娅角色语音插件（v3.0 情感引擎适配版）"
)
class TheresiaVoicePlugin(Star):

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self._init_default_config()

        self.plugin_root = Path(__file__).parent.resolve()

        # === 核心状态管理 (线程安全升级) ===
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
        logger.info("[Echo of Theresia] 核心逻辑已装载 (Sentiment Engine v3.1 Linked)")

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
        self.config.setdefault("params.base_cooldown", 15)      # 基础CD
        self.config.setdefault("params.mood_duration", 120)     # 情绪持续时间(秒) - 配合v3.1引擎延长

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
                # 简单的随机清理，避免排序带来的性能损耗
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

    # ==================== 核心决策算法 (v3.0 升级版) ====================

    def make_decision(self, *, base_tag: str, analysis: AnalysisResult, is_late_night: bool, session_state: dict) -> str:
        """
        基于 v3.1 情感引擎结果的决策逻辑
        """
        now = time.time()
        candidates = []
        
        # 1. 提取分析结果
        current_tag = analysis.tag
        current_score = analysis.score
        
        # 2. 情绪惯性 (Plugin层面的短期惯性)
        mood_tag = session_state.get("mood_tag")
        mood_expiry = session_state.get("mood_expiry", 0)
        has_strong_mood = (mood_tag is not None) and (now < mood_expiry)

        # 3. 候选池构建
        # A. 当前识别到的情绪
        if current_tag:
            candidates.append(current_tag)
            # 如果强度很高，加入双倍权重
            if analysis.intensity in ["severe", "extreme"]:
                candidates.append(current_tag)
        
        # B. 混合情绪 (v3.1 新特性)
        if analysis.mixed_emotions:
            for mix_tag, _ in analysis.mixed_emotions:
                candidates.append(mix_tag)

        # C. 惯性情绪 (如果没有被当前强情绪覆盖)
        if has_strong_mood:
            # 只有当当前情绪不是强烈的反向情绪时，才保留惯性
            # (简化逻辑：只要当前强度不是 extreme，就混入惯性)
            if analysis.intensity != "extreme":
                candidates.append(mood_tag)

        # D. 环境因素 (深夜模式)
        if is_late_night:
            # 深夜适合：安抚、晚安、陪伴
            if current_tag in {"comfort", "dont_cry", "company"}:
                candidates.append(current_tag) # 加重当前
            else:
                candidates.append("sanity") # 默认晚安

        # E. 默认Tag
        if base_tag:
            candidates.append(base_tag)

        # 去重
        candidates = list(set(candidates))
        if not candidates:
            return None

        # 4. 动态权重计算
        weights = []
        for tag in candidates:
            w = 1.0
            
            # 命中当前识别
            if tag == current_tag:
                w += current_score * 0.8  # 利用 v3.1 的精准分数
            
            # 命中惯性
            if tag == mood_tag and has_strong_mood:
                w += 2.5
            
            # 避免复读机
            if tag == session_state["last_tag"]:
                w *= 0.05
            
            weights.append(w)

        final_tag = random.choices(candidates, weights=weights, k=1)[0]
        
        # 5. 更新状态 (返回需要更新的字段)
        updates = {}
        
        # 只有 "moderate" 以上的情绪才值得被记住
        if current_tag and analysis.intensity in ["moderate", "severe", "extreme"]:
            updates["mood_tag"] = current_tag
            updates["mood_expiry"] = now + self.config.get("params.mood_duration", 120)
        
        # 如果是晚安，清除情绪
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
        
        # 戳一戳也尝试走一下情感分析(为了获取用户画像)，但强制 tag 为 poke
        # 这样即使是戳一戳，也能让 SentimentAnalyzer 记住用户活跃了
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

        # 过滤指令
        if text_lower.startswith(self.config.get("command.prefix", "/theresia").lower()): return

        # 关键词检测
        keywords = [str(k).lower() for k in self.config.get("command.keywords", [])]
        if not any(k in text_lower for k in keywords):
            return

        # === 获取会话状态 ===
        state = self._get_session_state(event.session_id)
        now = time.time()
        last_time = state["last_trigger"]

        # === 情感分析 (v3.1 核心调用) ===
        # 使用 get_analysis_details 获取完整对象，并传入 user_id 用于上下文记忆
        analysis_result = AnalysisResult(None, 0, 0, 0, "mild", {}, [], 0) # 默认空
        
        if self.config.get("features.emotion_detect", True):
            analysis_result = self.analyzer.get_analysis_details(
                text, 
                user_id=event.session_id # 关键：传入 ID 激活上下文记忆
            )

        # === 自适应冷却 (ACD v2) ===
        base_cd = self.config.get("params.base_cooldown", 15)
        
        # 利用 v3.1 的 intensity 属性
        if analysis_result.intensity == "extreme":
            actual_cd = 0 # 极端情绪无视冷却
        elif analysis_result.intensity == "severe":
            actual_cd = 3
        elif analysis_result.intensity == "moderate":
            actual_cd = base_cd * 0.5
        else:
            actual_cd = base_cd
            
        if now - last_time < actual_cd:
            return 

        # === 决策 ===
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

        # 更新状态
        state_updates["last_trigger"] = now
        state_updates["last_tag"] = final_tag
        self._update_session_state(event.session_id, state_updates)

        async for msg in self.send_voice_by_tag(event, final_tag):
            yield msg

    async def send_voice_by_tag(self, event: AstrMessageEvent, tag: str | None):
        rel_path = self.voice_manager.get_voice(tag or None)
        if not rel_path and tag:
            # 降级策略
            rel_path = self.voice_manager.get_voice(None)

        if rel_path:
            async for msg in self.safe_yield_voice(event, rel_path):
                yield msg

    # ==================== 指令系统 ====================

    @filter.command("theresia")
    async def main_command(self, event: AstrMessageEvent, action: str = None, payload: str = None):
        action = (action or "").lower().strip()

        if not action:
            yield event.plain_result("Echo of Theresia v3.0 (Sentiment v3.1) 已就绪~\n发送 /theresia help 查看指令。")
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
            # 调试指令：查看 v3.1 引擎对当前文本的分析结果
            if not payload:
                yield event.plain_result("请在指令后输入要分析的文本。")
                return
            res = self.analyzer.get_analysis_details(payload, user_id=event.session_id)
            info = (
                f"Tag: {res.tag}\n"
                f"Score: {res.score:.2f}\n"
                f"Intensity: {res.intensity}\n"
                f"Mixed: {res.mixed_emotions}\n"
                f"Context Influence: {res.context_influence:.2f}"
            )
            yield event.plain_result(info)

        elif action == "reset_context":
            # 清除当前用户的上下文
            if event.session_id in self.analyzer.context_memory:
                del self.analyzer.context_memory[event.session_id]
                self.analyzer._save_context_async(event.session_id) # 强制保存
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
            "【Echo of Theresia v3.0】\n"
            "/theresia help\n"
            "/theresia enable/disable\n"
            "/theresia voice [标签]\n"
            "/theresia analyze [文本] (调试情感)\n"
            "/theresia reset_context (重置记忆)\n"
            "/theresia tags\n"
            "特性：\n"
            "• v3.1 情感引擎：双重否定/反问句/上下文感知\n"
            "• 智能响应：根据情绪强度动态调整冷却\n"
        )