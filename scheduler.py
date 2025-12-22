# -*- coding: utf-8 -*-
"""
定时任务模块 - 使用 self.plugin.config 访问配置
"""

import asyncio
import time
import random
from typing import List

from astrbot.api import logger
from astrbot.api.message_components import Record

class VoiceScheduler:
    def __init__(self, plugin, voice_manager):
        self.plugin = plugin
        self.voice_manager = voice_manager
        self.task: asyncio.Task | None = None
        self.running = False
        self.last_sent_key = ""

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._loop())
        logger.info("[Echo of Theresia] 定时任务已启动")

    async def stop(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            self.task = None
        logger.info("[Echo of Theresia] 定时任务已停止")

    async def _loop(self) -> None:
        while self.running:
            try:
                enabled = self.plugin.config.get("enabled", True)
                sched_enabled = self.plugin.config.get("schedule.enabled", False)
                if not (enabled and sched_enabled):
                    await asyncio.sleep(60)
                    continue

                if await self._should_send():
                    await self._send_voice()

                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[定时任务] 错误: {e}")
                await asyncio.sleep(60)

    async def _should_send(self) -> bool:
        now = time.localtime()
        current_time = time.strftime("%H:%M", now)
        target_time = self.plugin.config.get("schedule.time", "08:00")
        if current_time != target_time:
            return False

        freq = self.plugin.config.get("schedule.frequency", "daily")
        if freq == "daily":
            key = time.strftime("%Y-%m-%d", now)
        elif freq == "weekly":
            key = time.strftime("%Y-%W%W", now)
        elif freq == "hourly":
            key = time.strftime("%Y-%m-%d %H", now)
        else:
            key = time.strftime("%Y-%m-%d", now)

        if self.last_sent_key == key:
            return False
        self.last_sent_key = key
        return True

    async def _send_voice(self) -> None:
        targets: List[str] = self.plugin.config.get("schedule.target_sessions", [])
        if not targets:
            logger.info("[定时发送] 无目标会话，跳过")
            return

        tags: List[str] = self.plugin.config.get("schedule.voice_tags", [])
        tag = random.choice(tags) if tags else None

        path = self.voice_manager.get_voice(tag)
        if not path:
            logger.info(f"[定时发送] 无匹配语音 (tag={tag})")
            return

        for session_id in targets:
            try:
                await self.plugin.context.message_sender.send_message(
                    session_id=session_id,
                    message_chain=[Record(file=path)]
                )
                logger.info(f"[定时发送] 已发送至 {session_id}: {path}")
            except Exception as e:
                logger.error(f"[定时发送] 失败 {session_id}: {e}")

    async def add_target(self, session_id: str):
        current: List[str] = self.plugin.config.get("schedule.target_sessions", [])
        if session_id not in current:
            current.append(session_id)
            self.plugin.config["schedule.target_sessions"] = current
            self.plugin.config.save_config()

    async def remove_target(self, session_id: str):
        current: List[str] = self.plugin.config.get("schedule.target_sessions", [])
        if session_id in current:
            current.remove(session_id)
            self.plugin.config["schedule.target_sessions"] = current
            self.plugin.config.save_config()