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
        
        # 宽容窗口 (秒): 错过时间点多久内允许补发 (30分钟)
        self.GRACE_PERIOD = 1800 
        
        self._last_config_signature = ""

    # ==================== 生命周期 ====================

    async def start(self):
        if self.running: return
        self.running = True
        self.task = asyncio.create_task(self._loop())
        logger.info("[Echo Scheduler v3.1] 智能调度服务已挂载 (Active Context Link)")

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        logger.info("[Echo Scheduler v3.1] 服务已卸载")
        
    async def add_target(self, session_id: str):
        """动态添加目标 (供指令调用)"""
        targets = self.plugin.config.get("schedule.target_sessions", [])
        if session_id not in targets:
            targets.append(session_id)
            self.plugin.config["schedule.target_sessions"] = targets
            self.plugin._save_config()
            
    async def remove_target(self, session_id: str):
        """动态移除目标"""
        targets = self.plugin.config.get("schedule.target_sessions", [])
        if session_id in targets:
            targets.remove(session_id)
            self.plugin.config["schedule.target_sessions"] = targets
            self.plugin._save_config()

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
                should_trigger, trigger_key, is_compensation = self._check_trigger_condition()

                if should_trigger:
                    action_type = "断点补发" if is_compensation else "定时触发"
                    logger.info(f"[定时任务] {action_type} 条件满足 (Key: {trigger_key})")
                    
                    # 执行分发
                    await self._execute_dispatch(trigger_key, is_compensation)
                    
                    # 等待一会防止重复判定
                    await asyncio.sleep(5)
                else:
                    await asyncio.sleep(5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[定时任务] 循环异常: {e}")
                await asyncio.sleep(60)

    # ==================== 触发判定逻辑 ====================

    def _check_trigger_condition(self) -> (bool, str, bool):
        freq = self.plugin.config.get("schedule.frequency", "daily").lower()
        now = datetime.datetime.now()

        # 1. 构造 Time Key
        trigger_key = self._generate_time_key(freq, now)
        if not trigger_key: return False, "", False

        # 2. 计算宽容度
        target_dt = self._get_target_datetime(freq, now)
        delta = (now - target_dt).total_seconds()

        # 3. 判定窗口
        is_compensation = False
        if 0 <= delta < 60:
            pass # 正常
        elif 60 <= delta < self.GRACE_PERIOD:
            is_compensation = True
        else:
            return False, "", False

        # 4. 检查是否已经发过
        targets = self.plugin.config.get("schedule.target_sessions", [])
        if not targets: return False, "", False
        
        needs_trigger = any(self.session_sent_keys.get(sid) != trigger_key for sid in targets)
        
        return needs_trigger, trigger_key, is_compensation

    def _generate_time_key(self, freq: str, dt: datetime.datetime) -> str:
        if freq == "daily": return dt.strftime("%Y-%m-%d")
        elif freq == "hourly": return dt.strftime("%Y-%m-%d-%H")
        elif freq == "weekly": return dt.strftime("%Y-W%W")
        return ""

    def _get_target_datetime(self, freq: str, now: datetime.datetime) -> datetime.datetime:
        time_str = self.plugin.config.get("schedule.time", "08:00")
        try:
            h, m = map(int, time_str.split(":"))
        except:
            h, m = 8, 0
        
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        
        if freq == "hourly":
            target = now.replace(minute=m, second=0, microsecond=0)
            if now.minute < m:
                target -= datetime.timedelta(hours=1)
        
        return target

    # ==================== 分发执行 (智能上下文版) ====================

    async def _execute_dispatch(self, trigger_key: str, is_compensation: bool):
        targets = self.plugin.config.get("schedule.target_sessions", [])
        config_tags = self.plugin.config.get("schedule.voice_tags", [])
        
        dispatch_list = list(targets)
        random.shuffle(dispatch_list)

        logger.info(f"[调度器] 开始分发，目标数: {len(dispatch_list)}，模式: {'补偿' if is_compensation else '实时'}")

        for i, session_id in enumerate(dispatch_list):
            if self.session_sent_keys.get(session_id) == trigger_key:
                continue

            # 1. 确定上下文标签
            final_tag = self._determine_context_tag(config_tags)

            # 2. 获取语音
            rel_path = self.voice_manager.get_voice(final_tag)
            
            if rel_path:
                sent = await self._do_send(session_id, rel_path)
                if sent:
                    self.session_sent_keys[session_id] = trigger_key
                    
                    # === 3. 智能上下文注入 (v3.1 新增) ===
                    # 主动发送后，告诉情感引擎和主插件：“我现在处于这个情绪状态”
                    # 这样如果用户回复，会接上这个状态
                    self._inject_context(session_id, final_tag)
            
            # 4. 时间抖动
            if i < len(dispatch_list) - 1:
                jitter = random.uniform(0.5, 1.5) if is_compensation else random.uniform(2.0, 8.0)
                await asyncio.sleep(jitter)

    def _determine_context_tag(self, config_tags: List[str]) -> Optional[str]:
        if config_tags: return random.choice(config_tags)
        
        # 智能时间段判定 (Sync with Sentiment Engine)
        h = datetime.datetime.now().hour
        if 5 <= h < 10: return "morning"
        elif 11 <= h < 14: return "rest" # 午休
        elif 14 <= h < 18: return "work" # 下午工作
        elif 22 <= h or h < 4: return "sanity" # 晚安
        
        return "theresia" # 默认

    def _inject_context(self, session_id: str, tag: str):
        """注入上下文状态，让插件'记住'这次主动发言"""
        try:
            # 1. 更新主插件的 Session 状态 (防止用户秒回时触发 CD)
            if hasattr(self.plugin, "_update_session_state"):
                updates = {
                    "last_trigger": time.time(), # 视为一次触发
                    "last_tag": tag,
                    # 如果是特定情绪，设置为心情惯性
                    "mood_tag": tag if tag in ["morning", "sanity"] else None,
                    "mood_expiry": time.time() + 300 # 5分钟惯性
                }
                self.plugin._update_session_state(session_id, updates)
            
            # 2. 更新情感引擎的记忆 (Context Memory)
            # 构造一个假的结果注入进去
            if hasattr(self.plugin, "analyzer"):
                # 模拟 AnalysisResult
                from .sentiment_analyzer import AnalysisResult
                fake_res = AnalysisResult(
                    tag=tag, score=6.0, priority=1, confidence=1.0, 
                    intensity="moderate", details={}, mixed_emotions=[]
                )
                self.plugin.analyzer._update_context(session_id, fake_res)
                
        except Exception as e:
            logger.warning(f"[调度器] 上下文注入失败: {e}")

    # ==================== 底层发送 ====================

    async def _do_send(self, session_id: str, rel_path: str) -> bool:
        abs_path = (self.voice_manager.base_dir / rel_path).resolve()
        if not abs_path.exists(): return False

        try:
            # 兼容不同版本的 Astrbot 接口
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
            return True
        except Exception as e:
            logger.warning(f"[调度器] 发送失败 ({session_id}): {e}")
            return False

    # ==================== 辅助方法 ====================

    def _config_changed(self) -> bool:
        cfg = self.plugin.config
        # 签名包含 target_sessions，支持动态添加目标
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