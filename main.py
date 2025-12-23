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
    "1.3.4",
    "明日方舟特雷西娅角色语音插件 (Chain Check Fix)"
)
class TheresiaVoicePlugin(Star):
    
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

    INTENSIFIERS = ["好", "太", "真", "非常", "超级", "死", "特别"]
    NEGATIONS = ["不", "没", "别", "勿", "无"]

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}

        # 基础配置
        self.config.setdefault("enabled", True)
        self.config.setdefault("command.keywords", ["特雷西娅", "特蕾西娅", "Theresia"])
        self.config.setdefault("command.prefix", "/theresia")
        self.config.setdefault("voice.default_tag", "")
        
        # 智能特性开关
        self.config.setdefault("features.sanity_mode", True)
        self.config.setdefault("features.emotion_detect", True)
        self.config.setdefault("features.smart_negation", True)
        self.config.setdefault("features.nudge_response", True)

        # 定时任务配置
        self.config.setdefault("schedule.enabled", False)
        self.config.setdefault("schedule.time", "08:00")
        self.config.setdefault("schedule.frequency", "daily")
        self.config.setdefault("schedule.voice_tags", [])
        self.config.setdefault("schedule.target_sessions", [])

        # 运行时状态
        self.last_trigger_time = 0
        self.cooldown_seconds = 10 

        self.plugin_root = Path(__file__).parent.resolve()
        
        self.voice_manager = VoiceManager(self)
        self.voice_manager.load_voices() 
        
        self.scheduler = VoiceScheduler(self, self.voice_manager)

        if self.config.get("enabled", True):
            asyncio.create_task(self.scheduler.start())
            logger.info("[Echo of Theresia] 插件加载完成 (Chain Check Fix)")

    async def on_unload(self):
        await self.scheduler.stop()

    def _rel_to_abs(self, rel_path: str | None) -> Path | None:
        if not rel_path: return None
        return (self.plugin_root / rel_path).resolve()

    def _save_config(self):
        try:
            if hasattr(self.config, "save_config"):
                self.config.save_config()
        except Exception:
            pass

    async def safe_yield_voice(self, event: AstrMessageEvent, rel_path: str | None):
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
            logger.error(f"[Echo of Theresia] 发送失败: {e}")

    # ==================== 智能情感分析引擎 ====================
    def analyze_sentiment(self, text: str) -> str | None:
        text_lower = text.lower()
        best_tag = None
        max_score = 0

        for keyword, (tag, base_score) in self.EMOTION_DEFINITIONS.items():
            if keyword not in text_lower:
                continue

            current_score = base_score
            kw_index = text_lower.find(keyword)

            if self.config.get("features.smart_negation", True):
                is_negated = False
                window_start = max(0, kw_index - 3)
                prefix_window = text_lower[window_start:kw_index]
                for neg in self.NEGATIONS:
                    if neg in prefix_window:
                        is_negated = True
                        break
                if is_negated: continue 

            for intensifier in self.INTENSIFIERS:
                if intensifier in text_lower:
                    current_score += 5
                    break

            if current_score > max_score:
                max_score = current_score
                best_tag = tag

        return best_tag

    # ==================== 统一消息触发入口 ====================
    
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def keyword_trigger(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True): return

        # 1. [核心修改] 遍历消息链检测 Poke
        # 这是最稳健的方法，不依赖 message_str
        is_poke = False
        
        # 检查配置是否开启
        if self.config.get("features.nudge_response", True):
            # 遍历消息组件
            if hasattr(event, 'message_chain') and event.message_chain:
                for component in event.message_chain:
                    # 打印组件信息方便调试
                    # comp_type = getattr(component, 'type', 'unknown')
                    # comp_cls = component.__class__.__name__
                    
                    # 检测逻辑：
                    # 1. 类名包含 Poke
                    # 2. type 属性是 poke
                    # 3. 字符串表示包含 [Poke:
                    if "Poke" in component.__class__.__name__ or \
                       getattr(component, 'type', '').lower() == 'poke' or \
                       "[Poke:" in str(component):
                        is_poke = True
                        break
            
            # 备用：检查 message_str (防止某些适配器转译为纯文本)
            if not is_poke:
                raw_text = event.message_str or ""
                if "[戳一戳]" in raw_text or "戳了戳" in raw_text:
                    is_poke = True

        if is_poke:
            logger.info(f"[Echo of Theresia] 检测到信赖触摸 (Source: Chain Detection)")
            interaction_type = random.choice(["poke", "trust"])
            rel_path = self.voice_manager.get_voice(interaction_type)
            if rel_path:
                async for msg in self.safe_yield_voice(event, rel_path):
                    yield msg
            return # 戳一戳处理完毕，退出

        # =========================================================
        # 2. 常规文本处理
        # =========================================================
        text = (event.message_str or "").strip()
        if not text: return # 空文本拦截

        # 指令过滤
        cmd_prefix = self.config.get("command.prefix", "/theresia").lower()
        if text.lower().startswith(cmd_prefix): return
        
        first_word = text.split()[0].lower()
        if first_word == "theresia": return

        now = datetime.datetime.now()
        hour = now.hour
        text_lower = text.lower()
        
        target_tag = None
        should_trigger = False
        bypass_cooldown = False 

        keywords = [kw.lower() for kw in self.config["command.keywords"]]
        has_called_name = any(kw in text_lower for kw in keywords)

        # 理智护航
        is_late_night = 1 <= hour < 5
        if self.config.get("features.sanity_mode", True) and is_late_night and has_called_name:
            logger.info(f"[Echo of Theresia] 触发理智护航: {text}")
            target_tag = "sanity"
            yield event.plain_result("博士，夜已经很深了……还在工作吗？")
            should_trigger = True
            bypass_cooldown = True

        # 情感共鸣
        elif self.config.get("features.emotion_detect", True):
            detected_tag = self.analyze_sentiment(text)
            if detected_tag and has_called_name: 
                target_tag = detected_tag
                should_trigger = True
                logger.info(f"[Echo of Theresia] 情感共鸣捕获: {target_tag}")

        # 标准触发
        if not should_trigger and has_called_name:
            logger.info(f"[Echo of Theresia] 标准关键词触发")
            target_tag = self.config["voice.default_tag"]
            should_trigger = True

        if should_trigger:
            current_time = time.time()
            if not bypass_cooldown and (current_time - self.last_trigger_time < self.cooldown_seconds):
                return

            rel_path = self.voice_manager.get_voice(target_tag or None)
            if not rel_path and target_tag:
                 rel_path = self.voice_manager.get_voice(None)
            
            if rel_path:
                self.last_trigger_time = current_time 
                async for msg in self.safe_yield_voice(event, rel_path):
                    yield msg

    # ==================== 指令入口 ====================
    @filter.command("theresia")
    async def main_command_handler(self, event: AstrMessageEvent, action: str = None, payload: str = None):
        if not action:
            yield event.plain_result(self._get_help_text(brief=True))
            return
        action = action.lower()

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
            tag = payload or self.config["voice.default_tag"]
            rel_path = self.voice_manager.get_voice(tag)
            async for msg in self.safe_yield_voice(event, rel_path):
                yield msg
        elif action == "tags":
            tags = self.voice_manager.get_tags()
            lines = ["【可用语音标签】"] + [f"• {t}: {self.voice_manager.get_voice_count(t)} 条" for t in tags]
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
            return "Echo of Theresia (v1.3.4) 已就绪~\n发送 /theresia help 查看完整指令。"
        return (
            "【Echo of Theresia】\n"
            "/theresia enable/disable\n"
            "/theresia voice [标签]\n"
            "/theresia tags\n"
            "/theresia update\n"
            "/theresia set_target\n"
            "特性：\n"
            "1. 情感共鸣：识别累/难过等情绪\n"
            "2. 理智护航：深夜劝睡\n"
            "3. 信赖触摸：检测戳一戳事件"
        )