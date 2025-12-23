# -*- coding: utf-8 -*-
"""
Echo of Theresia - 最终完美版
完全适配最新 AstrBot（2025）
"""

from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.event.filter import EventMessageType
from astrbot.api import logger
from astrbot.api.message_components import Record

from .voice_manager import VoiceManager
from .scheduler import VoiceScheduler

from pathlib import Path


@register(
    "echo_of_theresia",
    "特雷西娅",
    "明日方舟特雷西娅角色语音插件",
    "1.0.5"
)
class TheresiaVoicePlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}

        # 默认配置
        self.config.setdefault("enabled", True)
        self.config.setdefault("command.keywords", ["特雷西娅", "特蕾西娅", "Theresia"])
        self.config.setdefault("command.prefix", "/theresia")
        self.config.setdefault("voice.default_tag", "")

        # 定时任务默认配置
        self.config.setdefault("schedule.enabled", False)
        self.config.setdefault("schedule.time", "08:00")
        self.config.setdefault("schedule.frequency", "daily")
        self.config.setdefault("schedule.voice_tags", [])
        self.config.setdefault("schedule.target_sessions", [])

        self.voice_manager = VoiceManager(self)
        self.scheduler = VoiceScheduler(self, self.voice_manager)

        # 插件根目录
        self.plugin_root = Path(__file__).parent.resolve()

    async def initialize(self) -> None:
        logger.info("[Echo of Theresia] 插件加载中...")
        self.voice_manager.load_voices()  # 同步加载，无 await
        if self.config.get("enabled", True):
            await self.scheduler.start()
        logger.info("[Echo of Theresia] 插件加载完成")

    async def on_unload(self) -> None:
        await self.scheduler.stop()
        logger.info("[Echo of Theresia] 插件已卸载")

    def _rel_to_abs(self, rel_path: str) -> Path:
        return (self.plugin_root / rel_path).resolve()

    async def safe_yield_voice(self, event: AstrMessageEvent, rel_path: str | None):
        if not rel_path:
            yield event.plain_result("未找到匹配的语音哦~")
            return

        abs_path = self._rel_to_abs(rel_path)

        if not abs_path.exists():
            logger.warning(f"[语音发送] 文件不存在: {abs_path}")
            yield event.plain_result("语音文件不存在哦~（路径异常）")
            return

        logger.info(f"[语音发送] 正在发送语音文件: {abs_path}")

        try:
            chain = [Record(file=str(abs_path))]
            yield event.chain_result(chain)
        except Exception as e:
            logger.error(f"[语音发送] 发送失败: {e}")
            yield event.plain_result("发送语音失败了呢…请查看日志")

    # 关键词触发 - 加强排除
    @filter.event_message_type(EventMessageType.ALL)
    async def keyword_trigger(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True):
            return

        text = (event.message_str or "").strip()
        if not text:
            return

        # 超级严格排除：所有以 /theresia 开头的消息（无论后面有什么）
        if text.lower().startswith("/theresia"):
            return

        lowered = text.lower()
        keywords = [kw.lower() for kw in self.config["command.keywords"]]
        if any(kw in lowered for kw in keywords):
            # 只发默认标签的随机语音
            tag = self.config["voice.default_tag"]
            rel_path = self.voice_manager.get_voice(tag or None)
            if rel_path:
                async for msg in self.safe_yield_voice(event, rel_path):
                    yield msg

    # ==================== 命令定义（适配最新 AstrBot 参数规则） ====================

    @filter.command("theresia")
    async def main_cmd(self, event: AstrMessageEvent, _empty: str = ""):
        """仅在精确输入 /theresia（无任何额外内容）时显示帮助"""
        # 额外保险：检查原始消息是否正好是 /theresia（忽略大小写和前后空格）
        raw_text = (event.message_str or "").strip()
        if raw_text.lower() != "/theresia":
            return
        yield event.plain_result(self._get_help_text(brief=True))

    @filter.command("theresia enable")
    async def enable(self, event: AstrMessageEvent, _empty: str = ""):
        self.config["enabled"] = True
        self.config.save_config()
        await self.scheduler.start()
        yield event.plain_result("特雷西娅语音插件已启用♪")

    @filter.command("theresia disable")
    async def disable(self, event: AstrMessageEvent, _empty: str = ""):
        self.config["enabled"] = False
        self.config.save_config()
        await self.scheduler.stop()
        yield event.plain_result("特雷西娅语音插件已禁用")

    @filter.command("theresia voice")
    async def voice(self, event: AstrMessageEvent, tag: str = ""):
        """支持 /theresia voice [标签]，tag 为空时使用默认标签"""
        actual_tag = tag.strip() or self.config["voice.default_tag"]
        rel_path = self.voice_manager.get_voice(actual_tag)
        if not rel_path:
            yield event.plain_result("未找到匹配的语音哦~")
            return
        async for msg in self.safe_yield_voice(event, rel_path):
            yield msg

    @filter.command("theresia tags")
    async def tags(self, event: AstrMessageEvent, _empty: str = ""):
        tags = self.voice_manager.get_tags()
        if not tags:
            yield event.plain_result("暂无标签（但可能有语音）")
            return
        lines = ["可用标签:"]
        for t in tags:
            count = self.voice_manager.get_voice_count(t)
            lines.append(f"• {t}: {count} 条")
        yield event.plain_result("\n".join(lines))

    @filter.command("theresia update")
    async def update(self, event: AstrMessageEvent, _empty: str = ""):
        yield event.plain_result("正在重新扫描语音资源...")
        self.voice_manager.update_voices()  # 同步调用
        total = self.voice_manager.get_voice_count()
        yield event.plain_result(f"更新完成！共 {total} 条语音")

    @filter.command("theresia set_target")
    async def set_target(self, event: AstrMessageEvent, _empty: str = ""):
        await self.scheduler.add_target(event.session_id)
        yield event.plain_result("本会话已设为定时发送目标，特雷西娅会准时出现~")

    @filter.command("theresia unset_target")
    async def unset_target(self, event: AstrMessageEvent, _empty: str = ""):
        await self.scheduler.remove_target(event.session_id)
        yield event.plain_result("已取消本会话的定时发送")

    @filter.command("theresia help")
    async def help_cmd(self, event: AstrMessageEvent, _empty: str = ""):
        yield event.plain_result(self._get_help_text(brief=False))

    # ==================== 帮助文本 ====================

    def _get_help_text(self, brief: bool = True) -> str:
        if brief:
            return (
                "Echo of Theresia 已就绪~\n"
                "命令列表：\n"
                "/theresia enable      启用插件\n"
                "/theresia disable     禁用插件\n"
                "/theresia voice [标签] 手动发送语音\n"
                "/theresia tags        查看标签\n"
                "/theresia update      重新扫描语音\n"
                "/theresia set_target  设置定时目标\n"
                "/theresia unset_target 取消定时目标\n"
                "/theresia help        显示帮助\n\n"
                "直接说「特雷西娅」也可触发♪"
            )
        else:
            return """
【Echo of Theresia 完整命令】
/theresia               显示简要信息
/theresia enable        启用插件
/theresia disable       禁用插件
/theresia voice [标签]   手动发送语音（如：/theresia voice 问候）
/theresia tags          查看所有标签及数量
/theresia update        重新扫描语音文件
/theresia set_target    设置当前会话为定时目标
/theresia unset_target  取消定时目标
/theresia help          显示此帮助

提示：直接发送包含「特雷西娅」的消息也会自动触发随机语音哦♪
            """.strip()