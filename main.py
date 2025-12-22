# -*- coding: utf-8 -*-
"""
AstrBot 明日方舟特雷西娅语音插件
实现特雷西娅角色语音的定时发送和对话触发功能
"""

import os
import sys
import random
import json
import asyncio
import time
from typing import Dict, Any, List

# 使用AstrBot Star插件框架
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api import logger
from astrbot.api.message_components import Plain, Record

# 导入语音资源管理和定时任务模块
from .voice_manager import VoiceManager
from .scheduler import VoiceScheduler

@register(
    name="echo_of_theresia",
    author="AstrBot Dev",
    desc="明日方舟特雷西娅角色语音插件，支持定时发送和对话触发功能",
    version="1.0.0"
)
class TheresiaVoicePlugin(Star):
    """特雷西娅语音插件"""
    
    def __init__(self, context: Context):
        super().__init__(context)
        
        # 初始化插件组件
        self.voice_manager = VoiceManager(self)
        self.scheduler = VoiceScheduler(self, self.voice_manager)
        
        # 缓存配置，避免频繁异步获取
        self._config_cache = {}
    
    async def on_load(self) -> None:
        """插件加载时执行"""
        logger.info(f"[{self.name}] 插件加载中...")
        
        # 加载配置缓存
        self._config_cache = await self.context.config.get_all_config()
        
        # 更新VoiceManager的配置缓存
        self.voice_manager.update_config(self._config_cache)
        
        # 加载语音资源
        self.voice_manager.load_voices()
        
        # 启动定时任务
        self.scheduler.start()
        
        logger.info(f"[{self.name}] 插件加载完成")
    
    async def terminate(self) -> None:
        """插件卸载时执行"""
        logger.info(f"[{self.name}] 插件卸载中...")
        
        # 停止定时任务
        self.scheduler.stop()
        
        logger.info(f"[{self.name}] 插件卸载完成")
    
    # 注册指令组
    @filter.command_group("theresia")
    async def theresia_group(self, event: AstrMessageEvent):
        """特雷西娅语音插件指令组"""
        pass
    
    # 启用插件指令
    @theresia_group.command("enable")
    async def enable(self, event: AstrMessageEvent):
        """启用特雷西娅语音插件"""
        # 设置配置
        await self.context.config.set_config("enabled", True)
        # 更新配置缓存
        self._config_cache["enabled"] = True
        # 更新VoiceManager的配置缓存
        self.voice_manager.update_config(self._config_cache)
        # 启动定时任务
        self.scheduler.start()
        yield event.plain_result("特雷西娅语音插件已启用")
    
    # 禁用插件指令
    @theresia_group.command("disable")
    async def disable(self, event: AstrMessageEvent):
        """禁用特雷西娅语音插件"""
        # 设置配置
        await self.context.config.set_config("enabled", False)
        # 更新配置缓存
        self._config_cache["enabled"] = False
        # 更新VoiceManager的配置缓存
        self.voice_manager.update_config(self._config_cache)
        # 停止定时任务
        self.scheduler.stop()
        yield event.plain_result("特雷西娅语音插件已禁用")
    
    # 查看配置指令
    @theresia_group.command("config")
    async def config(self, event: AstrMessageEvent):
        """查看插件配置"""
        # 获取配置
        config = await self.context.config.get_all_config()
        
        # 格式化配置
        config_str = "当前配置:\n"
        if config.get("enabled", True):
            config_str += "- 插件状态: 已启用\n"
        else:
            config_str += "- 插件状态: 已禁用\n"
        
        schedule = config.get("schedule", {})
        config_str += f"- 定时发送: {'启用' if schedule.get('enabled', False) else '禁用'}\n"
        config_str += f"- 发送时间: {schedule.get('time', '08:00')}\n"
        config_str += f"- 发送频率: {schedule.get('frequency', 'daily')}\n"
        config_str += f"- 语音标签: {', '.join(schedule.get('voice_tags', [])) or '所有'}\n"
        
        voice = config.get("voice", {})
        config_str += f"- 语音质量: {voice.get('quality', 'high')}\n"
        
        command = config.get("command", {})
        config_str += f"- 指令前缀: {command.get('prefix', '/theresia')}\n"
        config_str += f"- 触发关键词: {', '.join(command.get('keywords', []))}\n"
        
        yield event.plain_result(config_str)
    
    # 设置配置指令
    @theresia_group.command("set")
    async def set_config(self, event: AstrMessageEvent, key: str, value: str):
        """设置插件配置项\n用法: /theresia set <config> <value>"""
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
        await self.context.config.set_config(key, value)
        
        # 更新配置缓存
        keys = key.split(".")
        config = self._config_cache
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        
        # 更新VoiceManager的配置缓存
        self.voice_manager.update_config(self._config_cache)
        
        yield event.plain_result(f"配置已更新: {key} = {value}")
        
        # 如果是定时相关配置，重启定时任务
        if key.startswith("schedule."):
            self.scheduler.update_schedule()
    
    # 发送语音指令
    @theresia_group.command("voice")
    async def send_voice(self, event: AstrMessageEvent, tag: str = ""):
        """发送随机语音，可选指定标签\n用法: /theresia voice [tag]"""
        # 获取语音文件
        voice_path = self.voice_manager.get_voice(tag)
        if not voice_path:
            yield event.plain_result("未找到匹配的语音资源")
            return
        
        # 发送语音
        yield event.chain_result([
            Record(file=voice_path)
        ])
    
    # 查看可用标签指令
    @theresia_group.command("tags")
    async def list_tags(self, event: AstrMessageEvent):
        """查看可用的语音标签"""
        tags = self.voice_manager.get_tags()
        if not tags:
            yield event.plain_result("暂无可用语音标签")
            return
        
        tags_str = "可用语音标签:\n"
        for tag in tags:
            count = self.voice_manager.get_voice_count(tag)
            tags_str += f"- {tag}: {count} 条语音\n"
        
        yield event.plain_result(tags_str)
    
    # 更新语音资源指令
    @theresia_group.command("update")
    async def update_voices(self, event: AstrMessageEvent):
        """更新语音资源索引"""
        yield event.plain_result("正在更新语音资源...")
        
        # 更新语音资源
        self.voice_manager.update_voices()
        
        count = self.voice_manager.get_voice_count()
        yield event.plain_result(f"语音资源更新完成，共 {count} 条语音")
    
    # 帮助指令
    @theresia_group.command("help")
    async def help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_str = "特雷西娅语音插件命令:\n"
        help_str += "/theresia enable - 启用插件\n"
        help_str += "/theresia disable - 禁用插件\n"
        help_str += "/theresia config - 查看配置\n"
        help_str += "/theresia set <config> <value> - 设置配置项\n"
        help_str += "/theresia voice [tag] - 发送随机语音\n"
        help_str += "/theresia tags - 查看可用标签\n"
        help_str += "/theresia update - 更新语音资源\n"
        help_str += "/theresia help - 显示帮助信息\n"
        
        yield event.plain_result(help_str)
    
    # 监听所有消息，检查关键词触发
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def handle_message(self, event: AstrMessageEvent):
        """处理收到的消息，检查关键词触发"""
        # 使用缓存的配置
        config = self._config_cache
        
        # 检查插件是否启用
        if not config.get("enabled", True):
            return
        
        # 获取消息内容
        msg_content = event.message_str.strip()
        if not msg_content:
            return
        
        # 检查是否为命令，跳过处理
        prefix = config.get("command", {}).get("prefix", "/theresia")
        if msg_content.startswith(prefix):
            return
        
        # 检查是否包含关键词
        keywords = config.get("command", {}).get("keywords", ["特雷西娅", "特蕾西娅", "Theresia"])
        for keyword in keywords:
            if keyword in msg_content:
                # 发送随机语音
                voice_path = self.voice_manager.get_voice()
                if voice_path:
                    yield event.chain_result([
                        Record(file=voice_path)
                    ])
                break
