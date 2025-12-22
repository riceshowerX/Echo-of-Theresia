# -*- coding: utf-8 -*-
"""
Echo of Theresia - 最终完美版（QQ 直接发语音 + 兼容原 voice_manager）
"""

from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.event.filter import EventMessageType
from astrbot.api import logger
from astrbot.api.message_components import Record

from .voice_manager import VoiceManager
from .scheduler import VoiceScheduler

import os

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
        self.voice_manager = VoiceManager(self)
        self.scheduler = VoiceScheduler(self, self.voice_manager)

        # 计算插件根目录，用于将相对路径转为绝对路径
        self.plugin_root = os.path.dirname(os.path.abspath(__file__))

    async def initialize(self) -> None:
        logger.info("[Echo of Theresia] 插件加载中...")
        await self.voice_manager.load_voices()
        await self.scheduler.start()
        logger.info("[Echo of Theresia] 插件加载完成")

    async def on_unload(self) -> None:
        await self.scheduler.stop()
        logger.info("[Echo of Theresia] 插件已卸载")

    def _rel_to_abs(self, rel_path: str) -> str:
        """将 voice_manager 返回的相对路径转换为绝对路径"""
        return os.path.abspath(os.path.join(self.plugin_root, rel_path))

    def _get_voice_url(self, rel_path: str) -> str:
        """为 WebUI 生成静态资源 URL"""
        filename = os.path.basename(rel_path)
        return f"/static/plugins/echo_of_theresia/voices/{filename}"

    async def safe_yield_voice(self, event: AstrMessageEvent, rel_path: str):
        """优先发送真实语音消息（QQ 会直接发语音，WebUI 自动降级）"""
        if not rel_path:
            yield event.plain_result("未找到匹配的语音哦~")
            return

        abs_path = self._rel_to_abs(rel_path)

        if not os.path.exists(abs_path):
            logger.warning(f"[语音发送] 文件不存在: {abs_path} (相对路径: {rel_path})")
            yield event.plain_result("语音文件不存在哦~（路径异常）")
            return

        logger.info(f"[语音发送] 正在发送语音文件: {abs_path}")

        # 关键：直接使用 chain 发送本地文件
        # 支持的平台（如 QQ）会直接上传并发送语音消息
        # 不支持的平台（如 WebUI）AstrBot 核心会自动降级为文字或 URL
        yield event.chain([Record(file=abs_path)])

        # 可选：为 WebUI 额外补一个可点击的 URL（防止某些情况下 chain 被忽略）
        # 如果你发现 WebUI 完全没反应，可以取消下面注释
        # voice_url = self._get_voice_url(rel_path)
        # yield event.plain_result(f"（Web 播放地址：{voice_url}）")

    # 关键词触发
    @filter.event_message_type(EventMessageType.ALL)
    async def keyword_trigger(self, event: AstrMessageEvent):
        enabled = self.config.get("enabled", True)
        if not enabled:
            return

        keywords = self.config.get("command.keywords", ["特雷西娅", "特蕾西娅", "Theresia"])
        text = event.message_str or ""
        prefix = self.config.get("command.prefix", "/theresia")

        if text.startswith(prefix):
            return

        if any(kw in text for kw in keywords):
            tag = self.config.get("voice.default_tag", "")
            rel_path = self.voice_manager.get_voice(tag or None)
            if rel_path:
                async for msg in self.safe_yield_voice(event, rel_path):
                    yield msg

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
        rel_path = self.voice_manager.get_voice(actual_tag)
        if not rel_path:
            yield event.plain_result("未找到匹配的语音哦~")
            return

        async for msg in self.safe_yield_voice(event, rel_path):
            yield msg

    @filter.command("theresia tags")
    async def tags(self, event: AstrMessageEvent):
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
/theresia voice [标签]   手动发送语音（如：/theresia voice 问候）
/theresia tags          查看所有标签及数量
/theresia update        重新扫描语音文件
/theresia set_target    设置当前会话为定时目标
/theresia unset_target  取消定时目标
/theresia help          显示此帮助

提示：直接发送包含「特雷西娅」的消息也会自动触发随机语音哦♪
        """.strip()
        yield event.plain_result(help_text)