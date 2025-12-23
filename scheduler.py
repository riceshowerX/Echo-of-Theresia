import asyncio
import re
from typing import List, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class VoiceScheduler:
    def __init__(self, plugin, voice_manager):
        self.plugin = plugin
        self.voice_manager = voice_manager
        self.config_lock = asyncio.Lock()  # 确保配置操作线程安全
        self.task = None  # 定时任务句柄
        self._validate_schedule_config()  # 初始化时验证配置
        self._start_scheduler()  # 启动定时任务

    def _validate_schedule_config(self) -> None:
        """验证并修复定时任务配置"""
        # 时间格式校验（HH:MM）
        time_str = self.plugin.config.get("schedule.time", "08:00")
        if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', time_str):
            logger.warning(f"无效的时间格式 '{time_str}'，已重置为默认值 '08:00'")
            self.plugin.config["schedule.time"] = "08:00"

        # 频率合法性校验
        valid_frequencies = ["daily", "weekly", "hourly"]
        freq = self.plugin.config.get("schedule.frequency", "daily")
        if freq not in valid_frequencies:
            logger.warning(f"无效的频率 '{freq}'，已重置为默认值 'daily'")
            self.plugin.config["schedule.frequency"] = "daily"

        # 目标会话格式提醒（非强制，但建议规范）
        target_sessions = self.plugin.config.get("schedule.target_sessions", [])
        for session_id in target_sessions:
            if not (session_id.startswith("group_") or session_id.startswith("private_")):
                logger.warning(f"会话ID '{session_id}' 格式不规范，建议前缀为'group_'或'private_'")

    async def add_target(self, session_id: str) -> None:
        """线程安全地添加定时发送目标会话"""
        async with self.config_lock:  # 加锁防止并发修改冲突
            current: List[str] = self.plugin.config.get("schedule.target_sessions", [])
            if session_id in current:
                logger.info(f"会话 {session_id} 已在定时目标中，无需重复添加")
                return
            
            current.append(session_id)
            self.plugin.config["schedule.target_sessions"] = current
            await self.plugin.config.save_config()  # 假设save_config为异步方法
            logger.info(f"[定时目标] 成功添加会话：{session_id}")

    async def remove_target(self, session_id: str) -> None:
        """线程安全地移除定时发送目标会话"""
        async with self.config_lock:
            current: List[str] = self.plugin.config.get("schedule.target_sessions", [])
            if session_id not in current:
                logger.info(f"会话 {session_id} 不在定时目标中，无需移除")
                return
            
            current.remove(session_id)
            self.plugin.config["schedule.target_sessions"] = current
            await self.plugin.config.save_config()
            logger.info(f"[定时目标] 成功移除会话：{session_id}")

    def _get_next_run_time(self) -> datetime:
        """计算下一次定时任务的运行时间"""
        now = datetime.now()
        target_time = datetime.strptime(self.plugin.config["schedule.time"], "%H:%M")
        next_run = now.replace(
            hour=target_time.hour,
            minute=target_time.minute,
            second=0,
            microsecond=0
        )

        # 根据频率调整下次运行时间
        freq = self.plugin.config["schedule.frequency"]
        if next_run <= now:
            if freq == "daily":
                next_run += timedelta(days=1)
            elif freq == "weekly":
                next_run += timedelta(weeks=1)
            elif freq == "hourly":
                next_run += timedelta(hours=1)
        
        return next_run

    async def _scheduler_loop(self) -> None:
        """定时任务主循环"""
        while True:
            # 检查功能开关
            if not self.plugin.config.get("enabled") or not self.plugin.config.get("schedule.enabled"):
                await asyncio.sleep(60)  # 功能关闭时每分钟检查一次
                continue

            # 计算下次运行时间并等待
            next_run = self._get_next_run_time()
            sleep_seconds = (next_run - datetime.now()).total_seconds()
            logger.debug(f"下次定时发送时间：{next_run}，将等待 {sleep_seconds:.1f} 秒")
            await asyncio.sleep(sleep_seconds)

            # 执行发送任务
            await self._execute_scheduled_send()

    def _start_scheduler(self) -> None:
        """启动定时任务循环"""
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._scheduler_loop())
            logger.info("定时任务调度器已启动")

    async def _execute_scheduled_send(self) -> None:
        """执行定时发送逻辑"""
        target_sessions = self.plugin.config.get("schedule.target_sessions", [])
        if not target_sessions:
            logger.warning("定时发送目标会话为空，跳过发送")
            return

        # 获取匹配标签的语音
        voice_tags = self.plugin.config.get("schedule.voice_tags", [])
        voice = self.voice_manager.get_matched_voice(voice_tags)
        if not voice:
            logger.error("没有可用语音文件，无法执行定时发送")
            return

        # 向所有目标会话发送语音
        for session_id in target_sessions:
            try:
                await self.plugin.send_voice(session_id, voice["path"])  # 假设插件实现了发送方法
                logger.info(f"[定时发送] 已向 {session_id} 发送语音：{voice['filename']}")
            except Exception as e:
                logger.error(f"[定时发送] 向 {session_id} 发送失败：{str(e)}")