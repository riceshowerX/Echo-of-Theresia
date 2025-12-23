# -*- coding: utf-8 -*-
import asyncio
import time
import random
import datetime
from typing import List, Optional
from pathlib import Path

from astrbot.api import logger
from astrbot.api.message_components import Record

class VoiceScheduler:
    FREQUENCY_MAP = {
        "daily": "%Y-%m-%d",
        "weekly": "%Y-%W", 
        "hourly": "%Y-%m-%d %H",
        "once": "once_sent",
    }

    def __init__(self, plugin, voice_manager):
        self.plugin = plugin
        self.voice_manager = voice_manager
        self.task: Optional[asyncio.Task] = None
        self.running = False
        self.last_sent_key: str = ""
        # 用于配置变更检测
        self._last_config_signature = "" 

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._scheduler_loop())
        logger.info("[Echo of Theresia] 定时任务服务已启动")

    async def stop(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        logger.info("[Echo of Theresia] 定时任务服务已停止")

    async def _scheduler_loop(self) -> None:
        """
        主循环：采用分段休眠机制，支持配置热更新
        """
        logger.info("[定时任务] 进入监听循环...")
        
        while self.running:
            try:
                # 1. 基础检查
                if not self._is_schedule_enabled():
                    await asyncio.sleep(30) # 没开功能就每30秒看一眼
                    continue

                # 2. 计算距离下次触发的时间
                wait_seconds = self._seconds_until_next_trigger()

                # 3. 智能休眠策略
                # 如果时间还早 (>60秒)，我们只睡 30 秒，然后醒来检查配置有没有变
                # 如果时间快到了 (<=60秒)，我们睡完剩余时间，准备触发
                if wait_seconds > 60:
                    await asyncio.sleep(30)
                    continue
                
                # 4. 精确等待触发时刻
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

                # 5. 二次检查（防止sleep期间被禁用或时间未到）
                if not self.running or not self._is_schedule_enabled():
                    continue

                # 6. 尝试发送
                if await self._should_send_now():
                    await self._send_voice()
                    # 发送完休息一小会儿防止逻辑抖动
                    await asyncio.sleep(5) 

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[定时任务] 循环发生异常: {e}")
                await asyncio.sleep(60) # 出错后冷却

    def _is_schedule_enabled(self) -> bool:
        return (
            self.plugin.config.get("enabled", True) and
            self.plugin.config.get("schedule.enabled", False)
        )

    def _seconds_until_next_trigger(self) -> int:
        """计算距离下次触发还有多少秒"""
        now = datetime.datetime.now()
        target_time_str = self.plugin.config.get("schedule.time", "08:00")
        
        try:
            h_str, m_str = target_time_str.split(":")
            target_hour, target_minute = int(h_str), int(m_str)
        except ValueError:
            # 容错处理
            target_hour, target_minute = 8, 0

        target_today = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

        # 如果今天的目标时间已过，计算到明天的距离
        if target_today <= now:
            target_today += datetime.timedelta(days=1)

        delta = (target_today - now).total_seconds()
        return max(0, int(delta))

    async def _should_send_now(self) -> bool:
        """检查是否满足发送频率"""
        freq = self.plugin.config.get("schedule.frequency", "daily").lower()
        
        # 处理 once
        if freq == "once":
            # 如果配置里的标记还没被设为 sent
            if self.plugin.config.get("schedule.once_status") == "sent":
                return False
            return True

        # 处理常规频率
        fmt = self.FREQUENCY_MAP.get(freq, self.FREQUENCY_MAP["daily"])
        current_key = time.strftime(fmt)

        if current_key == self.last_sent_key:
            return False

        self.last_sent_key = current_key
        return True

    async def _send_voice(self) -> None:
        """执行发送逻辑"""
        targets: List[str] = self.plugin.config.get("schedule.target_sessions", [])
        if not targets:
            return

        tags: List[str] = self.plugin.config.get("schedule.voice_tags", [])
        # 如果没配置标签，默认用全部
        tag = random.choice(tags) if tags else None
        
        rel_path = self.voice_manager.get_voice(tag)
        if not rel_path:
            logger.warning(f"[定时发送] 标签 '{tag}' 无可用语音")
            return

        # 路径转换
        if hasattr(self.plugin, "_rel_to_abs"):
            abs_path = self.plugin._rel_to_abs(rel_path)
        else:
            # 兼容性后备
            abs_path = (Path(self.plugin.plugin_root) / rel_path).resolve()

        if not abs_path.exists():
            return

        logger.info(f"[定时发送] 开始向 {len(targets)} 个会话推送语音")
        
        count = 0
        for session_id in targets:
            try:
                # 核心发送逻辑：尝试使用 unified interface
                # 1. 尝试直接通过 context 发送 (AstrBot 新版)
                if hasattr(self.plugin.context, "send_message"):
                    await self.plugin.context.send_message(
                        session_id=session_id,
                        message_chain=[Record(file=str(abs_path))]
                    )
                    count += 1
                    
                # 2. 回退：如果找不到通用接口，尝试获取 message_sender (旧版/特定实现)
                elif hasattr(self.plugin.context, "message_sender"):
                    await self.plugin.context.message_sender.send_message(
                        session_id=session_id,
                        message_chain=[Record(file=str(abs_path))]
                    )
                    count += 1
                else:
                    logger.error("[定时发送] 无法找到可用的发送接口 (context.send_message)")
                    break
                    
            except Exception as e:
                logger.error(f"[定时发送] 发送给 {session_id} 失败: {e}")

        logger.info(f"[定时发送] 推送完成，成功: {count}")

        # 如果是 once 模式，更新状态写入配置
        if self.plugin.config.get("schedule.frequency") == "once":
            self.plugin.config["schedule.once_status"] = "sent"
            # 尝试保存
            if hasattr(self.plugin.config, "save_config"):
                self.plugin.config.save_config()

    # ================= 配置管理 =================
    
    async def add_target(self, session_id: str) -> None:
        current = self.plugin.config.get("schedule.target_sessions", [])
        if session_id not in current:
            current.append(session_id)
            self.plugin.config["schedule.target_sessions"] = current
            if hasattr(self.plugin.config, "save_config"):
                self.plugin.config.save_config()
            logger.info(f"[定时目标] 已添加会话: {session_id}")

    async def remove_target(self, session_id: str) -> None:
        current = self.plugin.config.get("schedule.target_sessions", [])
        if session_id in current:
            current.remove(session_id)
            self.plugin.config["schedule.target_sessions"] = current
            if hasattr(self.plugin.config, "save_config"):
                self.plugin.config.save_config()
            logger.info(f"[定时目标] 已移除会话: {session_id}")