# -*- coding: utf-8 -*-
"""
命令处理模块
"""

from typing import Dict, Any, List

class CommandHandler:
    """命令处理类"""
    
    def __init__(self, plugin, voice_manager, scheduler):
        self.plugin = plugin
        # 使用AstrBot官方的配置管理
        self.config = plugin.config
        self.voice_manager = voice_manager
        self.scheduler = scheduler
    
    async def handle_message(self, message: Dict[str, Any]) -> None:
        """处理收到的消息"""
        if not self.config.get("enabled"):
            return
        
        # 获取消息内容
        msg_content = message.get("content", "").strip()
        if not msg_content:
            return
        
        # 检查是否为命令
        prefix = self.config.get("command.prefix", "/theresia")
        if msg_content.startswith(prefix):
            # 处理命令
            await self._handle_command(message, msg_content[len(prefix):].strip())
        else:
            # 检查是否包含关键词
            await self._check_keywords(message, msg_content)
    
    async def _handle_command(self, message: Dict[str, Any], command: str) -> None:
        """处理命令"""
        if not command:
            # 发送帮助信息
            await self._send_help(message)
            return
        
        # 解析命令
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:]
        
        # 执行对应命令
        if cmd == "enable":
            await self._cmd_enable(message)
        elif cmd == "disable":
            await self._cmd_disable(message)
        elif cmd == "config":
            await self._cmd_config(message)
        elif cmd == "set":
            await self._cmd_set(message, args)
        elif cmd == "voice":
            await self._cmd_voice(message, args)
        elif cmd == "tags":
            await self._cmd_tags(message)
        elif cmd == "update":
            await self._cmd_update(message)
        elif cmd == "help":
            await self._send_help(message)
        else:
            await self._send_message(message, f"未知命令: {cmd}\n输入 /theresia help 查看帮助")
    
    async def _check_keywords(self, message: Dict[str, Any], content: str) -> None:
        """检查关键词触发"""
        keywords = self.config.get("command.keywords", [])
        for keyword in keywords:
            if keyword in content:
                # 发送随机语音
                await self._send_voice(message, "")
                break
    
    async def _cmd_enable(self, message: Dict[str, Any]) -> None:
        """启用插件"""
        self.config.set("enabled", True)
        self.scheduler.start()
        await self._send_message(message, "特雷西娅语音插件已启用")
    
    async def _cmd_disable(self, message: Dict[str, Any]) -> None:
        """禁用插件"""
        self.config.set("enabled", False)
        self.scheduler.stop()
        await self._send_message(message, "特雷西娅语音插件已禁用")
    
    async def _cmd_config(self, message: Dict[str, Any]) -> None:
        """查看配置"""
        config = self.config.get_all()
        config_str = "当前配置:\n"
        
        # 格式化配置
        if config.get("enabled"):
            config_str += "- 插件状态: 已启用\n"
        else:
            config_str += "- 插件状态: 已禁用\n"
        
        schedule = config.get("schedule", {})
        config_str += f"- 定时发送: {'启用' if schedule.get('enabled') else '禁用'}\n"
        config_str += f"- 发送时间: {schedule.get('time', '08:00')}\n"
        config_str += f"- 发送频率: {schedule.get('frequency', 'daily')}\n"
        config_str += f"- 语音标签: {', '.join(schedule.get('voice_tags', [])) or '所有'}\n"
        
        voice = config.get("voice", {})
        config_str += f"- 语音质量: {voice.get('quality', 'high')}\n"
        
        await self._send_message(message, config_str)
    
    async def _cmd_set(self, message: Dict[str, Any], args: List[str]) -> None:
        """设置配置"""
        if len(args) < 2:
            await self._send_message(message, "用法: /theresia set <config> <value>")
            return
        
        key = args[0]
        value = " ".join(args[1:])
        
        # 尝试转换值类型
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        elif value.isdigit():
            value = int(value)
        elif "," in value:
            # 处理列表值
            value = [v.strip() for v in value.split(",")]
        
        # 设置配置
        if self.config.set(key, value):
            await self._send_message(message, f"配置已更新: {key} = {value}")
            
            # 如果是定时相关配置，重启定时任务
            if key.startswith("schedule."):
                self.scheduler.update_schedule()
        else:
            await self._send_message(message, f"设置配置失败: {key}")
    
    async def _cmd_voice(self, message: Dict[str, Any], args: List[str]) -> None:
        """发送语音"""
        tag = args[0] if args else ""
        await self._send_voice(message, tag)
    
    async def _cmd_tags(self, message: Dict[str, Any]) -> None:
        """查看可用标签"""
        tags = self.voice_manager.get_tags()
        if not tags:
            await self._send_message(message, "暂无可用语音标签")
            return
        
        tags_str = "可用语音标签:\n"
        for tag in tags:
            count = self.voice_manager.get_voice_count(tag)
            tags_str += f"- {tag}: {count} 条语音\n"
        
        await self._send_message(message, tags_str)
    
    async def _cmd_update(self, message: Dict[str, Any]) -> None:
        """更新语音资源"""
        await self._send_message(message, "正在更新语音资源...")
        
        if self.voice_manager.update_voices():
            count = self.voice_manager.get_voice_count()
            await self._send_message(message, f"语音资源更新完成，共 {count} 条语音")
        else:
            await self._send_message(message, "语音资源更新失败")
    
    async def _send_voice(self, message: Dict[str, Any], tag: str) -> None:
        """发送语音"""
        voice_path = self.voice_manager.get_voice(tag)
        if not voice_path:
            await self._send_message(message, "未找到匹配的语音资源")
            return
        
        # 发送语音（这里需要根据AstrBot的API进行调整）
        # 示例：await self.plugin.send_voice(message, voice_path)
        await self._send_message(message, f"发送语音: {voice_path}")
    
    async def _send_help(self, message: Dict[str, Any]) -> None:
        """发送帮助信息"""
        help_str = "特雷西娅语音插件命令:\n"
        for cmd, desc in self.plugin.get_help().items():
            help_str += f"{cmd}: {desc}\n"
        
        await self._send_message(message, help_str)
    
    async def _send_message(self, message: Dict[str, Any], content: str) -> None:
        """发送消息（需要根据AstrBot的API实现）"""
        # 这里是示例实现，实际需要使用AstrBot的消息发送API
        print(f"发送消息: {content}")
        # 示例：await self.plugin.send_message(message, content)
