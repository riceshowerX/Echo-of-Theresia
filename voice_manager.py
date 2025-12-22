# -*- coding: utf-8 -*-
"""
语音资源管理模块 - 优化最终版
"""

import os
import random
import json
import re
from typing import List, Dict

from astrbot.api import logger

class VoiceManager:
    def __init__(self, plugin):
        self.plugin = plugin
        self.base_dir = os.path.dirname(os.path.dirname(__file__))  # 插件根目录
        self.voice_dir = os.path.join(self.base_dir, "data", "voices")
        self.index_file = os.path.join(self.voice_dir, "index.json")
        
        os.makedirs(self.voice_dir, exist_ok=True)
        
        self.voices: Dict[str, Dict] = {}
        self.tags: set[str] = set()

    async def load_voices(self) -> None:
        logger.info("[Echo of Theresia] 正在加载语音资源...")
        self.voices.clear()
        self.tags.clear()
        
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if loaded:
                        self.voices = loaded
                        for info in self.voices.values():
                            self.tags.update(info.get("tags", []))
                        logger.info(f"[Echo of Theresia] 从索引加载 {len(self.voices)} 条语音")
                        return
            except Exception as e:
                logger.warning(f"[语音管理] 索引损坏，重新扫描: {e}")

        await self._scan_voices()
        logger.info(f"[Echo of Theresia] 扫描完成，共 {len(self.voices)} 条语音")

    async def _scan_voices(self) -> None:
        if not os.path.exists(self.voice_dir):
            return

        for root, _, files in os.walk(self.voice_dir):
            for file in files:
                if file.lower().endswith((".mp3", ".wav", ".ogg", ".m4a")) and file != "index.json":
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.base_dir)
                    
                    filename_no_ext = os.path.splitext(file)[0]
                    tags = self._extract_tags(filename_no_ext)
                    tags.append("theresia")
                    
                    quality = self._detect_quality(file_path)
                    
                    self.voices[rel_path] = {
                        "path": rel_path,
                        "filename": file,
                        "tags": list(set(tags)),
                        "size": os.path.getsize(file_path),
                        "quality": quality
                    }
                    self.tags.update(tags)

        self._save_index()

    def _extract_tags(self, filename: str) -> List[str]:
        tags = []
        if "_" in filename:
            parts = filename.lower().split("_")
            for part in parts[1:]:
                if part and part not in ("01", "02", "1", "2", "theresia"):
                    tags.append(part)
        
        chinese = re.findall(r'[\u4e00-\u9fa5]+', filename)
        tags.extend(chinese)
        
        clean = re.sub(r'\d+', '', filename).strip("_ -")
        if clean and clean not in tags:
            tags.append(clean)
            
        return [t for t in tags if t]

    def _detect_quality(self, file_path: str) -> str:
        size_kb = os.path.getsize(file_path) / 1024
        if size_kb > 1000:
            return "high"
        elif size_kb > 400:
            return "medium"
        return "low"

    def _save_index(self) -> None:
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(self.voices, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"[语音管理] 保存索引失败: {e}")

    def get_voice(self, tag: str = None) -> str:
        if not self.voices:
            return ""
        
        candidates = []
        for rel_path, info in self.voices.items():
            tags = [t.lower() for t in info.get("tags", [])]
            if tag is None or tag.lower() in tags:
                candidates.append(rel_path)
        
        if not candidates:
            return ""
        
        return random.choice(candidates)

    def get_tags(self) -> List[str]:
        return sorted(list(self.tags))

    def get_voice_count(self, tag: str = None) -> int:
        if tag is None:
            return len(self.voices)
        return sum(1 for info in self.voices.values() if tag.lower() in [t.lower() for t in info.get("tags", [])])

    async def update_voices(self) -> None:
        await self._scan_voices()