from pathlib import Path
from typing import Context, Dict, Any, Optional
import logging

class EchoOfTheresia:
    def __init__(self, context: Context, config: Optional[Dict[str, Any]] = None):
        super().__init__(context)
        self.context = context
        self.logger = context.logger or logging.getLogger("EchoOfTheresia")
        self.config = self._init_config(config or {})

        # 初始化核心模块
        self.voice_manager = VoiceManager(self)
        self.scheduler = VoiceScheduler(self, self.voice_manager)

        # 插件目录
        self.plugin_root = Path(__file__).parent.resolve()
        self.logger.info(f"特雷西娅语音插件初始化完成，根目录：{self.plugin_root}")

    def _init_config(self, user_config: Dict[str, Any]) -> Dict[str, Any]:
        """初始化配置（合并用户配置与默认配置）"""
        # 默认配置模板
        default_config = {
            "enabled": True,
            "command": {
                "prefix": "/theresia",
                "keywords": ["特雷西娅", "特蕾西娅", "Theresia"]
            },
            "voice": {
                "default_tag": ""
            },
            "schedule": {
                "enabled": False,
                "time": "08:00",
                "frequency": "daily",
                "voice_tags": [],
                "target_sessions": []
            }
        }

        # 递归合并用户配置（用户配置优先级更高）
        def merge_config(default: Dict, user: Dict) -> Dict:
            merged = default.copy()
            for key, value in user.items():
                if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                    merged[key] = merge_config(merged[key], value)
                else:
                    merged[key] = value
            return merged

        return merge_config(default_config, user_config)

    async def on_message(self, message: Dict[str, Any]) -> None:
        """处理收到的消息（关键词触发逻辑）"""
        # 检查插件总开关
        if not self.config.get("enabled", True):
            return

        content = message.get("content", "").strip()
        session_id = message.get("session_id")
        if not content or not session_id:
            return  # 忽略空消息或无会话ID的消息

        # 检查是否包含触发关键词
        keywords = self.config.get("command", {}).get("keywords", [])
        if any(keyword in content for keyword in keywords):
            self.logger.info(f"[关键词触发] 会话 {session_id} 包含关键词，准备发送语音")
            await self._send_triggered_voice(session_id)

    async def _send_triggered_voice(self, session_id: str) -> None:
        """发送关键词触发的语音"""
        default_tag = self.config.get("voice", {}).get("default_tag", "")
        target_tags = [default_tag] if default_tag else []
        
        # 获取匹配的语音
        voice = self.voice_manager.get_matched_voice(target_tags)
        if not voice:
            self.logger.error("没有可用语音文件，无法发送")
            return

        # 发送语音
        try:
            await self.send_voice(session_id, voice["path"])
            self.logger.info(f"[关键词发送] 已向 {session_id} 发送语音：{voice['filename']}")
        except Exception as e:
            self.logger.error(f"[关键词发送] 向 {session_id} 发送失败：{str(e)}")

    async def send_voice(self, session_id: str, file_path: str) -> None:
        """发送语音文件到指定会话（需根据实际框架实现）"""
        # 此处为框架适配示例，实际需替换为对应机器人框架的发送方法
        await self.context.send_voice(
            session_id=session_id,
            file_path=file_path,
            timeout=30
        )

    async def shutdown(self) -> None:
        """插件关闭时清理资源"""
        if self.scheduler.task:
            self.scheduler.task.cancel()
            try:
                await self.scheduler.task
            except asyncio.CancelledError:
                self.logger.info("定时任务已取消")
        self.logger.info("特雷西娅语音插件已关闭")