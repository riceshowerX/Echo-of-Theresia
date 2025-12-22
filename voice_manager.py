# -*- coding: utf-8 -*-
"""
语音资源管理模块 - 优化最终版（增强日志 + 健壮扫描）
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
        # 插件根目录（main.py 同级）
        self.base_dir = os.path.dirname(os.path.dirname(__file__))
        self.voice_dir = os.path.join(self.base_dir, "data", "voices")
        self.index_file = os.path.join(self.voice_dir, "index.json")
        
        # 确保目录存在
        os.makedirs(self.voice_dir, exist_ok=True)
        
        self.voices: Dict[str, Dict] = {}
        self.tags: set[str] = set()

    async def load_voices(self) -> None:
        logger.info("[Echo of Theresia] 正在加载语音资源...")
        logger.info(f"[语音管理] 语音目录绝对路径: {os.path.abspath(self.voice_dir)}")
        
        self.voices.clear()
        self.tags.clear()
        
        # 尝试加载已有索引
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
                logger.warning(f"[语音管理] 索引文件损坏，将重新扫描: {e}")

        # 索引不存在或损坏 → 重新扫描
        await self._scan_voices()
        logger.info(f"[Echo of Theresia] 扫描完成，共 {len(self.voices)} 条语音")

    async def _scan_voices(self) -> None:
        logger.info(f"[语音管理] 开始扫描目录: {self.voice_dir}")
        
        if not os.path.exists(self.voice_dir):
            logger.warning(f"[语音管理] 语音目录不存在: {self.voice_dir}")
            return
        
        # 列出目录内容用于调试
        try:
            content = os.listdir(self.voice_dir)
            logger.info(f"[语音管理] voices 目录内容: {content}")
        except Exception as e:
            logger.error(f"[语音管理] 无法读取 voices 目录: {e}")
            return

        found_files = 0
        for root, dirs, files in os.walk(self.voice_dir):
            logger.info(f"[语音管理] 遍历子目录: {root}")
            logger.info(f"[语音管理] 当前目录文件: {files}")
            
            for file in files:
                # 支持大小写后缀
                if file.lower().endswith((".mp3", ".wav", ".ogg", ".m4a")) and file != "index.json":
                    found_files += 1
                    file_path = os.path.join(root, file)
                    # 相对插件根目录的路径（AstrBot Record 支持）
                    rel_path = os.path.relpath(file_path, self.base_dir)
                    logger.info(f"[语音管理] 发现语音文件: {file} -> 相对路径: {rel_path}")
                    
                    filename_no_ext = os.path.splitext(file)[0]
                    tags = self._extract_tags(filename_no_ext)
                    tags.append("theresia")  # 通用标签
                    
                    quality = self._detect_quality(file_path)
                    
                    self.voices[rel_path] = {
                        "path": rel_path,
                        "filename": file,
                        "tags": list(set(tags)),  # 去重
                        "size": os.path.getsize(file_path),
                        "quality": quality
                    }
                    self.tags.update(tags)

        logger.info(f"[语音管理] 扫描结束，共发现 {found_files} 个有效语音文件")

        if found_files > 0:
            self._save_index()
            logger.info(f"[语音管理] 已保存索引到: {self.index_file}")
        else:
            logger.warning("[语音管理] 未发现任何语音文件，索引未保存")

    def _extract_tags(self, filename: str) -> List[str]:
        tags = []
        # 英文格式：theresia_greeting_01 → greeting
        if "_" in filename:
            parts = filename.lower().split("_")
            for part in parts[1:]:
                if part and part not in ("01", "02", "1", "2", "theresia"):
                    tags.append(part)
        
        # 中文标签提取
        chinese = re.findall(r'[\u4e00-\u9fa5]+', filename)
        tags.extend(chinese)
        
        # 清理数字后的干净名称
        clean = re.sub(r'\d+', '', filename).strip("_ -.")
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
            logger.info(f"[语音管理] 索引保存成功: {self.index_file}")
        except Exception as e:
            logger.error(f"[语音管理] 保存索引失败: {e}")

    def get_voice(self, tag: str = None) -> str:
        if not self.voices:
            logger.info("[语音管理] 无可用语音（voices 字典为空）")
            return ""
        
        candidates = []
        for rel_path, info in self.voices.items():
            tags_lower = [t.lower() for t in info.get("tags", [])]
            if tag is None or tag.lower() in tags_lower:
                candidates.append(rel_path)
        
        if not candidates:
            logger.info(f"[语音管理] 无匹配标签 '{tag}' 的语音")
            return ""
        
        selected = random.choice(candidates)
        logger.info(f"[语音管理] 选中语音: {selected}")
        return selected

    def get_tags(self) -> List[str]:
        return sorted(list(self.tags))

    def get_voice_count(self, tag: str = None) -> int:
        if tag is None:
            return len(self.voices)
        count = sum(1 for info in self.voices.values() if tag.lower() in [t.lower() for t in info.get("tags", [])])
        return count

    async def update_voices(self) -> None:
        """手动触发重新扫描"""
        logger.info("[语音管理] 手动更新语音资源...")
        await self._scan_voices()