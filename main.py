# -*- coding: utf-8 -*-
import asyncio
import datetime
import time
import random
from pathlib import Path
from typing import Dict, Any

from astrbot.api.all import *
from astrbot.api.star import Star, Context, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.message_components import Record, Poke
from astrbot.api import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

from .voice_manager import VoiceManager
from .scheduler import VoiceScheduler
from .sentiment_analyzer import SentimentAnalyzer

@register(
    "echo_of_theresia",
    "riceshowerX",
    "2.2.0",
    "明日方舟特雷西娅角色语音插件（v2.2 自适应决策版）"
)
class TheresiaVoicePlugin(Star):

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self._init_default_config()

        self.plugin_root = Path(__file__).parent.resolve()

        # === 核心状态管理 ===
        # 结构: { session_id: { last_tag, last_trigger, mood_tag, mood_expiry } }
        self.session_state: Dict[str, Dict[str, Any]] = {}
        self.MAX_CACHE_SIZE = 500  # 最大缓存会话数 (防止内存泄漏)

        # === 初始化各模块 ===
        self.voice_manager = VoiceManager(self)
        self.voice_manager.load_voices()
        self.scheduler = VoiceScheduler(self, self.voice_manager)
        self.analyzer = SentimentAnalyzer() # 情感分析引擎

    async def on_load(self):
        if self.config.get("enabled", True):
            asyncio.create_task(self.scheduler.start())
        logger.info("[Echo of Theresia] 核心逻辑已装载 (Adaptive Decision System Online)")

    async def on_unload(self):
        await self.scheduler.stop()

    # ==================== 配置 ====================

    def _init_default_config(self):
        self.config.setdefault("enabled", True)
        self.config.setdefault("command.keywords", ["特雷西娅", "特蕾西娅", "Theresia"])
        self.config.setdefault("command.prefix", "/theresia")
        self.config.setdefault("voice.default_tag", "")

        # 功能开关
        self.config.setdefault("features.sanity_mode", True)
        self.config.setdefault("features.emotion_detect", True)
        self.config.setdefault("features.smart_negation", True) # 否定词检测
        self.config.setdefault("features.mood_inertia", True)   # 情感惯性开关 (新)
        
        # 阈值设置
        self.config.setdefault("params.base_cooldown", 15)      # 基础CD
        self.config.setdefault("params.high_emotion_cd", 5)     # 高情绪CD (响应更快)
        self.config.setdefault("params.mood_duration", 60)      # 情绪持续时间(秒)

        self.config.setdefault("sanity.night_start", 1)
        self.config.setdefault("sanity.night_end", 5)

        # 定时任务配置
        self.config.setdefault("schedule.enabled", False)
        self.config.setdefault("schedule.time", "08:00")
        self.config.setdefault("schedule.frequency", "daily")
        self.config.setdefault("schedule.voice_tags", [])
        self.config.setdefault("schedule.target_sessions", [])
        self.config.setdefault("schedule.weekday", 1)

    def _save_config(self):
        try:
            if hasattr(self.config, "save_config"):
                self.config.save_config()
        except Exception:
            pass

    # ==================== 状态管理 (LRU 机制) ====================

    def _get_session_state(self, session_id):
        now = time.time()
        
        # 如果不存在，创建新状态
        if session_id not in self.session_state:
            # 内存清理：如果超过最大缓存，清理最老的 20%
            if len(self.session_state) >= self.MAX_CACHE_SIZE:
                # 按 last_trigger 排序，取旧的删除
                sorted_keys = sorted(self.session_state.keys(), key=lambda k: self.session_state[k]['last_trigger'])
                for k in sorted_keys[:int(self.MAX_CACHE_SIZE * 0.2)]:
                    del self.session_state[k]
            
            self.session_state[session_id] = {
                "last_tag": None,
                "last_trigger": 0,
                "mood_tag": None,    # 当前持续的情绪状态
                "mood_expiry": 0     # 情绪过期时间戳
            }
        
        return self.session_state[session_id]

    # ==================== 安全发送语音 ====================

    async def safe_yield_voice(self, event: AstrMessageEvent, rel_path: str | None):
        if not rel_path:
            # 仅在指令模式下提示找不到
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

    def make_decision(self, *, base_tag, sentiment_tag, sentiment_score, is_late_night, session_state):
        """
        自适应决策逻辑：结合当前情绪、历史情绪惯性、环境时间来选择最佳 Tag
        """
        now = time.time()
        candidates = []
        
        # 1. 情绪惯性检查 (Emotional Inertia)
        # 如果之前处于强烈情绪(如哭泣、害怕)且未过期，且当前输入没有强烈的反向情绪，保持惯性
        mood_tag = session_state.get("mood_tag")
        mood_expiry = session_state.get("mood_expiry", 0)
        
        has_strong_mood = (mood_tag is not None) and (now < mood_expiry)
        
        # 2. 候选池构建
        if has_strong_mood and sentiment_score < 5:
            # 如果处于情绪余韵中，且当前只是普通说话，混入惯性Tag
            candidates.append(mood_tag)
            # logger.debug(f"触发情绪惯性: {mood_tag}")

        if is_late_night:
            if sentiment_tag in {"comfort", "dont_cry", "fail", "company"}:
                candidates += [sentiment_tag, "sanity"]
            else:
                candidates.append("sanity")

        if sentiment_tag:
            candidates.append(sentiment_tag)
        
        if base_tag:
            candidates.append(base_tag)

        # 去重
        candidates = list(set(candidates))
        if not candidates:
            return None

        # 3. 权重加权选择
        weights = []
        for tag in candidates:
            w = 1.0
            # 命中当前识别出的情绪，权重极高
            if tag == sentiment_tag:
                w += sentiment_score * 0.5  # 分数越高权重越大
            
            # 命中惯性情绪，权重加成
            if tag == mood_tag and has_strong_mood:
                w += 3.0
            
            # 避免重复：如果是上一条发过的，大幅降权
            if tag == session_state["last_tag"]:
                w *= 0.1
            
            weights.append(w)

        final_tag = random.choices(candidates, weights=weights, k=1)[0]
        
        # 4. 更新情绪惯性状态
        # 只有当情绪分很高(例如 > 8)时，才更新惯性状态
        if sentiment_tag and sentiment_score >= 8:
            session_state["mood_tag"] = sentiment_tag
            duration = self.config.get("params.mood_duration", 60)
            session_state["mood_expiry"] = now + duration
        
        # 如果选出了sanity(理智/晚安)，通常意味着结束对话，清除负面情绪惯性
        if final_tag == "sanity":
             session_state["mood_expiry"] = 0

        return final_tag

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

        # 构造兼容事件
        fake_event = AstrMessageEvent(
            session_id=str(event.get_group_id() or event.get_sender_id()),
            message_str="[戳一戳]",
            message_obj=event.message_obj, 
            platform_meta=event.platform_meta
        )

        # 戳一戳通常不走复杂决策，直接回应
        tag = "poke"
        rel_path = self.voice_manager.get_voice(tag) or self.voice_manager.get_voice(None)
        
        async for msg in self.safe_yield_voice(fake_event, rel_path):
            yield msg

    # ==================== 文本关键词触发 ====================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def keyword_trigger(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True):
            return

        text = (event.message_str or "").strip()
        text_lower = text.lower()
        if not text: return

        # 指令过滤
        if text_lower.startswith(self.config.get("command.prefix", "/theresia").lower()): return
        if text_lower.split(" ", 1)[0] == "theresia": return

        # 关键词检测
        keywords = [str(k).lower() for k in self.config.get("command.keywords", [])]
        if not any(k in text_lower for k in keywords):
            return

        # === 自适应冷却检测 (ACD) ===
        state = self._get_session_state(event.session_id)
        now = time.time()
        last_time = state["last_trigger"]
        
        # 预先分析情绪，用于判断 CD
        sentiment_tag, sentiment_score = (None, 0)
        if self.config.get("features.emotion_detect", True):
            sentiment_tag, sentiment_score = self.analyzer.analyze(
                text, 
                enable_negation=self.config.get("features.smart_negation", True)
            )

        # 动态 CD 计算
        base_cd = self.config.get("params.base_cooldown", 15)
        # 算法：情绪越激动(分数高)，CD越短，最低5秒
        if sentiment_score >= 8:
            actual_cd = self.config.get("params.high_emotion_cd", 5)
        else:
            actual_cd = base_cd
            
        if now - last_time < actual_cd:
            return # 冷却中

        # === 执行决策 ===
        # 环境判断
        hour = datetime.datetime.now().hour
        night_start = int(self.config.get("sanity.night_start", 1))
        night_end = int(self.config.get("sanity.night_end", 5))
        is_late_night = night_start <= hour < night_end
        
        base_tag = self.config.get("voice.default_tag", "")

        final_tag = self.make_decision(
            base_tag=base_tag,
            sentiment_tag=sentiment_tag,
            sentiment_score=sentiment_score,
            is_late_night=is_late_night,
            session_state=state
        )

        # 更新状态
        state["last_trigger"] = now
        state["last_tag"] = final_tag

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
            yield event.plain_result("Echo of Theresia v2.2 (Adaptive) 已就绪~\n发送 /theresia help 查看指令。")
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

        elif action == "tags":
            tags = self.voice_manager.get_tags()
            lines = ["【可用语音标签】"] + [
                f"• {t}: {self.voice_manager.get_voice_count(t)} 条" for t in tags
            ]
            yield event.plain_result("\n".join(lines))

        elif action == "update":
            self.voice_manager.update_voices()
            total = self.voice_manager.get_voice_count()
            yield event.plain_result(f"更新完成！共 {total} 条语音。")
        
        elif action == "status":
            # 调试用：查看当前会话状态
            state = self._get_session_state(event.session_id)
            mood = state.get('mood_tag') if time.time() < state.get('mood_expiry', 0) else "None"
            yield event.plain_result(f"当前会话状态:\nMood: {mood}\nSessions Cached: {len(self.session_state)}")

        elif action == "set_target":
            await self.scheduler.add_target(event.session_id)
            yield event.plain_result("已将本会话设为定时问候目标~")

        elif action == "unset_target":
            await self.scheduler.remove_target(event.session_id)
            yield event.plain_result("已取消本会话的定时问候。")

        else:
            yield event.plain_result(f"未知指令: {action}")

    def _help_text(self):
        return (
            "【Echo of Theresia v2.2】\n"
            "/theresia help\n"
            "/theresia enable/disable\n"
            "/theresia voice [标签]\n"
            "/theresia tags\n"
            "/theresia update\n"
            "/theresia status (查看状态)\n"
            "/theresia set_target\n"
            "特性：\n"
            "• 自适应冷却 (ACD)：急事回得快\n"
            "• 情感惯性 (EI)：记住你的情绪\n"
            "• 动态权重决策\n"
        )