# -*- coding: utf-8 -*-
import asyncio
import datetime
import time
import random
import re
from pathlib import Path

# AstrBot API Imports
from astrbot.api.all import *
from astrbot.api.star import Star, Context, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.message_components import Record
from astrbot.api import logger

# Local Imports
from .voice_manager import VoiceManager
from .scheduler import VoiceScheduler


@register(
    "echo_of_theresia",
    "riceshowerX",
    "1.4.0",
    "明日方舟特雷西娅角色语音插件 (Refactor + Smart Edition)"
)
class TheresiaVoicePlugin(Star):
    """
    Echo of Theresia 主插件
    - 支持情感识别、理智护航、戳一戳触发
    - 重构结构，更易维护
    - 修复潜在 bug
    - 增强语音选择逻辑
    """

    # ==================== 情感与文本分析配置 ====================

    # 情感定义：(标签, 基础权重)
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

    # 程度副词，提升情感权重
    INTENSIFIERS = ["好", "太", "真", "非常", "超级", "死", "特别"]

    # 否定词，命中则跳过该情感
    NEGATIONS = ["不", "没", "别", "勿", "无"]

    # 否定词检测窗口长度（字符）
    NEGATION_WINDOW = 5

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}

        # ==================== 基础配置 ====================
        self._init_default_config()

        # ==================== 运行时状态 ====================
        self.last_trigger_time = 0
        self.cooldown_seconds = 10

        # 用于更“智能”的语音选择（避免过于重复）
        self.last_tag: str | None = None
        self.last_voice_path: str | None = None

        self.plugin_root = Path(__file__).parent.resolve()

        # ==================== 管理器初始化 ====================
        self.voice_manager = VoiceManager(self)
        self.voice_manager.load_voices()

        self.scheduler = VoiceScheduler(self, self.voice_manager)

        if self.config.get("enabled", True):
            asyncio.create_task(self.scheduler.start())
            logger.info("[Echo of Theresia] 插件加载完成 (Refactor + Smart Edition)")

    # ==================== 配置与工具方法 ====================

    def _init_default_config(self):
        """统一配置初始化，集中管理所有默认值，便于维护。"""
        # 开关相关
        self.config.setdefault("enabled", True)

        # 文本触发相关
        self.config.setdefault("command.keywords", ["特雷西娅", "特蕾西娅", "Theresia"])
        self.config.setdefault("command.prefix", "/theresia")
        self.config.setdefault("voice.default_tag", "")

        # 智能特性开关
        self.config.setdefault("features.sanity_mode", True)       # 深夜理智护航
        self.config.setdefault("features.emotion_detect", True)    # 文本情感识别
        self.config.setdefault("features.smart_negation", True)    # 否定词识别
        self.config.setdefault("features.nudge_response", True)    # 戳一戳触发
        self.config.setdefault("features.smart_voice_pick", True)  # 智能语音选择

        # 定时任务配置
        self.config.setdefault("schedule.enabled", False)
        self.config.setdefault("schedule.time", "08:00")
        self.config.setdefault("schedule.frequency", "daily")
        self.config.setdefault("schedule.voice_tags", [])
        self.config.setdefault("schedule.target_sessions", [])

    async def on_unload(self):
        await self.scheduler.stop()

    def _rel_to_abs(self, rel_path: str | None) -> Path | None:
        if not rel_path:
            return None
        return (self.plugin_root / rel_path).resolve()

    def _save_config(self):
        """兼容 AstrBot Config 对象与普通 dict."""
        try:
            if hasattr(self.config, "save_config"):
                self.config.save_config()
        except Exception:
            # 这里吞掉异常是刻意为之，避免影响正常使用
            pass

    # ==================== 安全发送语音 ====================

    async def safe_yield_voice(self, event: AstrMessageEvent, rel_path: str | None):
        """
        安全发送语音：
        - 检查路径是否存在
        - 捕获发送异常
        - 仅在指令调用失败时提示
        """
        if not rel_path:
            # 仅在指令调用时提示
            if event.message_str and event.message_str.startswith("/"):
                yield event.plain_result("特雷西娅似乎没有找到这段语音呢~")
            return

        abs_path = self._rel_to_abs(rel_path)
        if not abs_path or not abs_path.exists():
            logger.warning(f"[Echo of Theresia] 文件缺失: {rel_path}")
            return

        logger.info(f"[Echo of Theresia] 发送语音: {abs_path.name}")
        try:
            chain = [Record(file=str(abs_path))]
            yield event.chain_result(chain)
        except Exception as e:
            # 建议打印 traceback 便于排查
            import traceback
            logger.error(f"[Echo of Theresia] 发送失败: {e}")
            logger.error(traceback.format_exc())

    # ==================== 文本情感分析引擎 ====================

    def analyze_sentiment(self, text: str) -> tuple[str | None, int]:
        """
        返回 (最佳情感标签, 情感强度分数)
        - 使用更安全的匹配方式
        - 支持否定词窗口
        """
        text_lower = text.lower()
        best_tag = None
        max_score = 0

        for keyword, (tag, base_score) in self.EMOTION_DEFINITIONS.items():
            # 使用正则匹配，避免子串误伤（如 “早安娜”）
            if keyword not in text_lower:
                continue

            for match in re.finditer(re.escape(keyword), text_lower):
                kw_index = match.start()
                current_score = base_score

                # 否定词检测
                if self.config.get("features.smart_negation", True):
                    window_start = max(0, kw_index - self.NEGATION_WINDOW)
                    prefix_window = text_lower[window_start:kw_index]
                    if any(neg in prefix_window for neg in self.NEGATIONS):
                        # 被否定的情感直接略过
                        continue

                # 程度副词加权：只要文本中包含任一强化词，就加分
                if any(intensifier in text_lower for intensifier in self.INTENSIFIERS):
                    current_score += 5

                if current_score > max_score:
                    max_score = current_score
                    best_tag = tag

        return best_tag, max_score

    # ==================== 智能语音选择逻辑 ====================

    def pick_voice_tag(
        self,
        *,
        base_tag: str | None,
        sentiment_tag: str | None,
        sentiment_score: int,
        is_late_night: bool
    ) -> str | None:
        """
        综合多因素选择最终语音标签：
        - 深夜优先理智/安慰
        - 有情感标签时优先情感
        - 根据强度调整标签
        - 避免连续重复同一标签（在 smart_voice_pick 开启时）
        """
        tag_candidates: list[str] = []

        # 1. 深夜优先策略：如果是深夜 + 有负面情绪，优先 comfort / sanity
        if is_late_night:
            if sentiment_tag in {"comfort", "dont_cry", "fail", "company"}:
                tag_candidates.append(sentiment_tag)
                tag_candidates.append("sanity")
            else:
                tag_candidates.append("sanity")

        # 2. 情感标签优先
        if sentiment_tag and sentiment_tag not in tag_candidates:
            tag_candidates.append(sentiment_tag)

        # 3. 用户配置的默认标签
        if base_tag and base_tag not in tag_candidates:
            tag_candidates.append(base_tag)

        # 4. 实在找不到，就交给 voice_manager 的默认逻辑（None）
        if not tag_candidates:
            return None

        # ============ 智能去重与随机 ============

        if not self.config.get("features.smart_voice_pick", True):
            # 关闭智能选择时，简单随机
            return random.choice(tag_candidates)

        # 避免短时间内重复同一标签（弱去重）
        # 如情感强度特别高，则允许重复
        if self.last_tag in tag_candidates and sentiment_score < 12:
            tag_candidates = [t for t in tag_candidates if t != self.last_tag] or tag_candidates

        # 简单权重：情感强度高时，优先情感标签
        if sentiment_tag and sentiment_tag in tag_candidates and sentiment_score >= 12:
            weights = [3 if t == sentiment_tag else 1 for t in tag_candidates]
            chosen = random.choices(tag_candidates, weights=weights, k=1)[0]
        else:
            chosen = random.choice(tag_candidates)

        return chosen

    async def send_voice_by_tag(self, event: AstrMessageEvent, tag: str | None):
        """根据标签选择语音并发送，同时记录上一次选择，用于后续智能选择。"""
        rel_path = self.voice_manager.get_voice(tag or None)
        if not rel_path and tag:
            # 当前标签没有语音时，尝试使用默认（None）
            rel_path = self.voice_manager.get_voice(None)

        if rel_path:
            self.last_tag = tag
            self.last_voice_path = rel_path
            async for msg in self.safe_yield_voice(event, rel_path):
                yield msg

    # ==================== 戳一戳 / Poke 处理 ====================

    def is_poke_event(self, event: AstrMessageEvent, text: str) -> bool:
        """统一判断是否为戳一戳事件，兼容多平台表现形式。"""
        if not self.config.get("features.nudge_response", True):
            return False

        # A. 通过 message_obj.type 判断（兼容性写法）
        msg_type = getattr(getattr(event, "message_obj", None), "type", None)
        if msg_type == "poke":
            return True

        # B. 通过文本特征判断
        if "[戳一戳]" in text or "戳了戳" in text:
            return True

        return False

    async def handle_poke(self, event: AstrMessageEvent):
        """处理戳一戳触发的语音回复。"""
        logger.info(f"[Echo of Theresia] 检测到信赖触摸 (Poke)")
        interaction_type = random.choice(["poke", "trust"])
        rel_path = self.voice_manager.get_voice(interaction_type)
        if rel_path:
            async for msg in self.safe_yield_voice(event, rel_path):
                yield msg

    # ==================== 文本触发主入口 ====================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def keyword_trigger(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True):
            return

        # 统一预取文本，允许为空
        text = (event.message_str or "").strip()
        text_lower = text.lower()

        # 1. 戳一戳优先处理（可能无文本）
        if self.is_poke_event(event, text):
            async for msg in self.handle_poke(event):
                yield msg
            return

        # 2. 其它非文本消息直接忽略（防止 list index out of range）
        if not text:
            return

        # 3. 指令前缀/保留关键字拦截
        cmd_prefix = self.config.get("command.prefix", "/theresia").lower()
        if text_lower.startswith(cmd_prefix):
            return

        # 使用 split 限制分割次数，更安全更高效
        first_word = text_lower.split(" ", 1)[0]
        if first_word == "theresia":
            return

        now = datetime.datetime.now()
        hour = now.hour
        is_late_night = 1 <= hour < 5

        # 4. 判断是否真正“叫了名字”
        keywords = [kw.lower() for kw in self.config["command.keywords"]]
        has_called_name = any(kw in text_lower for kw in keywords)
        if not has_called_name:
            # 未呼叫角色名，不触发角色语音逻辑
            return

        # ==================== 冷却机制（非强制绕过场景） ====================

        # 默认不绕过冷却；仅在“理智护航”时绕过
        bypass_cooldown = False

        # ==================== 触发逻辑：理智护航 / 情感共鸣 / 标准触发 ====================

        target_tag = None
        sentiment_tag = None
        sentiment_score = 0

        # 1. 理智护航（优先级最高）
        if self.config.get("features.sanity_mode", True) and is_late_night:
            logger.info(f"[Echo of Theresia] 触发理智护航: {text}")
            target_tag = "sanity"
            bypass_cooldown = True
            # 发送一条额外的文本提示（不影响语音）
            yield event.plain_result("博士，夜已经很深了……还在工作吗？")

        # 2. 情感共鸣
        if self.config.get("features.emotion_detect", True):
            sentiment_tag, sentiment_score = self.analyze_sentiment(text)
            if sentiment_tag:
                logger.info(f"[Echo of Theresia] 情感共鸣捕获: {sentiment_tag} (score={sentiment_score})")

        # 3. 整体触发判断
        # 如果没有理智护航也没有情感标签，就走默认标签
        if not target_tag and not sentiment_tag:
            logger.info(f"[Echo of Theresia] 标准关键词触发")
            target_tag = self.config.get("voice.default_tag", "")

        # 4. 冷却判断（理智护航可绕过）
        current_time = time.time()
        if not bypass_cooldown and (current_time - self.last_trigger_time < self.cooldown_seconds):
            return

        # 5. 通过智能策略最终决定使用哪个标签
        final_tag = self.pick_voice_tag(
            base_tag=target_tag,
            sentiment_tag=sentiment_tag,
            sentiment_score=sentiment_score,
            is_late_night=is_late_night
        )

        # 6. 语音发送
        if final_tag is not None or target_tag is None:
            self.last_trigger_time = current_time
            async for msg in self.send_voice_by_tag(event, final_tag):
                yield msg

    # ==================== 指令入口 ====================

    @filter.command("theresia")
    async def main_command_handler(self, event: AstrMessageEvent, action: str = None, payload: str = None):
        action = (action or "").lower().strip()

        if not action:
            yield event.plain_result(self._get_help_text(brief=True))
            return

        if action == "help":
            yield event.plain_result(self._get_help_text(brief=False))

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
            # 指令调用，直接按标签播放，不走智能选择逻辑
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

    def _get_help_text(self, brief: bool = True) -> str:
        if brief:
            return "Echo of Theresia (v1.4.0) 已就绪~\n发送 /theresia help 查看完整指令。"
        return (
            "【Echo of Theresia】\n"
            "/theresia help\n"
            "/theresia enable/disable\n"
            "/theresia voice [标签]\n"
            "/theresia tags\n"
            "/theresia update\n"
            "/theresia set_target\n"
            "/theresia unset_target\n"
            "特性：\n"
            "1. 情感共鸣：识别累/难过等情绪\n"
            "2. 理智护航：深夜劝睡\n"
            "3. 信赖触摸：检测戳一戳事件\n"
            "4. 智能语音：根据时间/情绪避免重复、动态选语音"
        )
