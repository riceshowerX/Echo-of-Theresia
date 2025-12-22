# -*- coding: utf-8 -*-
"""
Echo of Theresia - 修复版（完美兼容 WebUI 和所有平台）
"""

from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.event.filter import EventMessageType
from astrbot.api import logger
from astrbot.api.message_components import Record, MessageComponent
from astrbot.api.message.event import WebChatMessageEvent  # 导入 Web 事件类型用于判断

from .voice_manager import VoiceManager
from .scheduler import VoiceScheduler

import os

@register(
    "echo_of_theresia",
    "你的名字或昵称",
    "明日方舟特雷西娅角色语音插件",
    "1.0.1"  # 建议版本号 +1 表示修复
)
class TheresiaVoicePlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}
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

    def _get_base_url(self) -> str:
        """获取 AstrBot 的静态文件服务 URL（用于 WebUI 播放语音）"""
        # AstrBot 默认静态文件路径为 /static/plugins/<plugin_id>/
        plugin_id = "echo_of_theresia"
        return f"/static/plugins/{plugin_id}/voices"

    async def safe_yield_voice(self, event: AstrMessageEvent, path: str):
        """
        安全发送语音，自动适配不同平台
        """
        if not os.path.exists(path):
            yield event.plain_result("语音文件不存在哦~")
            return

        # 判断是否支持 chain() 方法（主流平台如 QQ、Telegram 支持）
        if hasattr(event, "chain"):
            yield event.chain([Record(file=path)])
        else:
            # WebUI 等不支持 chain 的平台：发送可直接播放的 URL
            filename = os.path.basename(path)
            voice_url = f"{self._get_base_url()}/{filename}"
            # WebUI 支持直接播放 URL 的 Record
            yield event.chain([Record(url=voice_url)]) if hasattr(event, "chain") else None
            
            # 更稳妥的方式：发送文字 + URL（兼容性最高）
            yield event.plain_result(f"特雷西娅的语音：\n{voice_url}")

    # 关键词触发
    @filter.event_message_type(EventMessageType.ALL)
    async def keyword_trigger(self, event: AstrMessageEvent):
        enabled = self.config.get("enabled", True)
        if not enabled:
            return

        keywords = self.config.get("command.keywords", ["特雷西娅", "特蕾西娅", "Theresia"])
        text = event.message_str or ""
        prefix = self.config.get("command.prefix", "/theresia")

        # 避免命令也被关键词触发
        if text.startswith(prefix):
            return

        if any(kw in text for kw in keywords):
            tag = self.config.get("voice.default_tag", "")
            path = self.voice_manager.get_voice(tag or None)
            if path:
                async for msg in self.safe_yield_voice(event, path):
                    yield msg

    # 主命令
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

    @filter.command("theresia enable")
    async def enable(self, event: AstrMessageEvent):
        self.config["enabled"] = True
        self.config.save_config()
        await self.scheduler.start()
        yield event.plain_result("特雷西娅语音插件已启用♪")

    @filter.command("theresia disable")
    async def disable(self, event: AstrMessageEvent):
        self.config["enabled"] = False
        self.config.save_config()
        await self.scheduler.stop()
        yield event.plain_result("特雷西娅语音插件已禁用")

    @filter.command("theresia voice")
    async def voice(self, event: AstrMessageEvent, tag: str = ""):
        actual_tag = tag.strip() if tag else None
        path = self.voice_manager.get_voice(actual_tag)
        if not path:
            yield event.plain_result("未找到匹配的语音哦~")
            return

        async for msg in self.safe_yield_voice(event, path):
            yield msg

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

    @filter.command("theresia update")
    async def update(self, event: AstrMessageEvent):
        yield event.plain_result("正在重新扫描语音资源...")
        await self.voice_manager.update_voices()
        total = self.voice_manager.get_voice_count()
        yield event.plain_result(f"更新完成！共 {total} 条语音")

    @filter.command("theresia set_target")
    async def set_target(self, event: AstrMessageEvent):
        await self.scheduler.add_target(event.session_id)
        yield event.plain_result("本会话已设为定时发送目标，特雷西娅会准时出现~")

    @filter.command("theresia unset_target")
    async def unset_target(self, event: AstrMessageEvent):
        await self.scheduler.remove_target(event.session_id)
        yield event.plain_result("已取消本会话的定时发送")

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