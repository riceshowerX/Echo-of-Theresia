# -*- coding: utf-8 -*-
"""
定时任务模块 - 优化版
改进点：
- 精确计算下次触发时间，避免每分钟轮询
- 修复 weekly key bug
- 支持配置变更自动生效
- 更优雅的频率控制和日志
- 更好的类型提示与默认配置处理
"""

import asyncio
import time
import random
import datetime
from typing import List, Optional

from astrbot.api import logger
from astrbot.api.message_components import Record


class VoiceScheduler:
    FREQUENCY_MAP = {
        "daily": "%Y-%m-%d",
        "weekly": "%Y-%W",      # 修正：周数格式为 %W（0-53）
        "hourly": "%Y-%m-%d %H",
        "once": None,           # 特殊：只发送一次（用于测试）
    }

    def __init__(self, plugin, voice_manager):
        self.plugin = plugin
        self.voice_manager = voice_manager
        self.task: Optional[asyncio.Task] = None
        self.running = False
        self.last_sent_key: str = ""  # 上次发送的频率 key

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._scheduler_loop())
        logger.info("[Echo of Theresia] 定时任务已启动")

    async def stop(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            self.task = None
        logger.info("[Echo of Theresia] 定时任务已停止")

    async def _scheduler_loop(self) -> None:
        """主循环：精确等待下次触发时间"""
        while self.running:
            try:
                if not self._is_schedule_enabled():
                    await asyncio.sleep(60)
                    continue

                sleep_seconds = self._seconds_until_next_trigger()
                if sleep_seconds > 0:
                    logger.debug(f"[定时任务] 等待 {sleep_seconds} 秒后检查触发")
                    await asyncio.sleep(sleep_seconds)

                if self.running and await self._should_send_now():
                    await self._send_voice()
                    # 发送后立即重新计算下次时间（避免连续触发）
                    continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[定时任务] 意外错误: {e}")
                await asyncio.sleep(60)

    def _is_schedule_enabled(self) -> bool:
        """检查插件和定时功能是否启用"""
        return (
            self.plugin.config.get("enabled", True) and
            self.plugin.config.get("schedule.enabled", False)
        )

    def _seconds_until_next_trigger(self) -> int:
        """计算距离下一次目标时间还有多少秒（返回 >=0）"""
        now = datetime.datetime.now()
        target_time_str = self.plugin.config.get("schedule.time", "08:00")
        try:
            target_hour, target_minute = map(int, target_time_str.split(":"))
        except ValueError:
            logger.warning(f"[定时任务] 时间格式错误: {target_time_str}，使用默认 08:00")
            target_hour, target_minute = 8, 0

        # 构造今天的目標時間
        target_today = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

        # 如果今天的目标时间已过，则推到明天
        if target_today <= now:
            target_today += datetime.timedelta(days=1)

        return int((target_today - now).total_seconds())

    async def _should_send_now(self) -> bool:
        """判断当前是否满足发送频率条件"""
        freq = self.plugin.config.get("schedule.frequency", "daily").lower()

        if freq == "once":
            if self.last_sent_key:  # 已发送过
                return False
            self.last_sent_key = "sent"
            return True

        fmt = self.FREQUENCY_MAP.get(freq)
        if not fmt:
            logger.warning(f"[定时任务] 不支持的频率: {freq}，回退到 daily")
            fmt = self.FREQUENCY_MAP["daily"]

        current_key = time.strftime(fmt)
        if current_key == self.last_sent_key:
            return False

        self.last_sent_key = current_key
        return True

    async def _send_voice(self) -> None:
        targets: List[str] = self.plugin.config.get("schedule.target_sessions", [])
        if not targets:
            logger.info("[定时发送] 无目标会话，跳过发送")
            return

        tags: List[str] = self.plugin.config.get("schedule.voice_tags", [])
        if not tags:
            logger.info("[定时发送] 未配置语音标签，跳过发送")
            return

        tag = random.choice(tags)
        rel_path = self.voice_manager.get_voice(tag)
        if not rel_path:
            logger.info(f"[定时发送] 未找到标签 '{tag}' 的语音，跳过")
            return

        abs_path = self.plugin._rel_to_abs(rel_path)  # 使用主插件的路径转换方法

        success_count = 0
        for session_id in targets:
            try:
                await self.plugin.context.message_sender.send_message(
                    session_id=session_id,
                    message_chain=[Record(file=str(abs_path))]
                )
                logger.info(f"[定时发送] 成功发送至 {session_id}: {rel_path} (tag: {tag})")
                success_count += 1
            except Exception as e:
                logger.error(f"[定时发送] 发送失败 {session_id}: {e}")

        logger.info(f"[定时发送] 本次完成：成功 {success_count}/{len(targets)} 个会话")

    # 目标会话管理（保持不变，但可加重复检查）
    async def add_target(self, session_id: str) -> None:
        current: List[str] = self.plugin.config.get("schedule.target_sessions", [])
        if session_id not in current:
            current.append(session_id)
            self.plugin.config["schedule.target_sessions"] = current
            self.plugin.config.save_config()
            logger.info(f"[定时目标] 添加 {session_id}")

    async def remove_target(self, session_id: str) -> None:
        current: List[str] = self.plugin.config.get("schedule.target_sessions", [])
        if session_id in current:
            current.remove(session_id)
            self.plugin.config["schedule.target_sessions"] = current
            self.plugin.config.save_config()
            logger.info(f"[定时目标] 移除 {session_id}")