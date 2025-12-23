# -*- coding: utf-8 -*-
import asyncio
import datetime
import random
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
    "1.0.5",
    "明日方舟特雷西娅角色语音插件"
)
class TheresiaVoicePlugin(Star):
    
    # 情感关键词映射 (用户输入词 -> 需要寻找的语音标签)
    # 这些标签对应 VoiceManager.PRESET_MAPPING 里的内容
    EMOTION_MAP = {
        "累": "sanity",       # 映射到 "闲置.mp3"
        "休息": "sanity",
        "难过": "comfort",    # 映射到 "选中干员2.mp3" (别怕，我在)
        "害怕": "comfort",
        "别怕": "comfort",
        "孤独": "company",    # 映射到 "部署2.mp3" (我在这儿呢)
        "没人": "company",
        "痛苦": "dont_cry",   # 映射到 "作战中4.mp3" (别哭)
        "想哭": "dont_cry",
        "失败": "fail",       # 映射到 "行动失败.mp3"
        "不行": "fail",
        "早安": "morning",    # 映射到 "问候.mp3"
        "晚安": "sanity",
        "戳": "poke",         # 映射到 "戳一下.mp3"
        "抱抱": "trust"       # 映射到 "信赖触摸.mp3"
    }

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}

        # 配置初始化
        self.config.setdefault("enabled", True)
        self.config.setdefault("command.keywords", ["特雷西娅", "特蕾西娅", "Theresia"])
        self.config.setdefault("command.prefix", "/theresia")
        self.config.setdefault("voice.default_tag", "")
        
        # 功能开关
        self.config.setdefault("features.sanity_mode", True)
        self.config.setdefault("features.emotion_detect", True)

        # 定时任务配置
        self.config.setdefault("schedule.enabled", False)
        self.config.setdefault("schedule.time", "08:00")
        self.config.setdefault("schedule.frequency", "daily")
        self.config.setdefault("schedule.voice_tags", [])
        self.config.setdefault("schedule.target_sessions", [])

        self.plugin_root = Path(__file__).parent.resolve()
        
        self.voice_manager = VoiceManager(self)
        self.voice_manager.load_voices() 
        
        self.scheduler = VoiceScheduler(self, self.voice_manager)

        if self.config.get("enabled", True):
            asyncio.create_task(self.scheduler.start())
            logger.info("[Echo of Theresia] 插件加载完成，定时服务已启动")

    async def on_unload(self):
        await self.scheduler.stop()
        logger.info("[Echo of Theresia] 插件已卸载")

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
            yield event.plain_result("特雷西娅似乎没有找到这段语音呢~")
            return

        abs_path = self._rel_to_abs(rel_path)
        if not abs_path or not abs_path.exists():
            logger.warning(f"[Echo of Theresia] 文件缺失: {rel_path}")
            yield event.plain_result("语音文件走丢了哦~")
            return

        logger.info(f"[Echo of Theresia] 发送语音: {abs_path.name}")

        try:
            chain = [Record(file=str(abs_path))]
            yield event.chain_result(chain)
        except Exception as e:
            logger.error(f"[Echo of Theresia] 发送失败: {e}")
            yield event.plain_result(f"发送出错: {e}")

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
            if not tags:
                yield event.plain_result("暂无标签数据")
                return
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

    # ==================== 智能触发系统 (核心升级) ====================
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def keyword_trigger(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True): return

        text = (event.message_str or "").strip()
        if not text: return

        # 0. 指令过滤
        cmd_prefix = self.config.get("command.prefix", "/theresia").lower()
        if text.lower().startswith(cmd_prefix): return
        
        # 0.1 如果第一个词是 theresia，也不触发（留给指令处理器）
        first_word = text.split()[0].lower()
        if first_word == "theresia": return

        now = datetime.datetime.now()
        hour = now.hour
        text_lower = text.lower()
        
        target_tag = None
        should_trigger = False

        # 1. 检测是否包含关键词
        keywords = [kw.lower() for kw in self.config["command.keywords"]]
        has_keyword = any(kw in text_lower for kw in keywords)

        # ---------------------------------------------------------
        # 【功能 1】理智护航 (Sanity Protocol) - 深夜劝睡
        # ---------------------------------------------------------
        is_late_night = 1 <= hour < 5
        # 如果开启了深夜模式，且是在深夜，且提到了关键词
        if self.config.get("features.sanity_mode", True) and is_late_night and has_keyword:
            logger.info(f"[Echo of Theresia] 触发理智护航: {text}")
            target_tag = "sanity"  # 对应 "闲置.mp3"
            yield event.plain_result("博士，夜已经很深了……还在工作吗？")
            should_trigger = True

        # ---------------------------------------------------------
        # 【功能 2】源石技艺共鸣 (Resonance) - 情感检测
        # ---------------------------------------------------------
        elif self.config.get("features.emotion_detect", True):
            # 遍历情感字典，看看那句话里有没有关键词
            for emotion_word, tag in self.EMOTION_MAP.items():
                if emotion_word in text_lower:
                    logger.info(f"[Echo of Theresia] 触发情感共鸣 [{emotion_word} -> {tag}]")
                    target_tag = tag
                    should_trigger = True
                    break

        # ---------------------------------------------------------
        # 【功能 3】标准触发 (随机)
        # ---------------------------------------------------------
        if not should_trigger and has_keyword:
            logger.info(f"[Echo of Theresia] 标准关键词触发")
            target_tag = self.config["voice.default_tag"]
            should_trigger = True

        # 执行发送
        if should_trigger:
            rel_path = self.voice_manager.get_voice(target_tag or None)
            # 如果指定标签没找到 (比如没有对应情感的语音)，回退到随机
            if not rel_path and target_tag:
                 rel_path = self.voice_manager.get_voice(None)
            
            async for msg in self.safe_yield_voice(event, rel_path):
                yield msg

    def _get_help_text(self, brief: bool = True) -> str:
        if brief:
            return "Echo of Theresia 已就绪~\n发送 /theresia help 查看完整指令。"
        return (
            "【Echo of Theresia】\n"
            "/theresia enable/disable\n"
            "/theresia voice [标签]\n"
            "/theresia tags\n"
            "/theresia update\n"
            "/theresia set_target\n"
            "直接发送「特雷西娅」触发，支持情感关键词检测(累/难过/晚安等)。"
        )