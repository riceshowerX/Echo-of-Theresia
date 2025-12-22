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
        # 使用官方规范的插件名称
        self.name = "astrbot_plugin_theresia_voice"
        self.version = "1.0.0"
        self.description = "明日方舟特雷西娅角色语音插件，支持定时发送和对话触发功能"
        self.author = "AstrBot Dev"
        
        # 初始化默认配置（使用官方配置机制）
        self._init_default_config()
        
        # 初始化插件组件
        # 使用AstrBot官方的self.config属性进行配置管理
        self.voice_manager = VoiceManager(self)
        self.scheduler = VoiceScheduler(self, self.voice_manager)
        self.command_handler = CommandHandler(self, self.voice_manager, self.scheduler)
    
    def _init_default_config(self) -> None:
        """初始化默认配置"""
        # 使用AstrBot官方的配置机制，自动处理配置的加载和保存
        # 设置默认配置
        default_config = {
            "enabled": True,
            "schedule": {
                "enabled": False,
                "time": "08:00",
                "frequency": "daily",  # daily, weekly, hourly
                "voice_tags": []  # 空列表表示所有语音
            },
            "command": {
                "prefix": "/theresia",
                "keywords": ["特雷西娅", "特蕾西娅", "Theresia"]
            },
            "voice": {
                "quality": "high",  # high, medium, low
                "default_tag": ""
            }
        }
        
        # AstrBot会自动合并默认配置和用户配置
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
    
    def on_load(self) -> None:
        """插件加载时执行"""
        logger.info(f"[{self.name}] 插件加载中...")
        
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
    
    # 使用AstrBot官方的消息事件装饰器
    from astrbot.event import event
    
    @event.receive_message
    async def handle_message(self, message: Dict[str, Any]) -> None:
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

# 注册插件 - 使用官方规范的插件名称
plugin.register_plugin("astrbot_plugin_theresia_voice", TheresiaVoicePlugin)
