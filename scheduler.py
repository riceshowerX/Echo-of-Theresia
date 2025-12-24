# -*- coding: utf-8 -*-
import asyncio
import datetime
import time
import random
from pathlib import Path
from typing import List, Optional, Dict

from astrbot.api import logger
from astrbot.api.message_components import Record


class VoiceScheduler:
    """
    Echo of Theresia v2.0 — 定时任务调度器（重构版）
    - 支持真正的 hourly / weekly 调度
    - 支持 once 模式严格一次
    - 支持配置热更新（秒级响应）
    - 多会话独立 last_sent_key
    - 更稳健的路径解析
    """

    def __init__(self, plugin, voice_manager):
        self.plugin = plugin
        self.voice_manager = voice_manager

        self.running = False
        self.task: Optional[asyncio.Task] = None

        # 每个 session 独立的 last_sent_key
        self.session_sent_keys: Dict[str, str] = {}

        # 用于配置热更新
        self._last_config_signature = ""

    # ==================== 生命周期 ====================

    async def start(self):
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._loop())
        logger.info("[Echo v2.0] 定时任务服务已启动")

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        logger.info("[Echo v2.0] 定时任务服务已停止")

    # ==================== 主循环 ====================

    async def _loop(self):
        logger.info("[定时任务] 进入监听循环...")

        while self.running:
            try:
                # 配置热更新检测
                if self._config_changed():
                    logger.info("[定时任务] 检测到配置变更，立即刷新调度参数")

                if not self._is_enabled():
                    await asyncio.sleep(30)
                    continue

                # 计算下一次触发时间
                wait_seconds = self._seconds_until_next_trigger()

                # 智能休眠策略
                if wait_seconds > 60:
                    await asyncio.sleep(30)
                    continue

                # 精确等待
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

                # 二次检查
                if not self.running or not self._is_enabled():
                    continue

                # 执行发送
                await self._try_send()

                # 防抖
                await asyncio.sleep(3)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[定时任务] 循环异常: {e}")
                await asyncio.sleep(60)

    # ==================== 配置检测 ====================

    def _config_changed(self) -> bool:
        """检测配置是否变化（热更新）"""
        cfg = self.plugin.config
        signature = json_signature = str({
            "enabled": cfg.get("schedule.enabled"),
            "time": cfg.get("schedule.time"),
            "frequency": cfg.get("schedule.frequency"),
            "tags": tuple(cfg.get("schedule.voice_tags", [])),
            "targets": tuple(cfg.get("schedule.target_sessions", [])),
        })

        if signature != self._last_config_signature:
            self._last_config_signature = signature
            return True
        return False

    # ==================== 启用判断 ====================

    def _is_enabled(self) -> bool:
        return (
            self.plugin.config.get("enabled", True)
            and self.plugin.config.get("schedule.enabled", False)
        )

    # ==================== 触发时间计算 ====================

    def _seconds_until_next_trigger(self) -> int:
        """根据 frequency 计算下一次触发时间"""

        freq = self.plugin.config.get("schedule.frequency", "daily").lower()
        now = datetime.datetime.now()

        # 解析时间
        time_str = self.plugin.config.get("schedule.time", "08:00")
        try:
            h, m = map(int, time_str.split(":"))
        except:
            h, m = 8, 0

        # DAILY — 每天固定时间
        if freq == "daily":
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)
            return int((target - now).total_seconds())

        # HOURLY — 每小时固定分钟
        if freq == "hourly":
            target = now.replace(minute=m, second=0, microsecond=0)
            if target <= now:
                target += datetime.timedelta(hours=1)
            return int((target - now).total_seconds())

        # WEEKLY — 每周固定时间（默认周一）
        if freq == "weekly":
            weekday = self.plugin.config.get("schedule.weekday", 1)  # 1=周一
            days_ahead = (weekday - now.isoweekday()) % 7
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            target += datetime.timedelta(days=days_ahead)
            if target <= now:
                target += datetime.timedelta(days=7)
            return int((target - now).total_seconds())

        # ONCE — 立即触发一次
        if freq == "once":
            return 0

        # 默认 daily
        return 60

    # ==================== 是否应该发送 ====================

    async def _try_send(self):
        freq = self.plugin.config.get("schedule.frequency", "daily").lower()
        targets = self.plugin.config.get("schedule.target_sessions", [])

        if not targets:
            return

        # once 模式严格一次
        if freq == "once":
            if self.plugin.config.get("schedule.once_status") == "sent":
                return
            await self._send_to_targets(targets)
            self.plugin.config["schedule.once_status"] = "sent"
            if hasattr(self.plugin.config, "save_config"):
                self.plugin.config.save_config()
            return

        # 其它模式：按 session 独立判断
        fmt = {
            "daily": "%Y-%m-%d",
            "hourly": "%Y-%m-%d %H",
            "weekly": "%Y-%W",
        }.get(freq, "%Y-%m-%d")

        current_key = time.strftime(fmt)

        for session_id in targets:
            last_key = self.session_sent_keys.get(session_id)
            if last_key == current_key:
                continue

            await self._send_to_targets([session_id])
            self.session_sent_keys[session_id] = current_key

    # ==================== 发送逻辑 ====================

    async def _send_to_targets(self, targets: List[str]):
        tags = self.plugin.config.get("schedule.voice_tags", [])
        tag = random.choice(tags) if tags else None

        rel_path = self.voice_manager.get_voice(tag)
        if not rel_path:
            logger.warning(f"[定时发送] 标签 '{tag}' 无可用语音")
            return

        # 更稳健的路径解析
        abs_path = (self.voice_manager.base_dir / rel_path).resolve()
        if not abs_path.exists():
            logger.error(f"[定时发送] 文件不存在: {abs_path}")
            return

        logger.info(f"[定时发送] 正在向 {len(targets)} 个会话推送语音...")

        success = 0
        for session_id in targets:
            try:
                # 新版接口
                if hasattr(self.plugin.context, "send_message"):
                    await self.plugin.context.send_message(
                        session_id=session_id,
                        message_chain=[Record(file=str(abs_path))]
                    )
                # 旧版接口
                elif hasattr(self.plugin.context, "message_sender"):
                    await self.plugin.context.message_sender.send_message(
                        session_id=session_id,
                        message_chain=[Record(file=str(abs_path))]
                    )
                else:
                    logger.error("[定时发送] 找不到可用的发送接口")
                    continue

                success += 1

            except Exception as e:
                logger.error(f"[定时发送] 发送给 {session_id} 失败: {e}")

        logger.info(f"[定时发送] 推送完成，成功 {success}/{len(targets)}")
