# -*- coding: utf-8 -*-
import asyncio
import datetime
import time
import random
import json
from pathlib import Path
from typing import List, Optional, Dict, Set

from astrbot.api import logger
from astrbot.api.message_components import Record

class VoiceScheduler:

    def __init__(self, plugin, voice_manager):
        self.plugin = plugin
        self.voice_manager = voice_manager

        self.running = False
        self.task: Optional[asyncio.Task] = None

        # 记录发送状态: { session_id: last_sent_key }
        self.session_sent_keys: Dict[str, str] = {}
        
        # 宽容窗口 (秒): 错过时间点多久内允许补发
        self.GRACE_PERIOD = 1800 
        
        self._last_config_signature = ""

    # ==================== 生命周期 ====================

    async def start(self):
        if self.running: return
        self.running = True
        self.task = asyncio.create_task(self._loop())
        logger.info("[Echo Scheduler v3.0] 拟人化调度服务已挂载")

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        logger.info("[Echo Scheduler v3.0] 服务已卸载")

    # ==================== 核心循环 ====================

    async def _loop(self):
        logger.info("[定时任务] 监听循环启动...")
        while self.running:
            try:
                # 1. 热更新检测
                if self._config_changed():
                    logger.info("[定时任务] 配置热重载完成")

                if not self._is_enabled():
                    await asyncio.sleep(30)
                    continue

                # 2. 计算触发状态
                # 返回: (是否触发, 触发类型key, 是否是补发)
                should_trigger, trigger_key, is_compensation = self._check_trigger_condition()

                if should_trigger:
                    action_type = "断点补发" if is_compensation else "定时触发"
                    logger.info(f"[定时任务] {action_type} 条件满足 (Key: {trigger_key})")
                    
                    # 执行分发
                    await self._execute_dispatch(trigger_key, is_compensation)
                    
                    # 等待一会防止重复判定
                    await asyncio.sleep(5)
                else:
                    # 没到时间，智能休眠
                    # 这里不再 sleep(distance)，因为要保持一定的响应频率以检测配置变更
                    await asyncio.sleep(5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[定时任务] 循环异常: {e}")
                await asyncio.sleep(60)

    # ==================== 触发判定逻辑 ====================

    def _check_trigger_condition(self) -> (bool, str, bool):
        """
        判断当前是否应该触发。
        包含算法：断点补偿检测
        """
        freq = self.plugin.config.get("schedule.frequency", "daily").lower()
        now = datetime.datetime.now()

        # 1. 构造当前的 Time Key
        trigger_key = self._generate_time_key(freq, now)
        if not trigger_key:
            return False, "", False

        # 2. 解析目标时间 (用于计算宽容度)
        target_dt = self._get_target_datetime(freq, now)
        delta = (now - target_dt).total_seconds()

        # 3. 判定窗口
        # 情况A: 正好在时间点附近 (0 <= delta < 60) -> 正常触发
        # 情况B: 错过了时间点，但在宽容期内 (60 <= delta < GRACE_PERIOD) -> 补偿触发
        # 情况C: 还没到 (<0) 或 错过太久 (>GRACE_PERIOD) -> 不触发
        
        is_compensation = False
        if 0 <= delta < 60:
            pass # 正常
        elif 60 <= delta < self.GRACE_PERIOD:
            is_compensation = True
        else:
            return False, "", False

        # 4. 检查是否已经发过 (全局检查，具体每个 Session 还会复查)
        # 这里只要有一个目标没发过这个 Key，就应该触发流程
        targets = self.plugin.config.get("schedule.target_sessions", [])
        if not targets:
            return False, "", False
        
        # 只要有一个 session 的 last_key 不等于 current_key，就说明需要触发
        needs_trigger = any(self.session_sent_keys.get(sid) != trigger_key for sid in targets)
        
        return needs_trigger, trigger_key, is_compensation

    def _generate_time_key(self, freq: str, dt: datetime.datetime) -> str:
        """生成用于去重的唯一时间键"""
        if freq == "daily":
            return dt.strftime("%Y-%m-%d") # 每天一个Key
        elif freq == "hourly":
            return dt.strftime("%Y-%m-%d-%H") # 每小时一个Key
        elif freq == "weekly":
            return dt.strftime("%Y-W%W") # 每周一个Key
        elif freq == "once":
            return "ONCE_TASK"
        return ""

    def _get_target_datetime(self, freq: str, now: datetime.datetime) -> datetime.datetime:
        """反推当前的理论触发时间"""
        time_str = self.plugin.config.get("schedule.time", "08:00")
        try:
            h, m = map(int, time_str.split(":"))
        except:
            h, m = 8, 0
        
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        
        if freq == "hourly":
            target = now.replace(minute=m, second=0, microsecond=0)
            # 如果当前分钟 < 目标分钟，说明目标是上一个小时
            if now.minute < m:
                target -= datetime.timedelta(hours=1)
        
        elif freq == "weekly":
            weekday = self.plugin.config.get("schedule.weekday", 1)
            # 简单处理：仅计算当天的目标时间，周几的判断交给 Key 匹配
            # 这里逻辑可以简化，因为 Key 匹配才是硬道理
            pass 

        return target

    # ==================== 分发执行 (Polymorphic Dispatch) ====================

    async def _execute_dispatch(self, trigger_key: str, is_compensation: bool):
        targets = self.plugin.config.get("schedule.target_sessions", [])
        config_tags = self.plugin.config.get("schedule.voice_tags", [])
        
        # 乱序发送，模拟真人操作
        # list() copy 一份防止修改原配置
        dispatch_list = list(targets)
        random.shuffle(dispatch_list)

        logger.info(f"[调度器] 开始分发，目标数: {len(dispatch_list)}，模式: {'补偿' if is_compensation else '实时'}")

        for i, session_id in enumerate(dispatch_list):
            # 1. 幂等性检查 (Double Check)
            if self.session_sent_keys.get(session_id) == trigger_key:
                continue

            # 2. 上下文注入 (Context Injection)
            final_tag = self._determine_context_tag(config_tags)

            # 3. 多态获取 (Polymorphic Fetch)
            # 每个群独立调用 VoiceManager，配合 v3.0 的去重算法，每个群听到的可能不同
            rel_path = self.voice_manager.get_voice(final_tag)
            
            if rel_path:
                await self._do_send(session_id, rel_path)
                self.session_sent_keys[session_id] = trigger_key
            
            # 4. 时间抖动 (Temporal Jitter)
            # 如果是补偿模式，为了尽快发完，抖动小一点；正常模式抖动大一点
            if i < len(dispatch_list) - 1:
                jitter = random.uniform(0.5, 1.5) if is_compensation else random.uniform(2.0, 8.0)
                await asyncio.sleep(jitter)

    def _determine_context_tag(self, config_tags: List[str]) -> Optional[str]:
        """
        根据当前时间注入上下文标签。
        如果配置了特定标签，优先用配置的；否则根据时间段智能选择。
        """
        if config_tags:
            return random.choice(config_tags)
        
        # 智能时间段判定
        h = datetime.datetime.now().hour
        if 5 <= h < 10:
            return "morning"
        elif 11 <= h < 14:
            return "lunch" # 如果你的库里有
        elif 22 <= h or h < 4:
            return "sanity" # 晚安/休息
        
        return None # 随机

    # ==================== 底层发送 ====================

    async def _do_send(self, session_id: str, rel_path: str):
        abs_path = (self.voice_manager.base_dir / rel_path).resolve()
        if not abs_path.exists():
            return

        try:
            if hasattr(self.plugin.context, "send_message"):
                await self.plugin.context.send_message(
                    session_id=session_id,
                    message_chain=[Record(file=str(abs_path))]
                )
            elif hasattr(self.plugin.context, "message_sender"):
                await self.plugin.context.message_sender.send_message(
                    session_id=session_id,
                    message_chain=[Record(file=str(abs_path))]
                )
        except Exception as e:
            logger.warning(f"[调度器] 发送失败 ({session_id}): {e}")

    # ==================== 辅助方法 ====================

    def _config_changed(self) -> bool:
        cfg = self.plugin.config
        signature = str({
            "en": cfg.get("schedule.enabled"),
            "tm": cfg.get("schedule.time"),
            "fr": cfg.get("schedule.frequency"),
            "tg": tuple(cfg.get("schedule.voice_tags", [])),
            "tr": tuple(cfg.get("schedule.target_sessions", [])),
        })
        if signature != self._last_config_signature:
            self._last_config_signature = signature
            return True
        return False

    def _is_enabled(self) -> bool:
        return (self.plugin.config.get("enabled", True) and 
                self.plugin.config.get("schedule.enabled", False))