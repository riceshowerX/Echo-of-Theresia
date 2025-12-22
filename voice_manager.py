# -*- coding: utf-8-
"""
语音资源管理模块 - 相对路径终极成功版
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
        # 基于插件根目录的正确路径方案
        # 获取插件根目录路径
        plugin_root = os.path.dirname(os.path.abspath(__file__))
        
        # 语音目录相对于插件根目录
        self.voice_dir = os.path.join(plugin_root, "data", "voices")
        self.index_file = os.path.join(self.voice_dir, "index.json")
        
        # 确保目录存在
        os.makedirs(self.voice_dir, exist_ok=True)
        
        self.voices: List[str] = []  # 简化：只存相对路径列表
        self.tags: set[str] = set()

    async def load_voices(self) -> None:
        logger.info("[Echo of Theresia] 正在加载语音资源...")
        logger.info(f"[语音管理] 语音目录: {self.voice_dir}")
        
        self.voices.clear()
        self.tags.clear()
        
        # 尝试加载索引
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("files"):
                        self.voices = data["files"]
                        self.tags = set(data.get("tags", []))
                        logger.info(f"[Echo of Theresia] 从索引加载 {len(self.voices)} 条语音")
                        return
            except Exception as e:
                logger.warning(f"[语音管理] 索引损坏，将重新扫描: {e}")

        await self._scan_voices()
        logger.info(f"[Echo of Theresia] 扫描完成，共 {len(self.voices)} 条语音")

    async def _scan_voices(self) -> None:
        if not os.path.exists(self.voice_dir):
            logger.warning(f"[语音管理] 语音目录不存在: {self.voice_dir}")
            return
        
        content = os.listdir(self.voice_dir)
        logger.info(f"[语音管理] voices 目录内容: {content}")

        found_files = 0
        for file in content:
            file_lower = file.lower()
            if file_lower.endswith((".mp3", ".wav", ".ogg", ".m4a")) and file_lower != "index.json":
                found_files += 1
                # 使用相对于插件根目录的路径
                rel_path = os.path.join("data", "voices", file)
                logger.info(f"[语音管理] 发现语音: {rel_path}")
                
                # 提取标签
                filename_no_ext = os.path.splitext(file)[0]
                tags = self._extract_tags(filename_no_ext)
                tags.append("theresia")
                self.tags.update(tags)
                
                self.voices.append(rel_path)

        logger.info(f"[语音管理] 扫描结束，共发现 {found_files} 个有效语音文件")

        if found_files > 0:
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
        
        clean = re.sub(r'\d+', '', filename).strip("_ -.")
        if clean and clean not in tags:
            tags.append(clean)
            
        return [t for t in tags if t]

    def _save_index(self) -> None:
        data = {
            "files": self.voices,
            "tags": list(self.tags)
        }
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info(f"[语音管理] 索引保存成功")
        except Exception as e:
            logger.error(f"[语音管理] 保存索引失败: {e}")

    def get_voice(self, tag: str = None) -> str:
        if not self.voices:
            return ""
        
        candidates = []
        for rel_path in self.voices:
            filename = os.path.basename(rel_path)
            filename_no_ext = os.path.splitext(filename)[0]
            file_tags = self._extract_tags(filename_no_ext)
            file_tags.append("theresia")
            file_tags_lower = [t.lower() for t in file_tags]
            if tag is None or tag.lower() in file_tags_lower:
                candidates.append(rel_path)
        
        if not candidates:
            return ""
        
        return random.choice(candidates)

    def get_tags(self) -> List[str]:
        return sorted(list(self.tags))

    def get_voice_count(self, tag: str = None) -> int:
        if tag is None:
            return len(self.voices)
        count = 0
        for rel_path in self.voices:
            filename = os.path.basename(rel_path)
            filename_no_ext = os.path.splitext(filename)[0]
            file_tags = self._extract_tags(filename_no_ext)
            file_tags.append("theresia")
            if tag.lower() in [t.lower() for t in file_tags]:
                count += 1
        return count

    async def update_voices(self) -> None:
        logger.info("[语音管理] 手动更新语音资源...")
        await self._scan_voices()