# -*- coding: utf-8 -*-
"""
Echo of Theresia - 完全兼容旧版 AstrBot 的最终版
（无 subcommand，支持一级命令 + 关键词触发）
"""

from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.event.filter import EventMessageType  # 兼容关键词触发
from astrbot.api import logger
from astrbot.api.message_components import Record

from .voice_manager import VoiceManager
from .scheduler import VoiceScheduler

# 位置参数注册（兼容你的版本）
@register(
    "echo_of_theresia",
    "你的名字或昵称",
    "明日方舟特雷西娅角色语音插件",
    "1.0.0"
)
class TheresiaVoicePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.voice_manager = VoiceManager(self)
        self.scheduler = VoiceScheduler(self, self.voice_manager)

    async def initialize(self) -> None:
        logger.info("[Echo of Theresia] 插件加载中...")
        await self.voice_manager.load_voices()
        await self.scheduler.start()
        logger.info("[Echo of Theresia] 插件加载完成")

    async def on_unload(self) -> None:
        await self.scheduler.stop()
        logger.info("[Echo of Theresia] 插件已卸载")

    # 关键词触发
    @filter.event_message_type(EventMessageType.ALL)
    async def keyword_trigger(self, event: AstrMessageEvent):
        enabled = await self.context.config.get("enabled", True)
        if not enabled:
            return

        keywords = await self.context.config.get("command.keywords", ["特雷西娅", "特蕾西娅", "Theresia"])
        text = event.get_plain_text() or ""
        prefix = await self.context.config.get("command.prefix", "/theresia")

        if text.startswith(prefix):
            return

        if any(kw in text for kw in keywords):
            tag = await self.context.config.get("voice.default_tag", "")
            path = self.voice_manager.get_voice(tag or None)
            if path:
                yield event.chain([Record(file=path)])

    # 主命令：/theresia
    @filter.command("theresia")
    async def main_cmd(self, event: AstrMessageEvent):
        yield event.plain_result(
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

    # 启用插件
    @filter.command("theresia enable")
    async def enable(self, event: AstrMessageEvent):
        await self.context.config.set("enabled", True)
        await self.scheduler.start()
        yield event.plain_result("特雷西娅语音插件已启用♪")

    # 禁用插件
    @filter.command("theresia disable")
    async def disable(self, event: AstrMessageEvent):
        await self.context.config.set("enabled", False)
        await self.scheduler.stop()
        yield event.plain_result("特雷西娅语音插件已禁用")

    # 手动发送语音
    @filter.command("theresia voice")
    async def voice(self, event: AstrMessageEvent, tag: str = ""):
        actual_tag = tag.strip() if tag else None
        path = self.voice_manager.get_voice(actual_tag)
        if not path:
            yield event.plain_result("未找到匹配的语音哦~")
            return
        yield event.chain([Record(file=path)])

    # 查看标签
    @filter.command("theresia tags")
    async def tags(self, event: AstrMessageEvent):
        tags = self.voice_manager.get_tags()
        if not tags:
            yield event.plain_result("暂无语音资源")
            return
        lines = ["可用标签:"]
        for t in tags:
            count = self.voice_manager.get_voice_count(t)
            lines.append(f"• {t}: {count} 条")
        yield event.plain_result("\n".join(lines))

    # 更新语音索引
    @filter.command("theresia update")
    async def update(self, event: AstrMessageEvent):
        yield event.plain_result("正在重新扫描语音资源...")
        await self.voice_manager.update_voices()
        total = self.voice_manager.get_voice_count()
        yield event.plain_result(f"更新完成！共 {total} 条语音")

    # 设置定时目标
    @filter.command("theresia set_target")
    async def set_target(self, event: AstrMessageEvent):
        await self.scheduler.add_target(event.session_id)
        yield event.plain_result("本会话已设为定时发送目标，特雷西娅会准时出现~")

    # 取消定时目标
    @filter.command("theresia unset_target")
    async def unset_target(self, event: AstrMessageEvent):
        await self.scheduler.remove_target(event.session_id)
        yield event.plain_result("已取消本会话的定时发送")

    # 帮助（可与主命令重复，优先显示详细帮助）
    @filter.command("theresia help")
    async def help(self, event: AstrMessageEvent):
        help_text = """
【Echo of Theresia 完整命令】
/theresia               显示简要信息
/theresia enable        启用插件
/theresia disable       禁用插件
/theresia voice [标签]   手动发送语音
/theresia tags          查看所有标签及数量
/theresia update        重新扫描语音文件
/theresia set_target    设置当前群为定时目标
/theresia unset_target  取消定时目标
/theresia help          显示此详细帮助

提示：直接发送包含「特雷西娅」的消息也会自动触发语音哦♪
        """.strip()
        yield event.plain_result(help_text)