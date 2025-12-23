# -*- coding: utf-8 -*-
import asyncio
import datetime
import time
import random
import re
import json
from pathlib import Path

# AstrBot API Imports
from astrbot.api.all import *
from astrbot.api.star import Star, Context, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.message_components import Record
from astrbot.api import logger

# Local Imports
from .voice_manager import VoiceManager
from .scheduler import VoiceScheduler

@register(
    "echo_of_theresia",
    "riceshowerX",
    "1.6.0",
    "明日方舟特雷西娅角色语音插件 (Deep Probe)"
)
class TheresiaVoicePlugin(Star):
    
    # ================= 情感定义 =================
    # (标签, 基础权重)
    EMOTION_DEFINITIONS = {
        "晚安": ("sanity", 10),
        "早安": ("morning", 9),
        "救命": ("comfort", 8),
        "痛苦": ("dont_cry", 8),
        "难过": ("comfort", 7),
        "害怕": ("comfort", 7),
        "累":   ("sanity", 6),
        "休息": ("sanity", 6),
        "失败": ("fail", 6),
        "孤独": ("company", 6),
        "抱抱": ("trust", 5),
        "戳":   ("poke", 4),
    }

    # 程度副词
    INTENSIFIERS = ["好", "太", "真", "非常", "超级", "死", "特别"]
    # 否定词
    NEGATIONS = ["不", "没", "别", "勿", "无"]

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}

        # ================= 配置初始化 =================
        self.config.setdefault("enabled", True)
        self.config.setdefault("command.keywords", ["特雷西娅", "特蕾西娅", "Theresia"])
        self.config.setdefault("command.prefix", "/theresia")
        self.config.setdefault("voice.default_tag", "")
        
        # 智能特性开关
        self.config.setdefault("features.sanity_mode", True)
        self.config.setdefault("features.emotion_detect", True)
        self.config.setdefault("features.smart_negation", True)
        self.config.setdefault("features.nudge_response", True)

        # 定时任务配置
        self.config.setdefault("schedule.enabled", False)
        self.config.setdefault("schedule.time", "08:00")
        self.config.setdefault("schedule.frequency", "daily")
        self.config.setdefault("schedule.voice_tags", [])
        self.config.setdefault("schedule.target_sessions", [])

        # 运行时状态
        self.last_trigger_time = 0
        self.cooldown_seconds = 10 

        self.plugin_root = Path(__file__).parent.resolve()
        
        self.voice_manager = VoiceManager(self)
        self.voice_manager.load_voices() 
        
        self.scheduler = VoiceScheduler(self, self.voice_manager)

        if self.config.get("enabled", True):
            asyncio.create_task(self.scheduler.start())
            logger.warning("[Echo of Theresia] 调试探测模式已启动，请注意查看控制台日志")

    async def on_unload(self):
        await self.scheduler.stop()
        logger.info("[Echo of Theresia] 插件已卸载")

    # ================= 辅助方法 =================

    def _rel_to_abs(self, rel_path: str | None) -> Path | None:
        if not rel_path:
            return None
        return (self.plugin_root / rel_path).resolve()

    def _save_config(self):
        """尝试保存配置"""
        try:
            if hasattr(self.config, "save_config"):
                self.config.save_config()
        except Exception:
            pass

    async def safe_yield_voice(self, event: AstrMessageEvent, rel_path: str | None):
        """安全发送语音的通用方法"""
        if not rel_path:
            # 仅在指令调用时提示
            if event.message_str and event.message_str.startswith("/"):
                yield event.plain_result("特雷西娅似乎没有找到这段语音呢~")
            return

        abs_path = self._rel_to_abs(rel_path)
        if not abs_path or not abs_path.exists():
            logger.warning(f"[Echo of Theresia] 文件缺失: {rel_path}")
            return

        logger.info(f"[Echo of Theresia] 发送语音: {abs_path.name}")

        try:
            chain = [Record(file=str(abs_path))]
            yield event.chain_result(chain)
        except Exception as e:
            logger.error(f"[Echo of Theresia] 发送失败: {e}")

    # ==================== 智能情感分析引擎 ====================
    
    def analyze_sentiment(self, text: str) -> str | None:
        text_lower = text.lower()
        best_tag = None
        max_score = 0

        for keyword, (tag, base_score) in self.EMOTION_DEFINITIONS.items():
            if keyword not in text_lower:
                continue

            current_score = base_score
            kw_index = text_lower.find(keyword)

            # 否定检测
            if self.config.get("features.smart_negation", True):
                is_negated = False
                window_start = max(0, kw_index - 3)
                prefix_window = text_lower[window_start:kw_index]
                for neg in self.NEGATIONS:
                    if neg in prefix_window:
                        is_negated = True
                        break
                if is_negated:
                    continue 

            # 程度检测
            for intensifier in self.INTENSIFIERS:
                if intensifier in text_lower:
                    current_score += 5
                    break

            if current_score > max_score:
                max_score = current_score
                best_tag = tag

        return best_tag

    # ==================== 全频段扫描入口 ====================
    
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def keyword_trigger(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True):
            return

        # ---------------------------------------------------------
        # 【调试探针】 打印所有可能的信息，寻找 Poke 的踪迹
        # ---------------------------------------------------------
        text = (event.message_str or "").strip()
        
        # 只有在文本为空，或者看起来像 Poke 的时候才打印，防止刷屏
        debug_mode = not text or "poke" in text.lower() or "戳" in text or "[" in text
        
        if debug_mode:
            logger.warning("="*30 + " DEBUG PROBE START " + "="*30)
            logger.warning(f"[DEBUG PROBE] Message String: '{text}'")
            
            # 探测 1: Raw Event
            raw = getattr(event, 'raw_event', None) or getattr(event, 'original_event', None)
            if raw:
                # 简化打印，防止太长
                sub_type = raw.get('sub_type', 'N/A')
                notice_type = raw.get('notice_type', 'N/A')
                post_type = raw.get('post_type', 'N/A')
                logger.warning(f"[DEBUG PROBE] Raw Event Keys: post_type={post_type}, notice_type={notice_type}, sub_type={sub_type}")
            else:
                logger.warning("[DEBUG PROBE] No Raw Event found.")

            # 探测 2: Message Chain Components
            if hasattr(event, 'message_chain'):
                logger.warning(f"[DEBUG PROBE] Chain Length: {len(event.message_chain)}")
                for i, comp in enumerate(event.message_chain):
                    comp_type = getattr(comp, 'type', 'unknown')
                    comp_cls = comp.__class__.__name__
                    comp_str = str(comp)
                    logger.warning(f"[DEBUG PROBE] Comp #{i}: Class={comp_cls}, Type={comp_type}, Str={comp_str}")
            
            logger.warning("="*30 + " DEBUG PROBE END " + "="*30)

        # ---------------------------------------------------------
        # 【全手段检测逻辑】
        # ---------------------------------------------------------
        is_poke = False
        
        if self.config.get("features.nudge_response", True):
            # 1. 检查 Raw Event (OneBot 标准)
            raw = getattr(event, 'raw_event', None) or getattr(event, 'original_event', None)
            if isinstance(raw, dict):
                # 兼容 OneBot v11 notice 事件
                if raw.get('sub_type') == 'poke' or raw.get('type') == 'poke' or raw.get('notice_type') == 'notify':
                    is_poke = True
                    logger.info("[Echo of Theresia] 命中: Raw Event")

            # 2. 检查 Message Chain (组件扫描)
            if not is_poke and hasattr(event, 'message_chain'):
                for comp in event.message_chain:
                    s = str(comp).lower()
                    t = getattr(comp, 'type', '').lower()
                    c = comp.__class__.__name__.lower()
                    # 暴力匹配所有可能的属性
                    if "poke" in s or "nudge" in s or "戳" in s or t == 'poke' or "poke" in c:
                        is_poke = True
                        logger.info(f"[Echo of Theresia] 命中: Chain Component ({s})")
                        break
            
            # 3. 检查 文本遗留
            if not is_poke and ("[Poke:" in text or "[戳一戳]" in text):
                 is_poke = True
                 logger.info("[Echo of Theresia] 命中: Text String")

        if is_poke:
            logger.info(f"[Echo of Theresia] >>> 触发信赖触摸反馈 <<<")
            interaction_type = random.choice(["poke", "trust"])
            rel_path = self.voice_manager.get_voice(interaction_type)
            if rel_path:
                async for msg in self.safe_yield_voice(event, rel_path):
                    yield msg
            return # 戳一戳处理完毕，直接退出

        # ---------------------------------------------------------
        # 常规逻辑 (防止 IndexError)
        # ---------------------------------------------------------
        if not text:
            return 

        # 指令过滤
        cmd_prefix = self.config.get("command.prefix", "/theresia").lower()
        if text.lower().startswith(cmd_prefix):
            return
        
        first_word = text.split()[0].lower()
        if first_word == "theresia":
            return

        now = datetime.datetime.now()
        hour = now.hour
        text_lower = text.lower()
        keywords = [kw.lower() for kw in self.config["command.keywords"]]
        has_called_name = any(kw in text_lower for kw in keywords)

        target_tag = None
        should_trigger = False
        bypass_cooldown = False

        # 理智护航
        if self.config.get("features.sanity_mode", True) and (1 <= hour < 5) and has_called_name:
            target_tag = "sanity"
            yield event.plain_result("博士，夜已经很深了……还在工作吗？")
            should_trigger = True
            bypass_cooldown = True
        
        # 情感共鸣
        elif self.config.get("features.emotion_detect", True):
            detected = self.analyze_sentiment(text)
            if detected and has_called_name:
                target_tag = detected
                should_trigger = True

        # 标准触发
        if not should_trigger and has_called_name:
            target_tag = self.config["voice.default_tag"]
            should_trigger = True

        if should_trigger:
            curr = time.time()
            if not bypass_cooldown and (curr - self.last_trigger_time < self.cooldown_seconds):
                return
            
            rel_path = self.voice_manager.get_voice(target_tag or None)
            if not rel_path and target_tag:
                 rel_path = self.voice_manager.get_voice(None)
            
            if rel_path:
                self.last_trigger_time = curr
                async for msg in self.safe_yield_voice(event, rel_path):
                    yield msg

    # ==================== 指令入口 ====================
    
    @filter.command("theresia")
    async def main_command_handler(self, event: AstrMessageEvent, action: str = None, payload: str = None):
        """
        特雷西娅插件主指令
        """
        if not action:
            yield event.plain_result(self._get_help_text(brief=True))
            return
            
        action = action.lower()

        if action == "help":
            yield event.plain_result(self._get_help_text(brief=False))
            
        elif action == "enable":
            self.config["enabled"] = True
            self._save_config()
            asyncio.create_task(self.scheduler.start())
            yield event.plain_result("特雷西娅语音插件已启用♪")
            
        elif action == "disable":
            self.config["enabled"] = False
            self._save_config()
            asyncio.create_task(self.scheduler.stop())
            yield event.plain_result("特雷西娅语音插件已禁用。")
            
        elif action == "voice":
            tag = payload or self.config["voice.default_tag"]
            rel_path = self.voice_manager.get_voice(tag)
            async for msg in self.safe_yield_voice(event, rel_path):
                yield msg
                
        elif action == "tags":
            tags = self.voice_manager.get_tags()
            if not tags:
                yield event.plain_result("暂无标签数据")
            else:
                lines = ["【可用语音标签】"] + [f"• {t}: {self.voice_manager.get_voice_count(t)} 条" for t in tags]
                yield event.plain_result("\n".join(lines))
                
        elif action == "update":
            self.voice_manager.update_voices()
            total = self.voice_manager.get_voice_count()
            yield event.plain_result(f"更新完成！共 {total} 条语音。")
            
        elif action == "set_target":
            await self.scheduler.add_target(event.session_id)
            yield event.plain_result("已将本会话设为定时问候目标~")
            
        elif action == "unset_target":
            await self.scheduler.remove_target(event.session_id)
            yield event.plain_result("已取消本会话的定时问候。")
            
        else:
            yield event.plain_result(f"未知指令: {action}，请尝试 /theresia help")

    def _get_help_text(self, brief: bool = True) -> str:
        if brief:
            return "Echo of Theresia (v1.6.0) 已就绪~\n发送 /theresia help 查看完整指令。"
        return (
            "【Echo of Theresia】\n"
            "------------------------------\n"
            "/theresia enable    - 启用插件\n"
            "/theresia disable   - 禁用插件\n"
            "/theresia voice [标签] - 发送语音\n"
            "/theresia tags      - 查看标签\n"
            "/theresia update    - 刷新资源\n"
            "/theresia set_target - 设为定时目标\n"
            "------------------------------\n"
            "特性：\n"
            "1. 情感共鸣：识别累/难过等情绪\n"
            "2. 理智护航：深夜劝睡\n"
            "3. 信赖触摸：戳一戳头像触发互动\n"
            "4. 智能否定：说「不累」不会误触"
        )