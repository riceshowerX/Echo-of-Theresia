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
        # 使得用户能听到更多不同的语音，而不是总是听到同一句
        dynamic = base / (1 + self.usage_count * 0.5)
        return dynamic


class VoiceManager:

    # ==================== 深度语义映射表 ====================
    # 键：文件名中的关键词
    # 值：情感标签及权重 (权重 1-5)
    PRESET_MAPPING: Dict[str, Dict[str, int]] = {
        # === 核心情感回应 (High Priority) ===
        "闲置": { 
            # "博士，累了吗？那就休息吧..."
            "sanity": 5, "rest": 5, "sleep": 5, "tired": 5, "晚安": 5 
        },
        "选中干员2": { 
            # "别怕，我在。" -> 完美回应恐惧
            "comfort": 5, "fear": 5, "scared": 5, "help": 5 
        },
        "作战中4": { 
            # "别哭，很快就结束了。" -> 完美回应悲伤/痛苦
            "dont_cry": 5, "sad": 5, "pain": 5, "cry": 5, "comfort": 3 
        },
        "部署2": { 
            # "我在这儿呢，我会一直陪着你。" -> 完美回应孤独
            "company": 5, "lonely": 5, "alone": 5, "deploy": 3 
        },
        "行动失败": { 
            # "我们一定可以跨过这些伤痛..." -> 回应失败/挫折
            "fail": 5, "lose": 5, "encourage": 4, "pain": 3 
        },
        "信赖提升后交谈3": {
            # "博士，你的眼里常怀愧疚...停留在过去的有她就够了。" -> 回应内疚/道歉
            "forgive": 5, "guilt": 5, "comfort": 4, "trust": 3
        },
        "晋升后交谈2": {
            # "爱意会抚平疤痕...罗德岛会迎来黎明。" -> 回应希望/爱/治愈
            "hope": 5, "love": 4, "heal": 5, "future": 4
        },

        # === 互动与问候 ===
        "戳一下": { 
            # "哈！被吓到了吗？"
            "poke": 5, "surprise": 4, "fun": 3 
        },
        "信赖触摸": { 
            # "我在注视着你，博士。"
            "trust": 5, "gaze": 4, "love": 3 
        },
        "问候": { 
            # "程序启动...博士，早上好。"
            "morning": 5, "hello": 4, "start": 3 
        },
        "生日": {
            # "祝你今后的旅途，不再孤独。"
            "birthday": 5, "company": 4, "bless": 4
        },
        "新年祝福": {
            "newyear": 5, "happy": 3
        },

        # === 战斗与工作 ===
        "3星结束行动": { 
            # "让一切都依照你的计划进行..." -> 夸奖/聪明
            "praise": 5, "smart": 5, "victory": 4, "happy": 3
        },
        "非3星结束行动": {
            # "如果没有你，我们的伤亡可能会更加严重...谢谢你。" -> 安慰/感谢
            "thanks": 5, "comfort": 3, "victory": 2
        },
        "任命助理": {
            # "我并不需要（座位）。" -> 身份认知
            "assistant": 5, "identity": 3
        },
        "交谈1": { "chat": 3, "identity": 4 }, # "不要将我当作特蕾西娅"
        "交谈2": { "chat": 3, "company": 3, "smile": 3 }, # "我也是会笑的"
        "交谈3": { "chat": 3, "work": 3 }, # "改善后勤保障"
        "作战中3": { "company": 4, "support": 4 }, # "我会陪在你身边"
    }

    # === 同义词图谱 (用户输入 -> 文件标签) ===
    # 这一步将用户的自然语言情感链接到我们上方定义的标签
    SYNONYM_MAP: Dict[str, List[str]] = {
        # 负面情绪流
        "sad": ["dont_cry", "fail", "pain", "heal"],    # 难过 -> 别哭/失败/治愈
        "scared": ["comfort", "fear", "company"],       # 害怕 -> 别怕/陪伴
        "tired": ["sanity", "rest", "company"],         # 累了 -> 休息/陪伴
        "lonely": ["company", "birthday", "deploy"],    # 孤独 -> 部署2/生日(不再孤独)
        "guilt": ["forgive", "comfort", "trust"],       # 内疚 -> 信赖3(宽慰)
        
        # 正面情绪流
        "love": ["trust", "love", "gaze", "poke"],      # 喜欢 -> 信赖触摸/晋升2
        "happy": ["praise", "morning", "newyear"],      # 开心 -> 3星结算/早安
        "thanks": ["non_3_star", "trust"],              # 谢谢 -> 非3星(互谢)
    }

    def __init__(self, plugin):
        self.plugin = plugin
        self.base_dir = Path(__file__).parent.resolve()
        self.voice_dir = self.base_dir / "data" / "voices"

        self.entries: List[VoiceEntry] = []
        self.all_tags: Set[str] = set()
        # 历史队列：记录最近 5 次播放的路径，防止重复
        self.history_queue: Deque[str] = deque(maxlen=5)

    # ==================== 资源加载 ====================

    def load_voices(self) -> None:
        logger.info("[Echo Voice v3.2] 正在加载特雷西娅语音库 (深度语义版)...")
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
            # 相对路径
            rel_path = str(file_path.relative_to(self.base_dir))
            # 提取标签
            tags, weights = self._extract_tags(file_path.stem)
            
            # 默认标签
            tags.add("theresia")
            weights.setdefault("theresia", 1)

            entry = VoiceEntry(rel_path=rel_path, tags=tags, weights=weights)
            self.entries.append(entry)
            self.all_tags.update(entry.tags)
        
        logger.info(f"[Echo Voice] 加载完成，共 {len(self.entries)} 条语音，覆盖 {len(self.all_tags)} 个标签")

    def _extract_tags(self, filename: str) -> (Set[str], Dict[str, int]):
        tags: Set[str] = set()
        weights: Dict[str, int] = {}

        # 1. 深度匹配预设规则
        for key, preset in self.PRESET_MAPPING.items():
            if key in filename: 
                for tag, w in preset.items():
                    t_norm = str(tag).lower()
                    tags.add(t_norm)
                    # 取最大权重
                    weights[t_norm] = max(weights.get(t_norm, 0), int(w))

        # 2. 简单的中文分词匹配 (辅助)
        chinese_words = re.findall(r"[\u4e00-\u9fa5]+", filename)
        for word in chinese_words:
            w_norm = word.lower()
            tags.add(w_norm)
            weights.setdefault(w_norm, 1)

        return tags, weights

    # ==================== 智能获取逻辑 ====================

    def get_voice(self, tag: Optional[str] = None) -> Optional[str]:
        if not self.entries:
            return None

        # 1. 标签扩充 (Expansion)
        search_tags = set()
        primary_tag = "theresia"
        
        if tag:
            tag_lower = str(tag).lower()
            primary_tag = tag_lower
            search_tags.add(tag_lower)
            # 查同义词表
            if tag_lower in self.SYNONYM_MAP:
                search_tags.update(self.SYNONYM_MAP[tag_lower])
        
        # 2. 候选池筛选
        candidates = []
        if not search_tags:
            # 无标签：全选
            candidates = self.entries
        else:
            # 有标签：取交集
            for entry in self.entries:
                if not entry.tags.isdisjoint(search_tags):
                    candidates.append(entry)

        # 3. 模糊文件名回退 (Fallback)
        if not candidates and tag:
            t = str(tag).lower()
            candidates = [e for e in self.entries if t in Path(e.rel_path).stem.lower()]

        if not candidates:
            return None

        # 4. 短期记忆屏蔽 (History Blocking)
        # 防止 ABA 循环 (刚刚播过的不再播)
        available_pool = []
        if len(candidates) > 2:
            for c in candidates:
                if c.rel_path not in self.history_queue:
                    available_pool.append(c)
            # 如果屏蔽完没剩几个了，就还是用原来的
            if not available_pool:
                available_pool = candidates
        else:
            available_pool = candidates

        # 5. 动态权重计算 (Dynamic Scoring)
        weighted_pool = []
        weights = []
        
        for entry in available_pool:
            # 计算该 entry 针对当前 primary_tag 的动态权重
            # 如果 primary_tag 不在 entry 的权重表里，默认权重为 1
            # 但经过动态熵减算法，播放多的权重会 < 1
            w = entry.get_weight(primary_tag)
            
            # 如果命中了核心标签（例如在 search_tags 里），额外加成
            if not entry.tags.isdisjoint(search_tags):
                w *= 1.5

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
        
        # 老化机制：极小概率衰减所有计数，防止永久低权重
        if random.random() < 0.05:
            for e in self.entries:
                if e.usage_count > 0:
                    e.usage_count = int(e.usage_count * 0.9)

    # ==================== 工具方法 ====================

    def get_tags(self) -> List[str]:
        return sorted(self.all_tags)

    def get_voice_count(self, tag: Optional[str] = None) -> int:
        if not tag: return len(self.entries)
        t = str(tag).lower()
        return sum(1 for e in self.entries if t in e.tags)