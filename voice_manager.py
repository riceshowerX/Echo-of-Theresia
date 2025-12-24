# -*- coding: utf-8 -*-
import random
import re
import time
from pathlib import Path
from collections import deque
from typing import List, Set, Optional, Dict, Deque
from astrbot.api import logger


class VoiceEntry:
    __slots__ = ("rel_path", "tags", "base_weights", "usage_count", "last_used")

    def __init__(self, rel_path: str, tags: Set[str], weights: Dict[str, int]):
        self.rel_path = rel_path
        self.tags = {str(t).lower() for t in tags}
        # 基础权重 (静态)
        self.base_weights = {str(k).lower(): int(v) for k, v in weights.items()}
        
        # 动态状态 (运行时)
        self.usage_count = 0  # 播放次数
        self.last_used = 0.0  # 上次播放时间戳

    def get_weight(self, tag: str) -> float:
        """
        获取动态权重：结合基础权重和使用频率
        算法：公平排队 (Fair Queuing)
        Weight = Base / (1 + Usage * 0.5)
        """
        base = self.base_weights.get(tag, 1)
        # 惩罚系数 0.5: 播放一次，权重约变为原来的 2/3，播放两次变为 1/2
        # 这样既保证了随机性，又让冷门语音有机会浮上来
        dynamic = base / (1 + self.usage_count * 0.5)
        return dynamic


