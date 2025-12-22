# -*- coding: utf-8 -*-
"""
定时任务管理模块
"""

import asyncio
import time
from typing import Optional

class VoiceScheduler:
    """语音定时任务调度器"""
    
    def __init__(self, plugin, config, voice_manager):
        self.plugin = plugin
        self.config = config
        self.voice_manager = voice_manager
        self.task = None
        self.running = False
    
    def start(self) -> None:
        """启动定时任务"""
        if not self.config.get("enabled"):
            return
        
        if self.config.get("schedule.enabled"):
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
                # 检查是否需要发送
                if self._should_send():
                    await self._send_scheduled_voice()
                
                # 等待下一次检查（每60秒检查一次）
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"定时任务执行错误: {e}")
                await asyncio.sleep(60)
    
    def _should_send(self) -> bool:
        """判断是否需要发送语音"""
        if not self.config.get("schedule.enabled"):
            return False
        
        # 获取当前时间
        now = time.localtime()
        current_time = time.strftime("%H:%M", now)
        
        # 检查是否在指定时间
        scheduled_time = self.config.get("schedule.time", "08:00")
        if current_time != scheduled_time:
            return False
        
        # 检查频率
        frequency = self.config.get("schedule.frequency", "daily")
        
        # 记录上次发送时间
        if not hasattr(self, "last_sent"):
            self.last_sent = ""
        
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
    
    async def _send_scheduled_voice(self) -> None:
        """发送定时语音"""
        # 获取配置的语音标签
        voice_tags = self.config.get("schedule.voice_tags", [])
        
        # 随机选择一个标签（如果有多个）
        selected_tag = ""
        if voice_tags:
            import random
            selected_tag = random.choice(voice_tags)
        
        # 获取语音文件
        voice_path = self.voice_manager.get_voice(selected_tag)
        if not voice_path:
            return
        
        # 发送语音（这里需要根据AstrBot的API进行调整）
        # 示例：await self.plugin.send_voice(voice_path)
        print(f"发送定时语音: {voice_path}")
    
    def update_schedule(self) -> None:
        """更新定时任务配置"""
        self.stop()
        self.start()
    
    def get_status(self) -> dict:
        """获取定时任务状态"""
        return {
            "running": self.running,
            "enabled": self.config.get("schedule.enabled"),
            "time": self.config.get("schedule.time"),
            "frequency": self.config.get("schedule.frequency"),
            "voice_tags": self.config.get("schedule.voice_tags")
        }
