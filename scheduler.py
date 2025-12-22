# -*- coding: utf-8 -*-
"""
定时任务管理模块
"""

import asyncio
import time
import random
from typing import Optional, Dict, Any

from astrbot.api.message_components import Record
from astrbot.api import logger

class VoiceScheduler:
    """语音定时任务调度器"""
    
    def __init__(self, plugin, voice_manager):
        self.plugin = plugin
        self.voice_manager = voice_manager
        self.task = None
        self.running = False
        # 记录上次发送时间
        self.last_sent = ""
    
    def start(self) -> None:
        """启动定时任务"""
        self.running = True
        self.task = asyncio.create_task(self._scheduler_loop())
    
    def stop(self) -> None:
        """停止定时任务"""
        self.running = False
        if self.task:
            self.task.cancel()
            self.task = None
    
    async def _scheduler_loop(self) -> None:
        """定时任务循环"""
        while self.running:
            try:
                # 使用缓存的配置
                config = self.plugin._config_cache
                
                # 检查插件和定时任务是否启用
                if not config.get("enabled", True) or not config.get("schedule", {}).get("enabled", False):
                    await asyncio.sleep(60)
                    continue
                
                # 检查是否需要发送
                if self._should_send(config):
                    await self._send_scheduled_voice(config)
                
                # 等待下一次检查（每60秒检查一次）
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"定时任务执行错误: {e}")
                await asyncio.sleep(60)
    
    def _should_send(self, config: Dict[str, Any]) -> bool:
        """判断是否需要发送语音"""
        # 获取当前时间
        now = time.localtime()
        current_time = time.strftime("%H:%M", now)
        
        # 检查是否在指定时间
        schedule = config.get("schedule", {})
        scheduled_time = schedule.get("time", "08:00")
        if current_time != scheduled_time:
            return False
        
        # 检查频率
        frequency = schedule.get("frequency", "daily")
        
        current_date = time.strftime("%Y-%m-%d", now)
        
        if frequency == "daily":
            # 每天发送一次
            if self.last_sent != current_date:
                self.last_sent = current_date
                return True
        elif frequency == "weekly":
            # 每周发送一次（检查是否为同一周）
            current_week = time.strftime("%Y-W%W", now)
            if self.last_sent != current_week:
                self.last_sent = current_week
                return True
        elif frequency == "hourly":
            # 每小时发送一次
            current_hour = time.strftime("%Y-%m-%d %H", now)
            if self.last_sent != current_hour:
                self.last_sent = current_hour
                return True
        
        return False
    
    async def _send_scheduled_voice(self, config: Dict[str, Any]) -> None:
        """发送定时语音"""
        # 获取配置的语音标签
        schedule = config.get("schedule", {})
        voice_tags = schedule.get("voice_tags", [])
        
        # 随机选择一个标签（如果有多个）
        selected_tag = ""
        if voice_tags:
            selected_tag = random.choice(voice_tags)
        
        # 获取语音文件
        voice_path = self.voice_manager.get_voice(selected_tag)
        if not voice_path:
            return
        
        # 发送语音（这里需要根据AstrBot的API进行调整）
        # 由于定时任务中没有event对象，我们需要使用主动消息发送方式
        # 但当前AstrBot主动消息发送需要unified_msg_origin，暂时无法实现
        # 这里记录日志，实际使用中需要根据具体场景调整
        logger.info(f"[定时发送] 发送语音: {voice_path}")
        
        # TODO: 实现定时发送语音的主动消息发送
        # 需要获取unified_msg_origin，这通常需要从之前的消息事件中保存
    
    def update_schedule(self) -> None:
        """更新定时任务配置"""
        self.stop()
        self.start()
    
    def get_status(self) -> dict:
        """获取定时任务状态"""
        # 由于配置需要异步获取，这里返回基本状态
        return {
            "running": self.running,
            "last_sent": self.last_sent
        }
