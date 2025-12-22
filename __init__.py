# -*- coding: utf-8 -*-
"""
AstrBot 明日方舟特雷西娅语音插件
实现特雷西娅角色语音的定时发送和对话触发功能
"""

import os
import sys
from typing import Dict, Any

from astrbot import plugin
from astrbot.plugin import Plugin
from astrbot.log import logger

# 添加插件目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入插件模块
from .config import Config
from .voice_manager import VoiceManager
from .scheduler import VoiceScheduler
from .command_handler import CommandHandler

class TheresiaVoicePlugin(Plugin):
    """特雷西娅语音插件"""
    
    def __init__(self):
        super().__init__()
        self.name = "echo_of_theresia"
        self.version = "1.0.0"
        self.description = "明日方舟特雷西娅角色语音插件 - Echo of Theresia"
        self.author = "AstrBot Dev"
        
        # 初始化插件组件
        self.config = Config()
        self.voice_manager = VoiceManager(self.config)
        self.scheduler = VoiceScheduler(self, self.config, self.voice_manager)
        self.command_handler = CommandHandler(self, self.config, self.voice_manager, self.scheduler)
    
    def on_load(self) -> None:
        """插件加载时执行"""
        logger.info(f"[{self.name}] 插件加载中...")
        
        # 加载配置
        self.config.load()
        
        # 加载语音资源
        self.voice_manager.load_voices()
        
        # 启动定时任务
        self.scheduler.start()
        
        logger.info(f"[{self.name}] 插件加载完成")
    
    def on_unload(self) -> None:
        """插件卸载时执行"""
        logger.info(f"[{self.name}] 插件卸载中...")
        
        # 停止定时任务
        self.scheduler.stop()
        
        logger.info(f"[{self.name}] 插件卸载完成")
    
    async def on_message(self, message: Dict[str, Any]) -> None:
        """处理收到的消息"""
        await self.command_handler.handle_message(message)
    
    def get_help(self) -> Dict[str, str]:
        """获取插件帮助信息"""
        return {
            "/theresia enable": "启用插件",
            "/theresia disable": "禁用插件",
            "/theresia config": "查看配置",
            "/theresia set <config> <value>": "设置配置",
            "/theresia voice [tag]": "发送随机语音",
            "/theresia tags": "查看可用标签",
            "/theresia update": "更新语音资源"
        }

# 注册插件
plugin.register_plugin("echo_of_theresia", TheresiaVoicePlugin)
