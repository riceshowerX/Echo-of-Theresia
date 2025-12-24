# -*- coding: utf-8 -*-
import asyncio
import datetime
import time
import random
import re
from pathlib import Path

from astrbot.api.all import *
from astrbot.api.star import Star, Context, register
from astrbot.api.event import EventHandler, AstrMessageEvent
from astrbot.api.message_components import Record
from astrbot.api import logger

from .voice_manager import VoiceManager
from .scheduler import VoiceScheduler


@register(
    "echo_of_theresia",
    "riceshowerX",
    "2.0.0",
    "明日方舟特雷西娅角色语音插件（v2.0 重构版）"
)
class TheresiaVoicePlugin(Star):

    # ==================== 情感定义 ====================

    EMOTION_DEFINITIONS = {
        "晚安": ("sanity", 10),
        "早安": ("morning", 9),
        "救命": ("comfort", 8),
        "痛苦": ("dont_cry", 8),
        "难过": ("comfort", 7),
        "害怕": ("comfort", 7),
        "累":   ("sanity", 6),
        "休息": ("sanity", 6),
        "失败": ("fail", 6),
        "孤独": ("company", 6),
        "抱抱": ("trust", 5),
        "戳":   ("poke", 4),
    }

    INTENSIFIERS = ["好", "太", "真", "非常", "超级", "死", "特别"]
    NEGATIONS = ["不", "没", "别", "勿", "无"]
    NEGATION_WINDOW = 5

    # ==================== 初始化 ====================

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}

        self._init_default_config()

        # 多会话独立状态
        self.session_state = {}  # { session_id: { last_tag, last_voice_path, last_trigger_time } }

        self.plugin_root = Path(__file__).parent.resolve()

        # 管理器
        self.voice_manager = VoiceManager(self)
        self.voice_manager.load_voices()

        self.scheduler = VoiceScheduler(self, self.voice_manager)

    async def on_load(self):
        """生命周期：插件加载完成后启动 scheduler"""
        if self.config.get("enabled", True):
            asyncio.create_task(self.scheduler.start())
        logger.info("[Echo of Theresia v2.0] 插件加载完成")

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

        # 深夜护航时间段
        self.config.setdefault("sanity.night_start", 1)
        self.config.setdefault("sanity.night_end", 5)

        # 定时任务
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
            logger.warning(f"[Echo v2.0] 文件缺失: {rel_path}")
            return

        try:
            yield event.chain_result([Record(file=str(abs_path))])
        except Exception as e:
            import traceback
            logger.error(f"[Echo v2.0] 发送失败: {e} | session={event.session_id} | path={rel_path}")
            logger.error(traceback.format_exc())

    # ==================== 情感分析 ====================

    def analyze_sentiment(self, text: str):
        text_lower = text.lower()
        best_tag = None
        max_score = 0

        for keyword, (tag, base_score) in self.EMOTION_DEFINITIONS.items():
            keyword_lower = keyword.lower()
            if keyword_lower not in text_lower:
                continue

            for match in re.finditer(re.escape(keyword_lower), text_lower):
                kw_index = match.start()
                score = base_score

                if self.config.get("features.smart_negation", True):
                    window = text_lower[max(0, kw_index - self.NEGATION_WINDOW):kw_index]
                    if any(neg in window for neg in self.NEGATIONS):
                        continue

                if any(i in text_lower for i in self.INTENSIFIERS):
                    score += 5

                if score > max_score:
                    max_score = score
                    best_tag = tag

        return best_tag, max_score

    # ==================== 智能语音选择 ====================

    def pick_voice_tag(self, *, base_tag, sentiment_tag, sentiment_score, is_late_night, session_state):
        candidates = []

        # 深夜护航
        if is_late_night:
            if sentiment_tag in {"comfort", "dont_cry", "fail", "company"}:
                candidates += [sentiment_tag, "sanity"]
            else:
                candidates.append("sanity")

        # 情感标签
        if sentiment_tag and sentiment_tag not in candidates:
            candidates.append(sentiment_tag)

        # 默认标签
        if base_tag and base_tag not in candidates:
            candidates.append(base_tag)

        if not candidates:
            return None

        # 智能去重（按会话）
        last_tag = session_state["last_tag"]
        if self.config.get("features.smart_voice_pick", True):
            if last_tag in candidates and sentiment_score < 12:
                candidates = [c for c in candidates if c != last_tag] or candidates

        # 权重选择
        if sentiment_tag and sentiment_tag in candidates and sentiment_score >= 12:
            weights = [3 if c == sentiment_tag else 1 for c in candidates]
            return random.choices(candidates, weights=weights, k=1)[0]

        return random.choice(candidates)

    # ==================== raw_event 戳一戳桥接（核心） ====================

    @EventHandler.on_raw_event()
    async def _raw_event_poke_bridge(self, raw: dict):
        """
        兼容所有 AstrBot 版本的戳一戳事件桥接器：
        - OneBot v11: notice.poke
        - KOOK: eventType = "message.btn.click"
        - Telegram: callback_query / nudge
        """

        # OneBot v11（aiocqhttp）戳一戳事件
        if raw.get("post_type") == "notice" and raw.get("notice_type") == "poke":
            session_id = str(raw.get("group_id") or raw.get("user_id"))
            logger.info(f"[Echo v2.0] raw_event 捕获到 OneBot 戳一戳 session={session_id}")

            fake_event = AstrMessageEvent(
                session_id=session_id,
                message_str="[戳一戳]",
                message_obj=None
            )

            async for msg in self.handle_poke(fake_event):
                yield msg

    # ==================== 文本触发（兼容戳一戳文本） ====================

    @EventHandler.on_message()
    async def keyword_trigger(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True):
            return

        text = (event.message_str or "").strip()
        text_lower = text.lower()

        # 文本戳一戳（KOOK / Telegram / QQ）
        if "[戳一戳]" in text or "戳了戳" in text or "poke" in text_lower:
            async for msg in self.handle_poke(event):
                yield msg
            return

        if not text:
            return

        # 指令前缀
        if text_lower.startswith(self.config.get("command.prefix", "/theresia").lower()):
            return

        # 英文裸命令
        if text_lower.split(" ", 1)[0] == "theresia":
            return

        # 是否叫名字
        keywords = [str(k).lower() for k in self.config.get("command.keywords", [])]
        if not any(k in text_lower for k in keywords):
            return

        # 会话状态
        state = self._get_session_state(event.session_id)
        now = time.time()

        # 深夜
        hour = datetime.datetime.now().hour
        night_start = int(self.config.get("sanity.night_start", 1))
        night_end = int(self.config.get("sanity.night_end", 5))
        is_late_night = night_start <= hour < night_end

        # 情感
        sentiment_tag, sentiment_score = (None, 0)
        if self.config.get("features.emotion_detect", True):
            sentiment_tag, sentiment_score = self.analyze_sentiment(text)

        # 默认标签
        base_tag = self.config.get("voice.default_tag", "")

        # 冷却
        if now - state["last_trigger_time"] < 10:
            return

        # 智能选择
        final_tag = self.pick_voice_tag(
            base_tag=base_tag,
            sentiment_tag=sentiment_tag,
            sentiment_score=sentiment_score,
            is_late_night=is_late_night,
            session_state=state
        )

        # 发送
        state["last_trigger_time"] = now
        state["last_tag"] = final_tag

        async for msg in self.send_voice_by_tag(event, final_tag):
            yield msg

    # ==================== 按标签发送语音 ====================

    async def send_voice_by_tag(self, event: AstrMessageEvent, tag: str | None):
        """根据标签选择语音并发送"""
        rel_path = self.voice_manager.get_voice(tag or None)
        if not rel_path and tag:
            rel_path = self.voice_manager.get_voice(None)

        if rel_path:
            async for msg in self.safe_yield_voice(event, rel_path):
                yield msg

    # ==================== 指令 ====================

    @EventHandler.on_command("theresia")
    async def main_command(self, event: AstrMessageEvent, action: str = None, payload: str = None):
        action = (action or "").lower().strip()

        if not action:
            yield event.plain_result("Echo of Theresia v2.0 已就绪~\n发送 /theresia help 查看完整指令。")
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
            "【Echo of Theresia v2.0】\n"
            "/theresia help\n"
            "/theresia enable/disable\n"
            "/theresia voice [标签]\n"
            "/theresia tags\n"
            "/theresia update\n"
            "/theresia set_target\n"
            "/theresia unset_target\n"
            "特性：\n"
            "1. 多会话独立状态\n"
            "2. 情感共鸣：识别累/难过等情绪\n"
            "3. 深夜护航：可配置时间段\n"
            "4. 信赖触摸：检测戳一戳事件（raw_event 全兼容）\n"
            "5. 智能语音：避免重复、动态选语音\n"
        )
