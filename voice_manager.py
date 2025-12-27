# -*- coding: utf-8 -*-
import random
import re
import time
from pathlib import Path
from collections import deque
from typing import List, Set, Optional, Dict, Deque, Union
from astrbot.api import logger

class VoiceEntry:
    __slots__ = ("rel_path", "tags", "base_weights", "usage_count", "last_used")

    def __init__(self, rel_path: str, tags: Set[str], weights: Dict[str, int]):
        self.rel_path = rel_path
        self.tags = {str(t).lower() for t in tags}
        self.base_weights = {str(k).lower(): int(v) for k, v in weights.items()}
        self.usage_count = 0
        self.last_used = 0.0

    def get_weight(self, tag: str) -> float:
        base = self.base_weights.get(tag, 1)
        # 动态权重衰减算法 v2: 
        # 初始权重高，随着使用次数增加呈对数衰减，防止完全如果不播放
        # usage=0 -> 1.0
        # usage=1 -> 0.66
        # usage=5 -> 0.28
        dynamic = base / (1 + self.usage_count * 0.5)
        
        # 时间回升机制：如果很久没播了(比如1小时)，权重稍微回升
        elapsed = time.time() - self.last_used
        if self.usage_count > 0 and elapsed > 3600:
            dynamic *= 1.2
            
        return dynamic


