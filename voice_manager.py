# -*- coding: utf-8 -*-
import random
import re
from pathlib import Path
from typing import List, Set, Optional, Dict
from astrbot.api import logger


class VoiceEntry:
    __slots__ = ("rel_path", "tags", "weights")

    def __init__(self, rel_path: str, tags: Set[str], weights: Dict[str, int]):
        # rel_path 统一用 str，相对于插件根目录
        self.rel_path = rel_path
        # 所有标签统一为小写
        self.tags = {str(t).lower() for t in tags}
        # 权重字典也用小写 key
        self.weights = {str(k).lower(): int(v) for k, v in weights.items()}


class VoiceManager:
    """
    增强版 VoiceManager：
    - 支持标签权重
    - 支持智能随机（避免重复）
    - 支持更强的标签提取
    - 统一标签大小写（全部小写）
    """

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

    def __init__(self, plugin):
        self.plugin = plugin
        self.base_dir = Path(__file__).parent.resolve()
        self.voice_dir = self.base_dir / "data" / "voices"

        self.entries: List[VoiceEntry] = []
        self.all_tags: Set[str] = set()

        # 全局“上一次播放的语音”（跨会话）
        self.last_voice_path: Optional[str] = None

    # ==================== 加载与扫描 ====================

    def load_voices(self) -> None:
        logger.info("[Echo of Theresia] 正在初始化语音库...")
        self.entries.clear()
        self.all_tags.clear()
        self._scan_voices()

    def update_voices(self) -> None:
        logger.info("[语音管理] 正在执行强制全盘扫描...")
        self.entries.clear()
        self.all_tags.clear()
        self._scan_voices()
        logger.info(f"[语音管理] 更新完成，当前共 {len(self.entries)} 条语音")

    def _scan_voices(self) -> None:
        if not self.voice_dir.exists():
            self.voice_dir.mkdir(parents=True, exist_ok=True)
            logger.warning(f"[语音管理] 语音目录不存在，已创建: {self.voice_dir}")
            return

        audio_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".silk", ".aac", ".flac"}
        files = [
            f for f in self.voice_dir.iterdir()
            if f.is_file() and f.suffix.lower() in audio_extensions
        ]

        logger.info(f"[语音管理] 扫描到 {len(files)} 个音频文件")

        for file_path in files:
            # 相对插件根目录（与 main.py 中的拼接方式兼容）
            rel_path = str(file_path.relative_to(self.base_dir))

            tags, weights = self._extract_tags(file_path.stem)

            # 所有语音都带有 "theresia" 标签
            tags.add("theresia")
            weights.setdefault("theresia", 1)

            entry = VoiceEntry(rel_path=rel_path, tags=tags, weights=weights)
            self.entries.append(entry)
            self.all_tags.update(entry.tags)

        logger.info(f"[语音管理] 完成索引，标签总数: {len(self.all_tags)}")

    # ==================== 标签提取（增强版） ====================

    def _extract_tags(self, filename: str) -> (Set[str], Dict[str, int]):
        tags: Set[str] = set()
        weights: Dict[str, int] = {}

        # 1. 预设映射（键值匹配文件名）
        for key, preset in self.PRESET_MAPPING.items():
            if key in filename:
                for tag, w in preset.items():
                    tag_norm = str(tag).lower()
                    tags.add(tag_norm)
                    weights[tag_norm] = max(weights.get(tag_norm, 0), int(w))

        # 2. 下划线分割，抽取英文/拼音型标签
        parts = filename.lower().split("_")
        for part in parts:
            cleaned = re.sub(r"^\d+|\d+$", "", part)
            cleaned = cleaned.strip()
            if len(cleaned) > 1:
                tags.add(cleaned)
                weights.setdefault(cleaned, 1)

        # 3. 中文词提取
        chinese_words = re.findall(r"[\u4e00-\u9fa5]+", filename)
        for word in chinese_words:
            word_norm = word.lower()
            tags.add(word_norm)
            weights.setdefault(word_norm, 1)

        return tags, weights

    # ==================== 智能语音选择 ====================

    def get_voice(self, tag: Optional[str] = None) -> Optional[str]:
        if not self.entries:
            logger.warning("[语音管理] 当前语音库为空")
            return None

        # 1. 无标签 → 全局随机（避免重复）
        if not tag:
            candidates = [e.rel_path for e in self.entries]
            return self._pick_non_repeating(candidates)

        tag_lower = str(tag).lower()

        # 2. 精确匹配标签
        candidates_entries = [e for e in self.entries if tag_lower in e.tags]

        # 3. 模糊匹配文件名
        if not candidates_entries:
            candidates_entries = [
                e for e in self.entries
                if tag_lower in Path(e.rel_path).stem.lower()
            ]

        if not candidates_entries:
            logger.info(f"[语音管理] 未找到匹配标签的语音: tag={tag_lower}")
            return None

        # 4. 权重选择（智能随机）
        weighted_paths: List[str] = []
        for e in candidates_entries:
            weight = e.weights.get(tag_lower, 1)
            # 防止权重为 0 或负数
            weight = max(int(weight), 1)
            weighted_paths.extend([e.rel_path] * weight)

        return self._pick_non_repeating(weighted_paths)

    # ==================== 避免重复播放 ====================

    def _pick_non_repeating(self, items: List[str]) -> Optional[str]:
        """避免连续播放同一条语音（全局维度）"""
        if not items:
            return None

        if len(items) == 1:
            chosen = items[0]
        else:
            filtered = [i for i in items if i != self.last_voice_path]
            chosen = random.choice(filtered or items)

        self.last_voice_path = chosen
        return chosen

    # ==================== 工具方法 ====================

    def get_tags(self) -> List[str]:
        """返回当前语音库中所有标签（排序后）"""
        return sorted(self.all_tags)

    def get_voice_count(self, tag: Optional[str] = None) -> int:
        """获取语音条数，可按标签过滤"""
        if not tag:
            return len(self.entries)
        t = str(tag).lower()
        return sum(1 for e in self.entries if t in e.tags)
