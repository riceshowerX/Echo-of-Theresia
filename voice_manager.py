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
        self.base_weights = {str(k).lower(): int(v) for k, v in weights.items()}
        self.usage_count = 0
        self.last_used = 0.0

    def get_weight(self, tag: str) -> float:
        base = self.base_weights.get(tag, 1)
        # 动态权重衰减：播放次数越多，权重越低
        dynamic = base / (1 + self.usage_count * 0.5)
        return dynamic


class VoiceManager:
    """
    Echo of Theresia 资源管理器 v3.1 (定制语音包版)
    针对特雷西娅（文明的存续）语音文本进行了语义级优化
    """

    # ==================== 核心映射表 (根据语音包定制) ====================
    PRESET_MAPPING: Dict[str, Dict[str, int]] = {
        # === 情感回应类 ===
        "闲置": {
            "sanity": 5, "rest": 5, "sleep": 4, "tired": 4,  # "累了吗？那就休息吧"
            "晚安": 5
        },
        "选中干员2": {
            "comfort": 5, "fear": 5, "scared": 5, # "别怕，我在" (完美回应害怕)
            "help": 4
        },
        "作战中4": {
            "dont_cry": 5, "sad": 5, "pain": 5, # "别哭，很快就结束了" (完美回应难过)
            "comfort": 3
        },
        "部署2": {
            "company": 5, "lonely": 5, "alone": 5, # "我在这儿呢，我会一直陪着你" (完美回应孤独)
            "support": 4
        },
        "行动失败": {
            "fail": 5, "lose": 5, "encourage": 4, # "我们一定可以跨过这些伤痛"
            "dont_cry": 2
        },
        "戳一下": {
            "poke": 5, "surprise": 3 # "哈！被吓到了吗？"
        },
        "信赖触摸": {
            "trust": 5, "love": 4, "gaze": 3 # "我在注视着你"
        },
        "问候": {
            "morning": 5, "hello": 3 # "早上好"
        },
        
        # === 补充交互类 (用于丰富日常对话) ===
        "交谈1": {"chat": 3, "identity": 4}, # "不要将我当作特蕾西娅"
        "交谈2": {"chat": 3, "company": 3},  # "我会陪在阿米娅身边"
        "交谈3": {"chat": 3, "work": 3},     # 罗德岛工作相关
        "3星结束行动": {"praise": 5, "victory": 4, "smart": 4}, # "依照你的计划进行"
        "非3星结束行动": {"thanks": 4, "victory": 3},
        "任命助理": {"assistant": 5, "memory": 3},
        "作战中3": {"company": 4, "support": 4}, # "我会陪在你身边"
        "新年祝福": {"newyear": 5},
        "生日": {"birthday": 5},
    }

    # === 同义词图谱 (将用户情绪导向我们有的语音文件) ===
    SYNONYM_MAP: Dict[str, List[str]] = {
        # 用户输入 -> 映射到哪些文件标签
        "sad": ["dont_cry", "fail", "comfort"],   # 难过 -> 别哭/失败/安慰
        "scared": ["comfort", "company"],         # 害怕 -> 别怕/陪伴
        "tired": ["sanity", "company"],           # 累了 -> 闲置(休息)/陪伴
        "lonely": ["company", "talk", "chat"],    # 孤独 -> 部署2(陪伴)/交谈
        "love": ["trust", "poke"],                # 喜欢 -> 信赖触摸/戳一戳
        "happy": ["praise", "morning", "trust"],  # 开心 -> 3星结算/早安
    }

    def __init__(self, plugin):
        self.plugin = plugin
        self.base_dir = Path(__file__).parent.resolve()
        self.voice_dir = self.base_dir / "data" / "voices"

        self.entries: List[VoiceEntry] = []
        self.all_tags: Set[str] = set()
        self.history_queue: Deque[str] = deque(maxlen=5)

    def load_voices(self) -> None:
        logger.info("[Echo Voice] 正在加载特雷西娅语音库...")
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
            
            tags.add("theresia")
            weights.setdefault("theresia", 1)

            entry = VoiceEntry(rel_path=rel_path, tags=tags, weights=weights)
            self.entries.append(entry)
            self.all_tags.update(entry.tags)

    def _extract_tags(self, filename: str) -> (Set[str], Dict[str, int]):
        tags: Set[str] = set()
        weights: Dict[str, int] = {}

        # 1. 匹配预设规则
        for key, preset in self.PRESET_MAPPING.items():
            if key in filename: # 只要文件名包含 "作战中4" 就能匹配
                for tag, w in preset.items():
                    t_norm = str(tag).lower()
                    tags.add(t_norm)
                    weights[t_norm] = max(weights.get(t_norm, 0), int(w))

        # 2. 匹配中文词
        chinese_words = re.findall(r"[\u4e00-\u9fa5]+", filename)
        for word in chinese_words:
            w_norm = word.lower()
            tags.add(w_norm)
            weights.setdefault(w_norm, 1)

        return tags, weights

    def get_voice(self, tag: Optional[str] = None) -> Optional[str]:
        if not self.entries:
            return None

        # 标签扩充与搜索逻辑 (同 VoiceManager v3.0)
        search_tags = set()
        if tag:
            tag_lower = str(tag).lower()
            search_tags.add(tag_lower)
            if tag_lower in self.SYNONYM_MAP:
                search_tags.update(self.SYNONYM_MAP[tag_lower])
        
        candidates = []
        if not search_tags:
            candidates = self.entries
            primary_tag = "theresia"
        else:
            for entry in self.entries:
                if not entry.tags.isdisjoint(search_tags):
                    candidates.append(entry)
            primary_tag = tag.lower() if tag else "theresia"

        if not candidates and tag:
            t = str(tag).lower()
            candidates = [e for e in self.entries if t in Path(e.rel_path).stem.lower()]

        if not candidates:
            return None

        # 防重复逻辑
        available_pool = []
        if len(candidates) > 2:
            for c in candidates:
                if c.rel_path not in self.history_queue:
                    available_pool.append(c)
            if not available_pool: available_pool = candidates
        else:
            available_pool = candidates

        # 动态权重计算
        weighted_pool = []
        weights = []
        for entry in available_pool:
            w = entry.get_weight(primary_tag)
            weighted_pool.append(entry)
            weights.append(w)

        try:
            chosen_entry = random.choices(weighted_pool, weights=weights, k=1)[0]
        except:
            chosen_entry = random.choice(available_pool)

        self._update_stats(chosen_entry)
        return chosen_entry.rel_path

    def _update_stats(self, entry: VoiceEntry):
        entry.usage_count += 1
        entry.last_used = time.time()
        self.history_queue.append(entry.rel_path)
        if random.random() < 0.1:
            for e in self.entries:
                if e.usage_count > 0: e.usage_count = int(e.usage_count * 0.8)

    def get_tags(self) -> List[str]:
        return sorted(self.all_tags)

    def get_voice_count(self, tag: Optional[str] = None) -> int:
        if not tag: return len(self.entries)
        t = str(tag).lower()
        return sum(1 for e in self.entries if t in e.tags)