# -*- coding: utf-8 -*-
import asyncio
from pathlib import Path

# ================= 最终修复区 =================
# 1. 显式导入 Star (修复 StarryPlugin 报错)
# 2. 从 astrbot.api.event 中去掉 EventMessageType (修复 ImportError)
from astrbot.api.all import *
from astrbot.api.star import Star, Context, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.message_components import Record
from astrbot.api import logger
# ============================================

from .voice_manager import VoiceManager
from .scheduler import VoiceScheduler

@register(
    "echo_of_theresia",
    "riceshowerX",
    "1.0.5",
    "明日方舟特雷西娅角色语音插件"
)
class TheresiaVoicePlugin(Star):  # 确认继承 Star
    """
    特雷西娅语音插件核心类
    """
    
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}

        # ================= 配置初始化 =================
        self.config.setdefault("enabled", True)
        self.config.setdefault("command.keywords", ["特雷西娅", "特蕾西娅", "Theresia"])
        self.config.setdefault("command.prefix", "/theresia")
        self.config.setdefault("voice.default_tag", "")

        # 定时任务配置
        self.config.setdefault("schedule.enabled", False)
        self.config.setdefault("schedule.time", "08:00")
        self.config.setdefault("schedule.frequency", "daily")
        self.config.setdefault("schedule.voice_tags", [])
        self.config.setdefault("schedule.target_sessions", [])

        # ================= 资源加载 =================
        self.plugin_root = Path(__file__).parent.resolve()
        
        # 初始化管理器
        self.voice_manager = VoiceManager(self)
        self.voice_manager.load_voices() 
        
        # 初始化调度器
        self.scheduler = VoiceScheduler(self, self.voice_manager)

        # ================= 启动异步任务 =================
        if self.config.get("enabled", True):
            asyncio.create_task(self.scheduler.start())
            logger.info("[Echo of Theresia] 插件加载完成，定时服务已启动")

    async def on_unload(self):
        """插件卸载时清理资源"""
        await self.scheduler.stop()
        logger.info("[Echo of Theresia] 插件已卸载")

    # ================= 辅助方法 =================

    def _rel_to_abs(self, rel_path: str | None) -> Path | None:
        if not rel_path:
            return None
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
        if abs_path is None or not abs_path.exists():
            logger.warning(f"[Echo of Theresia] 文件缺失: {rel_path}")
            yield event.plain_result("语音文件走丢了哦~（文件路径异常）")
            return

        logger.info(f"[Echo of Theresia] 发送语音: {abs_path.name}")

        try:
            chain = [Record(file=str(abs_path))]
            yield event.chain_result(chain)
        except Exception as e:
            logger.error(f"[Echo of Theresia] 发送失败: {e}")
            yield event.plain_result(f"发送语音时出现错误: {e}")

    # ==================== 统一指令入口 ====================
    
    @filter.command("theresia")
    async def main_command_handler(self, event: AstrMessageEvent, action: str = None, payload: str = None):
        """特雷西娅插件主指令"""
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
            yield event.plain_result("特雷西娅语音插件已禁用，期待下次相见。")

        elif action == "voice":
            actual_tag = payload or self.config["voice.default_tag"]
            rel_path = self.voice_manager.get_voice(actual_tag)
            async for msg in self.safe_yield_voice(event, rel_path):
                yield msg

        elif action == "tags":
            tags = self.voice_manager.get_tags()
            if not tags:
                yield event.plain_result("暂无标签数据")
            else:
                lines = ["【可用语音标签】"] + [f"• {t}: {self.voice_manager.get_voice_count(t)} 条" for t in tags]
                yield event.plain_result("\n".join(lines))

        elif action == "update":
            yield event.plain_result("正在重新扫描思维链环...")
            self.voice_manager.update_voices()
            total = self.voice_manager.get_voice_count()
            yield event.plain_result(f"更新完成！当前共收录 {total} 条语音。")

        elif action == "set_target":
            await self.scheduler.add_target(event.session_id)
            yield event.plain_result("已将本会话设为定时问候目标，请期待吧~")

        elif action == "unset_target":
            await self.scheduler.remove_target(event.session_id)
            yield event.plain_result("已取消本会话的定时问候。")

        else:
            yield event.plain_result(f"未知指令: {action}")

    # ==================== 关键词触发 ====================
    
    # 修复：使用 filter.EventMessageType.ALL 代替直接 import
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def keyword_trigger(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True):
            return

        text = (event.message_str or "").strip()
        if not text:
            return

        cmd_prefix = self.config.get("command.prefix", "/theresia").lower()
        if text.lower().startswith(cmd_prefix):
            return
            
        first_word = text.split()[0].lower()
        if first_word == "theresia":
            return

        lowered = text.lower()
        keywords = [kw.lower() for kw in self.config["command.keywords"]]
        
        if any(kw in lowered for kw in keywords):
            tag = self.config["voice.default_tag"]
            rel_path = self.voice_manager.get_voice(tag or None)
            async for msg in self.safe_yield_voice(event, rel_path):
                yield msg

    def _get_help_text(self, brief: bool = True) -> str:
        if brief:
            return "Echo of Theresia 已就绪~\n发送 /theresia help 查看完整指令。"
        else:
            return (
                "【Echo of Theresia 指令列表】\n"
                "/theresia enable/disable - 启停插件\n"
                "/theresia voice [标签] - 点播语音\n"
                "/theresia tags - 查看标签\n"
                "/theresia update - 刷新资源\n"
                "/theresia set_target - 设置定时推送\n"
                "直接发送「特雷西娅」也可触发语音哦♪"
            )