# -*- coding: utf-8 -*-
import asyncio
import datetime
import time
import random
from pathlib import Path

from astrbot.api.all import *
from astrbot.api.star import Star, Context, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.message_components import Record, Poke
from astrbot.api import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

from .voice_manager import VoiceManager
from .scheduler import VoiceScheduler
from .sentiment_analyzer import SentimentAnalyzer  # <--- 导入新模块

@register(
    "echo_of_theresia",
    "riceshowerX",
    "2.1.0",
    "明日方舟特雷西娅角色语音插件（v2.1 分离重构版）"
)
class TheresiaVoicePlugin(Star):

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}

        self._init_default_config()

        # 多会话独立状态
        self.session_state = {}

        self.plugin_root = Path(__file__).parent.resolve()

        # === 初始化各模块 ===
        self.voice_manager = VoiceManager(self)
        self.voice_manager.load_voices()

        self.scheduler = VoiceScheduler(self, self.voice_manager)
        
        # 初始化情感分析器
        self.analyzer = SentimentAnalyzer()

    async def on_load(self):
        if self.config.get("enabled", True):
            asyncio.create_task(self.scheduler.start())
        logger.info("[Echo of Theresia] 插件加载完成")

    async def on_unload(self):
        await self.scheduler.stop()

    # ==================== 配置 ====================

    def _init_default_config(self):
        self.config.setdefault("enabled", True)
        self.config.setdefault("command.keywords", ["特雷西娅", "特蕾西娅", "Theresia"])
        self.config.setdefault("command.prefix", "/theresia")
        self.config.setdefault("voice.default_tag", "")

        self.config.setdefault("features.sanity_mode", True)
        self.config.setdefault("features.emotion_detect", True)
        self.config.setdefault("features.smart_negation", True)
        self.config.setdefault("features.nudge_response", True)
        self.config.setdefault("features.smart_voice_pick", True)

        self.config.setdefault("sanity.night_start", 1)
        self.config.setdefault("sanity.night_end", 5)

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

    # ==================== 会话状态 ====================

    def _get_session_state(self, session_id):
        if session_id not in self.session_state:
            self.session_state[session_id] = {
                "last_tag": None,
                "last_voice_path": None,
                "last_trigger_time": 0,
            }
        return self.session_state[session_id]

    # ==================== 安全发送语音 ====================

    async def safe_yield_voice(self, event: AstrMessageEvent, rel_path: str | None):
        if not rel_path:
            if event.message_str and event.message_str.startswith("/"):
                yield event.plain_result("特雷西娅似乎没有找到这段语音呢~")
            return

        abs_path = (self.plugin_root / rel_path).resolve()
        if not abs_path.exists():
            logger.warning(f"[Echo] 文件缺失: {rel_path}")
            return

        try:
            yield event.chain_result([Record(file=str(abs_path))])
        except Exception as e:
            import traceback
            logger.error(f"[Echo] 发送失败: {e} | session={event.session_id} | path={rel_path}")

    # ==================== 智能语音选择 ====================

    def pick_voice_tag(self, *, base_tag, sentiment_tag, sentiment_score, is_late_night, session_state):
        candidates = []

        if is_late_night:
            # 深夜模式下，优先理智、安慰
            if sentiment_tag in {"comfort", "dont_cry", "fail", "company"}:
                candidates += [sentiment_tag, "sanity"]
            else:
                candidates.append("sanity")

        if sentiment_tag and sentiment_tag not in candidates:
            candidates.append(sentiment_tag)

        if base_tag and base_tag not in candidates:
            candidates.append(base_tag)

        if not candidates:
            return None

        last_tag = session_state["last_tag"]
        # 智能防重复：如果上次播过这个类型，且情绪分不是特别高，尝试换一个
        if self.config.get("features.smart_voice_pick", True):
            if last_tag in candidates and sentiment_score < 12:
                filtered = [c for c in candidates if c != last_tag]
                if filtered:
                    candidates = filtered

        # 如果情绪分很高，大幅增加该情绪的权重
        if sentiment_tag and sentiment_tag in candidates and sentiment_score >= 12:
            weights = [3 if c == sentiment_tag else 1 for c in candidates]
            return random.choices(candidates, weights=weights, k=1)[0]

        return random.choice(candidates)

    # ==================== 戳一戳检测 ====================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def poke_trigger(self, event: AiocqhttpMessageEvent):
        raw_message = getattr(event.message_obj, "raw_message", None)

        if (
            not raw_message
            or not event.message_obj.message
            or not isinstance(event.message_obj.message[0], Poke)
        ):
            return

        target_id = raw_message.get("target_id", 0)
        self_id = raw_message.get("self_id", 0)
        if target_id != self_id:
            return

        # 修复后的事件构造
        fake_event = AstrMessageEvent(
            session_id=str(event.get_group_id() or event.get_sender_id()),
            message_str="[戳一戳]",
            message_obj=event.message_obj, 
            platform_meta=event.platform_meta
        )

        async for msg in self.handle_poke(fake_event):
            yield msg

    async def handle_poke(self, event: AstrMessageEvent):
        tag = "poke"
        rel_path = self.voice_manager.get_voice(tag)
        if not rel_path:
            rel_path = self.voice_manager.get_voice(None)
        async for msg in self.safe_yield_voice(event, rel_path):
            yield msg

    # ==================== 文本触发 ====================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def keyword_trigger(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True):
            return

        text = (event.message_str or "").strip()
        text_lower = text.lower()
        if not text:
            return

        # 排除指令
        if text_lower.startswith(self.config.get("command.prefix", "/theresia").lower()):
            return
        if text_lower.split(" ", 1)[0] == "theresia":
            return

        # 关键词检测
        keywords = [str(k).lower() for k in self.config.get("command.keywords", [])]
        if not any(k in text_lower for k in keywords):
            return

        state = self._get_session_state(event.session_id)
        now = time.time()

        # CD 检查
        if now - state["last_trigger_time"] < 10:
            return

        # 环境判断
        hour = datetime.datetime.now().hour
        night_start = int(self.config.get("sanity.night_start", 1))
        night_end = int(self.config.get("sanity.night_end", 5))
        is_late_night = night_start <= hour < night_end

        # === 调用新的情感分析模块 ===
        sentiment_tag, sentiment_score = (None, 0)
        if self.config.get("features.emotion_detect", True):
            enable_neg = self.config.get("features.smart_negation", True)
            # 使用 self.analyzer
            sentiment_tag, sentiment_score = self.analyzer.analyze(text, enable_negation=enable_neg)
        
        # 默认标签
        base_tag = self.config.get("voice.default_tag", "")

        # 决策
        final_tag = self.pick_voice_tag(
            base_tag=base_tag,
            sentiment_tag=sentiment_tag,
            sentiment_score=sentiment_score,
            is_late_night=is_late_night,
            session_state=state
        )

        # 更新状态
        state["last_trigger_time"] = now
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

    # ==================== 指令 ====================

    @filter.command("theresia")
    async def main_command(self, event: AstrMessageEvent, action: str = None, payload: str = None):
        action = (action or "").lower().strip()

        if not action:
            yield event.plain_result("Echo of Theresia v2.1 (Refactored) 已就绪~\n发送 /theresia help 查看完整指令。")
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
            "【Echo of Theresia v2.1】\n"
            "/theresia help\n"
            "/theresia enable/disable\n"
            "/theresia voice [标签]\n"
            "/theresia tags\n"
            "/theresia update\n"
            "/theresia set_target\n"
            "/theresia unset_target"
        )