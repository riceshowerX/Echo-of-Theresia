# -*- coding: utf-8 -*-
import json
import random
import re
from pathlib import Path
from typing import List, Set, Optional
from astrbot.api import logger

class VoiceEntry:
    __slots__ = ('rel_path', 'tags')
    def __init__(self, rel_path: str, tags: Set[str]):
        self.rel_path = rel_path
        self.tags = tags

class VoiceManager:
    # ================= 预设映射表 (适配 PRTS 默认文件名) =================
    # 即使文件名不改，也能通过这些特定名称识别出功能标签
    PRESET_MAPPING = {
        "闲置": {"sanity", "rest", "晚安", "休息", "累", "治愈"},  # 关键：理智护航语音
        "问候": {"morning", "早安", "启动"},
        "选中干员2": {"comfort", "安慰", "别怕", "难过", "fear"}, # "别怕，我在"
        "部署2": {"company", "陪伴", "孤独", "lonely"},         # "我在这儿呢"
        "作战中4": {"dont_cry", "别哭", "痛苦", "sad"},         # "别哭，很快就结束了"
        "行动失败": {"fail", "失败", "鼓励", "encourage"},      # "我们一定可以跨过这些伤痛"
        "非3星结束行动": {"thanks", "感谢"},
        "戳一下": {"poke", "互动", "惊喜", "戳"},
        "信赖触摸": {"trust", "互动", "注视", "抱抱"},
        "新年祝福": {"newyear", "新年"},
        "生日": {"birthday", "生日"}
    }
    # ===============================================================

    def __init__(self, plugin):
        self.plugin = plugin
        self.base_dir = Path(__file__).parent.resolve()
        self.voice_dir = self.base_dir / "data" / "voices"
        self.index_file = self.voice_dir / "index.json"
        self.entries: List[VoiceEntry] = []
        self.all_tags: Set[str] = set()

    def load_voices(self) -> None:
        logger.info("[Echo of Theresia] 正在初始化语音库...")
        self.entries.clear()
        self.all_tags.clear()
        
        # 即使有索引，为了配合代码映射更新，建议优先扫描或合并逻辑
        # 这里为了简单稳健，直接执行扫描，确保新映射生效
        self._scan_voices()

    def update_voices(self) -> None:
        logger.info("[语音管理] 正在执行强制全盘扫描...")
        self.entries.clear()
        self.all_tags.clear()
        self._scan_voices()
        logger.info(f"[语音管理] 更新完成，当前共 {len(self.entries)} 条语音")

    def _scan_voices(self) -> None:
        if not self.voice_dir.exists():
            try:
                self.voice_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            return

        audio_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".silk", ".aac", ".flac"}
        files = [f for f in self.voice_dir.iterdir() if f.is_file() and f.suffix.lower() in audio_extensions]

        logger.info(f"[语音管理] 扫描到 {len(files)} 个音频文件")

        for file_path in files:
            try:
                rel_path = str(file_path.relative_to(self.base_dir))
            except ValueError:
                rel_path = str(file_path.name)

            # 提取标签
            tags = self._extract_tags(file_path.stem)
            tags.add("theresia") 

            entry = VoiceEntry(rel_path=rel_path, tags=tags)
            self.entries.append(entry)
            self.all_tags.update(tags)

        if self.entries:
            self._save_index()

    def _extract_tags(self, filename: str) -> Set[str]:
        tags = set()
        
        # 1. 优先匹配预设映射表 (精确匹配文件名)
        # 例如文件名叫 "闲置"，直接赋予 "sanity", "晚安" 等标签
        for key, preset_tags in self.PRESET_MAPPING.items():
            # 检查文件名是否包含预设 Key (比如 "闲置" 在 "闲置.mp3" 中)
            if key in filename: 
                tags.update(preset_tags)

        # 2. 常规提取 (中文/下划线)
        filename_lower = filename.lower()
        parts = filename_lower.split("_")
        for part in parts:
            cleaned = re.sub(r'^\d+|\d+$', '', part)
            if len(cleaned) > 1:
                tags.add(cleaned)

        chinese_words = re.findall(r'[\u4e00-\u9fa5]+', filename_lower)
        tags.update(chinese_words)

        return tags

    def _save_index(self) -> None:
        # 简化的保存逻辑，实际应用中可按需实现完整 JSON 写入
        pass

    def get_voice(self, tag: Optional[str] = None) -> Optional[str]:
        if not self.entries: return None
        if not tag: return random.choice(self.entries).rel_path

        tag_lower = tag.lower()
        # 精确匹配标签
        candidates = [e for e in self.entries if tag_lower in e.tags]
        
        if not candidates:
            # 模糊匹配文件名作为回退
            candidates = [e for e in self.entries if tag_lower in str(Path(e.rel_path).stem).lower()]

        if not candidates: return None
        return random.choice(candidates).rel_path

    def get_tags(self) -> List[str]:
        return sorted(list(self.all_tags))

    def get_voice_count(self, tag: Optional[str] = None) -> int:
        if not tag: return len(self.entries)
        return sum(1 for e in self.entries if tag.lower() in e.tags)