# -*- coding: utf-8 -*-
"""
Echo of Theresia - 最终完美版 (Refactored)
适配 AstrBot (2025)
"""

import asyncio
from pathlib import Path

# 引入 AstrBot 核心组件
from astrbot.api.all import *
from astrbot.api.message_components import Record

# 引入本地模块 (确保这两个文件在同级目录)
from .voice_manager import VoiceManager
from .scheduler import VoiceScheduler

@register(
    "echo_of_theresia",
    "riceshowerX",
    "明日方舟特雷西娅角色语音插件",
    "1.0.5"
)
class TheresiaVoicePlugin(StarryPlugin):
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
        self.voice_manager.load_voices() # 同步加载资源
        
        # 初始化调度器
        self.scheduler = VoiceScheduler(self, self.voice_manager)

        # ================= 启动异步任务 =================
        # 使用 create_task 确保不阻塞主线程，且无需等待 initialize 回调
        if self.config.get("enabled", True):
            asyncio.create_task(self.scheduler.start())
            logger.info("[Echo of Theresia] 定时任务服务已启动")

    # ================= 辅助方法 =================

    def _rel_to_abs(self, rel_path: str | None) -> Path | None:
        if not rel_path:
            return None
        return (self.plugin_root / rel_path).resolve()

    async def safe_yield_voice(self, event: AstrMessageEvent, rel_path: str | None):
        """安全发送语音的通用方法"""
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
            # 构建语音消息链
            chain = [Record(file=str(abs_path))]
            yield event.chain_result(chain)
        except Exception as e:
            logger.error(f"[Echo of Theresia] 发送失败: {e}")
            yield event.plain_result(f"发送语音时出现错误: {e}")

    def _save_config(self):
        """尝试保存配置"""
        # 注意：AstrBot 的 config 对象如果是代理对象通常会自动保存
        # 如果是普通字典，需要框架支持。这里保留兼容性调用。
        try:
            if hasattr(self.config, "save_config"):
                self.config.save_config()
        except Exception:
            pass

    # ==================== 统一指令入口 (核心修改) ====================
    
    @filter.command("theresia")
    async def main_command_handler(self, event: AstrMessageEvent, action: str = None, payload: str = None):
        """
        特雷西娅插件主指令
        用法: /theresia [action] [payload]
        """
        # 1. 权限与状态检查
        # 如果需要可以在这里加
        
        # 2. 空指令处理 -> 显示帮助
        if not action:
            yield event.plain_result(self._get_help_text(brief=True))
            return

        action = action.lower()

        # 3. 路由分发
        if action == "help":
            yield event.plain_result(self._get_help_text(brief=False))

        elif action == "enable":
            if self.config["enabled"]:
                yield event.plain_result("插件已经是启用状态了哦~")
            else:
                self.config["enabled"] = True
                self._save_config()
                asyncio.create_task(self.scheduler.start())
                yield event.plain_result("特雷西娅语音插件已启用♪")

        elif action == "disable":
            if not self.config["enabled"]:
                yield event.plain_result("插件已经是禁用状态了。")
            else:
                self.config["enabled"] = False
                self._save_config()
                asyncio.create_task(self.scheduler.stop())
                yield event.plain_result("特雷西娅语音插件已禁用，期待下次相见。")

        elif action == "voice":
            # payload 即为 tag
            actual_tag = payload or self.config["voice.default_tag"]
            rel_path = self.voice_manager.get_voice(actual_tag)
            async for msg in self.safe_yield_voice(event, rel_path):
                yield msg

        elif action == "tags":
            tags = self.voice_manager.get_tags()
            if not tags:
                yield event.plain_result("暂无标签数据")
                return
            lines = ["【可用语音标签】"]
            for t in tags:
                count = self.voice_manager.get_voice_count(t)
                lines.append(f"• {t}: {count} 条")
            yield event.plain_result("\n".join(lines))

        elif action == "update":
            yield event.plain_result("正在重新扫描思维链环（更新语音库）...")
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
            yield event.plain_result(f"未知指令: {action}，请尝试 /theresia help")

    # ==================== 关键词触发 (保留防冲突逻辑) ====================
    
    @filter.event_message_type(EventMessageType.ALL)
    async def keyword_trigger(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True):
            return

        text = (event.message_str or "").strip()
        if not text:
            return

        # 1. 防冲突：如果是指令前缀开头，绝对不触发关键词
        cmd_prefix = self.config.get("command.prefix", "/theresia").lower()
        if text.lower().startswith(cmd_prefix):
            return

        # 2. 防冲突：如果第一个词是 theresia，也不触发（留给指令处理器）
        first_word = text.split()[0].lower()
        if first_word == "theresia":
            return

        # 3. 关键词匹配
        lowered = text.lower()
        keywords = [kw.lower() for kw in self.config["command.keywords"]]
        
        if any(kw in lowered for kw in keywords):
            logger.info(f"[Echo of Theresia] 关键词触发: {text[:10]}...")
            tag = self.config["voice.default_tag"]
            rel_path = self.voice_manager.get_voice(tag or None)
            
            async for msg in self.safe_yield_voice(event, rel_path):
                yield msg

    # ==================== 帮助文本 ====================

    def _get_help_text(self, brief: bool = True) -> str:
        if brief:
            return (
                "Echo of Theresia 已就绪~\n"
                "常用指令：\n"
                "/theresia voice [标签]  - 发送语音\n"
                "/theresia tags         - 查看标签\n"
                "/theresia help         - 完整菜单\n\n"
                "提示：直接在对话中提到「特雷西娅」也可以触发哦♪"
            )
        else:
            return """
【Echo of Theresia 完整指令列表】
------------------------------
/theresia                显示简要信息
/theresia help           显示此帮助
/theresia enable         启用插件功能
/theresia disable        禁用插件功能
/theresia update         重新扫描语音文件
/theresia voice [标签]    发送指定标签或随机语音
/theresia tags           列出所有语音标签及数量
/theresia set_target     [定时] 将当前会话设为推送目标
/theresia unset_target   [定时] 取消当前会话的推送
------------------------------
直接发送包含「特雷西娅」的消息也会自动触发随机语音♪
            """.strip()