class VoiceManager:

    # ==================== 1. 深度语义映射表 ====================
    # 作用：将明日方舟的原始文件名，映射到 v3.1 情感引擎的 Tag
    PRESET_MAPPING: Dict[str, Dict[str, int]] = {
        # === 核心回应 ===
        "闲置": { "sanity": 5, "rest": 5, "sleep": 5, "tired": 5, "company": 3 },
        "选中干员1": { "confidence": 5, "pride": 4 },
        "选中干员2": { "comfort": 5, "fear": 5, "trust": 4 },
        "部署1": { "company": 4, "battle": 3 },
        "部署2": { "company": 5, "loneliness": 5, "support": 4 },
        "作战中1": { "hope": 4, "battle": 3 },
        "作战中2": { "pain": 4, "dont_cry": 3 },
        "作战中3": { "company": 5, "trust": 4 }, 
        "作战中4": { "dont_cry": 5, "sadness": 5, "pain": 5, "comfort": 3 },
        
        # === 结算与反馈 ===
        "4星结束行动": { "praise": 5, "pride": 5, "excitement": 4, "victory": 5 },
        "3星结束行动": { "praise": 5, "smart": 5, "happy": 4 },
        "非3星结束行动": { "gratitude": 5, "thanks": 5, "comfort": 3 },
        "行动失败": { "fail": 5, "disappointment": 4, "encourage": 5 },
        
        # === 基地与互动 ===
        "任命助理": { "trust": 5, "identity": 4 },
        "交谈1": { "confusion": 4, "chat": 3 }, 
        "交谈2": { "happy": 4, "smile": 5, "chat": 3 },
        "交谈3": { "work": 4, "sanity": 3 },
        "信赖提升后交谈1": { "trust": 4, "memory": 4 },
        "信赖提升后交谈2": { "trust": 5, "hope": 4 },
        "信赖提升后交谈3": { "forgive": 5, "guilt": 5, "comfort": 4, "affection": 5 },
        
        # === 特殊 ===
        "问候": { "morning": 5, "hello": 5, "start": 4 },
        "信赖触摸": { "trust": 5, "affection": 5, "love": 4, "poke": 3 }, # 触摸也可以响应 poke
        "戳一下": { "poke": 5, "surprise": 5, "fun": 4 },
        "标题": { "intro": 5 },
        "晋升后交谈1": { "hope": 4, "future": 4 },
        "晋升后交谈2": { "hope": 5, "heal": 5, "affection": 4 },
    }

    # ==================== 2. 角色性格适配器 (核心升级) ====================
    # 作用：将用户的负面情绪，转化为特雷西娅的人设回应
    # 例如：用户 Anger (愤怒) -> 特雷西娅 Comfort (安抚) / Patience (包容)
    CHARACTER_ADAPTER: Dict[str, List[str]] = {
        # 用户情绪 -> 特雷西娅回应 Tag (按优先级)
        
        # 负面转化
        "anger": ["comfort", "soft", "patience", "sanity"],    # 你生气 -> 她安抚
        "disappointment": ["encourage", "company", "fail"],    # 你失望 -> 她鼓励
        "fear": ["comfort", "company", "trust"],               # 你害怕 -> 她陪伴
        "sadness": ["dont_cry", "comfort", "company"],         # 你悲伤 -> 她让你别哭
        "pain": ["heal", "dont_cry", "comfort"],               # 你痛苦 -> 她治愈
        "fatigue": ["sanity", "rest", "sleep"],                # 你累了 -> 她让你睡
        "loneliness": ["company", "deploy", "trust"],          # 你孤独 -> 她陪你
        "confusion": ["guide", "trust", "chat"],               # 你困惑 -> 她指引
        
        # 正面映射
        "excitement": ["praise", "happy", "smile"],            # 你兴奋 -> 她微笑/夸奖
        "pride": ["praise", "trust", "victory"],               # 你骄傲 -> 她夸奖
        "affection": ["trust", "love", "affection"],           # 你爱她 -> 她回应爱
        "gratitude": ["welcome", "trust", "smile"],            # 你感谢 -> 她接受
        "hope": ["hope", "future", "trust"],                   # 你希望 -> 她展望未来
        "morning": ["morning", "hello"],                       # 早安
    }

    def __init__(self, plugin):
        self.plugin = plugin
        self.base_dir = Path(__file__).parent.resolve()
        self.voice_dir = self.base_dir / "data" / "voices"

        self.entries: List[VoiceEntry] = []
        self.all_tags: Set[str] = set()
        self.history_queue: Deque[str] = deque(maxlen=6) # 稍微增加历史记录长度

    # ==================== 资源加载 ====================

    def load_voices(self) -> None:
        logger.info("[Echo Voice v3.3] 正在加载特雷西娅语音库 (Character Adapter Loaded)...")
        self.entries.clear()
        self.all_tags.clear()
        self._scan_voices()

    def update_voices(self) -> None:
        self.entries.clear()
        self.all_tags.clear()
        self._scan_voices()

    def _scan_voices(self) -> None:
        if not self.voice_dir.exists():
            self.voice_dir.mkdir(parents=True, exist_ok=True)
            return

        audio_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".silk", ".aac", ".flac"}
        files = [f for f in self.voice_dir.iterdir() if f.is_file() and f.suffix.lower() in audio_extensions]

        for file_path in files:
            rel_path = str(file_path.relative_to(self.base_dir))
            tags, weights = self._extract_tags(file_path.stem)
            
            # 添加基础标签
            tags.add("theresia")
            tags.add("all")
            weights.setdefault("theresia", 1)

            entry = VoiceEntry(rel_path=rel_path, tags=tags, weights=weights)
            self.entries.append(entry)
            self.all_tags.update(entry.tags)
        
        logger.info(f"[Echo Voice] 加载完成: {len(self.entries)} 条语音, 覆盖 {len(self.all_tags)} 个标签")

    def _extract_tags(self, filename: str) -> (Set[str], Dict[str, int]):
        tags: Set[str] = set()
        weights: Dict[str, int] = {}
        filename_norm = filename.lower()

        # 1. 深度匹配预设规则
        for key, preset in self.PRESET_MAPPING.items():
            if key in filename: 
                for tag, w in preset.items():
                    t_norm = str(tag).lower()
                    tags.add(t_norm)
                    weights[t_norm] = max(weights.get(t_norm, 0), int(w))

        # 2. 文件名关键词自动提取 (Backup)
        # 如果文件名里包含 "sleep", 自动加 sleep 标签
        common_keywords = ["sleep", "love", "trust", "hello", "bye", "laugh", "cry"]
        for kw in common_keywords:
            if kw in filename_norm:
                tags.add(kw)
                weights.setdefault(kw, 3)

        return tags, weights

    # ==================== 智能获取逻辑 ====================

    def get_voice(self, input_tag: Optional[str] = None) -> Optional[str]:
        if not self.entries:
            return None

        # 1. 标签转换与扩充 (Adapter Layer)
        search_tags = set()
        primary_tag = "theresia" # 默认 tag
        
        if input_tag:
            raw_tag = str(input_tag).lower()
            primary_tag = raw_tag
            
            # A. 直接匹配
            search_tags.add(raw_tag)
            
            # B. 角色性格适配 (Character Adapter)
            # 如果输入是 "anger" (用户生气)，转为 ["comfort", "sanity"] (特雷西娅安抚)
            if raw_tag in self.CHARACTER_ADAPTER:
                adapted_tags = self.CHARACTER_ADAPTER[raw_tag]
                search_tags.update(adapted_tags)
                # 将适配后的第一个 tag 设为主要权重参考
                if adapted_tags:
                    primary_tag = adapted_tags[0]
        
        # 2. 候选池筛选 (Intersection)
        candidates = []
        if not input_tag:
            candidates = self.entries
        else:
            # 只要包含 search_tags 中的任意一个即可
            for entry in self.entries:
                if not entry.tags.isdisjoint(search_tags):
                    candidates.append(entry)

        # 3. 降级策略 (Fallback)
        if not candidates and input_tag:
            # 尝试模糊文件名匹配
            t = str(input_tag).lower()
            candidates = [e for e in self.entries if t in Path(e.rel_path).stem.lower()]
            
            # 如果还是没有，且情感是负面的，尝试通用的 comfort
            if not candidates and input_tag in ["sadness", "pain", "fear", "fail"]:
                 candidates = [e for e in self.entries if "comfort" in e.tags]

        if not candidates:
            return None

        # 4. 短期记忆屏蔽 (History Blocking)
        # 尝试排除最近播放过的
        available_pool = []
        if len(candidates) > 2:
            for c in candidates:
                if c.rel_path not in self.history_queue:
                    available_pool.append(c)
            if not available_pool: # 如果都被屏蔽了，回退到原列表
                available_pool = candidates
        else:
            available_pool = candidates

        # 5. 动态权重计算 (Scoring)
        weighted_pool = []
        weights = []
        
        for entry in available_pool:
            # 获取权重
            # 如果 entry 有 primary_tag (适配后的最优解)，权重会很高
            # 如果 entry 只有 search_tags 里的次优解，权重基础值较低
            w = 1.0
            
            # 检查命中了哪个 tag，取最高权重
            max_hit_weight = 0
            for tag in search_tags:
                if tag in entry.base_weights:
                    max_hit_weight = max(max_hit_weight, entry.base_weights[tag])
            
            if max_hit_weight > 0:
                w = max_hit_weight
            
            # 应用使用次数衰减
            w = w / (1 + entry.usage_count * 0.6)
            
            # 随机扰动 (防止权重完全固定)
            w *= random.uniform(0.9, 1.1)

            weighted_pool.append(entry)
            weights.append(w)

        # 6. 最终选择
        try:
            chosen_entry = random.choices(weighted_pool, weights=weights, k=1)[0]
        except (IndexError, ValueError):
            chosen_entry = random.choice(available_pool)

        # 7. 更新状态
        self._update_stats(chosen_entry)
        
        return chosen_entry.rel_path

    def _update_stats(self, entry: VoiceEntry):
        """更新播放统计"""
        entry.usage_count += 1
        entry.last_used = time.time()
        
        self.history_queue.append(entry.rel_path)
        
        # 概率性全局衰减 (防止长期运行后所有语音权重都极低)
        # 每播放 20 次左右，全局衰减一次 usage_count
        if random.random() < 0.05:
            for e in self.entries:
                if e.usage_count > 0:
                    e.usage_count = max(0, int(e.usage_count * 0.8))

    # ==================== 工具方法 ====================

    def get_tags(self) -> List[str]:
        return sorted(list(self.all_tags))

    def get_voice_count(self, tag: Optional[str] = None) -> int:
        if not tag: return len(self.entries)
        t = str(tag).lower()
        # 考虑适配器
        search_tags = {t}
        if t in self.CHARACTER_ADAPTER:
            search_tags.update(self.CHARACTER_ADAPTER[t])
            
        count = 0
        for e in self.entries:
            if not e.tags.isdisjoint(search_tags):
                count += 1
        return count