class VoiceManager:
    """
    Echo of Theresia 资源管理器 v3.0 (Algorithm Enhanced)
    特性：
    - 动态权重衰减 (防止重复听同一条)
    - 短期记忆屏蔽 (防止 ABA 循环)
    - 模糊标签扩充 (同义词联想)
    """

    # 预设文件名映射规则
    PRESET_MAPPING: Dict[str, Dict[str, int]] = {
        "闲置": {"sanity": 3, "rest": 2, "晚安": 2, "休息": 2, "累": 1},
        "问候": {"morning": 3, "早安": 2},
        "选中干员2": {"comfort": 3, "安慰": 2, "别怕": 2, "fear": 1},
        "部署2": {"company": 3, "陪伴": 2, "孤独": 2},
        "作战中4": {"dont_cry": 3, "痛苦": 2, "sad": 2},
        "行动失败": {"fail": 3, "鼓励": 2},
        "戳一下": {"poke": 3, "互动": 2},
        "信赖触摸": {"trust": 3, "注视": 2, "抱抱": 2},
        "新年祝福": {"newyear": 3},
        "生日": {"birthday": 3},
    }

    # 同义词扩充图谱 (轻量级)
    SYNONYM_MAP: Dict[str, List[str]] = {
        "sad": ["dont_cry", "fail", "难过", "痛苦"],
        "happy": ["trust", "morning", "笑", "开心"],
        "rest": ["sanity", "sleep", "晚安", "休息"],
        "interaction": ["poke", "trust", "company"],
        "love": ["trust", "like", "喜欢"]
    }

    def __init__(self, plugin):
        self.plugin = plugin
        self.base_dir = Path(__file__).parent.resolve()
        self.voice_dir = self.base_dir / "data" / "voices"

        self.entries: List[VoiceEntry] = []
        self.all_tags: Set[str] = set()

        # 短期记忆队列：记录最近播放的 5 条路径
        self.history_queue: Deque[str] = deque(maxlen=5)

    # ==================== 加载与扫描 ====================

    def load_voices(self) -> None:
        logger.info("[Echo Voice v3.0] 正在初始化智能语音库...")
        self.entries.clear()
        self.all_tags.clear()
        self._scan_voices()

    def update_voices(self) -> None:
        logger.info("[语音管理] 执行全盘重扫...")
        self.entries.clear()
        self.all_tags.clear()
        self._scan_voices()
        logger.info(f"[语音管理] 索引完成，共 {len(self.entries)} 条资源")

    def _scan_voices(self) -> None:
        if not self.voice_dir.exists():
            self.voice_dir.mkdir(parents=True, exist_ok=True)
            return

        audio_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".silk", ".aac", ".flac"}
        files = [
            f for f in self.voice_dir.iterdir()
            if f.is_file() and f.suffix.lower() in audio_extensions
        ]

        for file_path in files:
            rel_path = str(file_path.relative_to(self.base_dir))
            tags, weights = self._extract_tags(file_path.stem)
            
            # 默认标签
            tags.add("theresia")
            weights.setdefault("theresia", 1)

            entry = VoiceEntry(rel_path=rel_path, tags=tags, weights=weights)
            self.entries.append(entry)
            self.all_tags.update(entry.tags)

    def _extract_tags(self, filename: str) -> (Set[str], Dict[str, int]):
        tags: Set[str] = set()
        weights: Dict[str, int] = {}

        # 1. 预设映射
        for key, preset in self.PRESET_MAPPING.items():
            if key in filename:
                for tag, w in preset.items():
                    t_norm = str(tag).lower()
                    tags.add(t_norm)
                    weights[t_norm] = max(weights.get(t_norm, 0), int(w))

        # 2. 下划线分割
        parts = filename.lower().split("_")
        for part in parts:
            cleaned = re.sub(r"^\d+|\d+$", "", part).strip()
            if len(cleaned) > 1:
                tags.add(cleaned)
                weights.setdefault(cleaned, 1)

        # 3. 中文提取
        chinese_words = re.findall(r"[\u4e00-\u9fa5]+", filename)
        for word in chinese_words:
            w_norm = word.lower()
            tags.add(w_norm)
            weights.setdefault(w_norm, 1)

        return tags, weights

    # ==================== 智能获取 (Core Algorithm) ====================

    def get_voice(self, tag: Optional[str] = None) -> Optional[str]:
        if not self.entries:
            return None

        # 1. 标签扩充 (Expansion)
        search_tags = set()
        if tag:
            tag_lower = str(tag).lower()
            search_tags.add(tag_lower)
            # 如果命中了同义词库，把同义词也加入搜索
            if tag_lower in self.SYNONYM_MAP:
                search_tags.update(self.SYNONYM_MAP[tag_lower])
        
        # 2. 候选筛选
        candidates = []
        if not search_tags:
            candidates = self.entries # 无标签则全选
            primary_tag = "theresia"
        else:
            # 只要包含任意一个 search_tags 里的标签就算命中
            for entry in self.entries:
                if not entry.tags.isdisjoint(search_tags):
                    candidates.append(entry)
            primary_tag = tag.lower() if tag else "theresia"

        # 3. 模糊文件名回退 (Fallback)
        if not candidates and tag:
            t = str(tag).lower()
            candidates = [e for e in self.entries if t in Path(e.rel_path).stem.lower()]

        if not candidates:
            return None

        # 4. 短期记忆屏蔽 (History Blocking)
        # 如果候选数量足够多(>2)，则屏蔽掉历史队列里的文件，防止 ABA 循环
        available_pool = []
        if len(candidates) > 2:
            for c in candidates:
                if c.rel_path not in self.history_queue:
                    available_pool.append(c)
            # 如果屏蔽完没剩几个了，就还是用原来的(防止无路可走)
            if not available_pool:
                available_pool = candidates
        else:
            available_pool = candidates

        # 5. 动态权重计算 (Dynamic Scoring)
        weighted_pool = []
        weights = []
        
        for entry in available_pool:
            # 计算该 entry 针对当前 tag 的动态权重
            w = entry.get_weight(primary_tag)
            weighted_pool.append(entry)
            weights.append(w)

        # 6. 加权随机选择
        try:
            chosen_entry = random.choices(weighted_pool, weights=weights, k=1)[0]
        except (IndexError, ValueError):
            chosen_entry = random.choice(available_pool)

        # 7. 更新状态
        self._update_stats(chosen_entry)
        
        return chosen_entry.rel_path

    def _update_stats(self, entry: VoiceEntry):
        """更新播放统计和历史队列"""
        entry.usage_count += 1
        entry.last_used = time.time()
        
        self.history_queue.append(entry.rel_path)
        
        # 简单的老化机制：每播放 10 次，让所有 entry 的计数器衰减，避免 permanently low probability
        # 这里用一种极简的概率触发方式
        if random.random() < 0.1:
            for e in self.entries:
                if e.usage_count > 0:
                    e.usage_count = int(e.usage_count * 0.8)

    # ==================== 工具 ====================

    def get_tags(self) -> List[str]:
        return sorted(self.all_tags)

    def get_voice_count(self, tag: Optional[str] = None) -> int:
        if not tag: return len(self.entries)
        t = str(tag).lower()
        return sum(1 for e in self.entries if t in e.tags)