# -*- coding: utf-8 -*-
"""
语音资源管理模块 - 终极优化版
改进点：
- 使用 pathlib，更安全现代
- 每个语音文件缓存其专属标签，避免重复提取
- 索引结构更完整，支持快速查询
- 标签提取更智能灵活
- 去除无意义 async
- 性能显著提升（尤其语音数量 > 100 时）
"""

import os
import re
import json
import random
from pathlib import Path
from typing import List, Dict, Set

from astrbot.api import logger


class VoiceEntry:
    """单个语音条目"""
    def __init__(self, rel_path: str, tags: Set[str]):
        self.rel_path = rel_path
        self.tags = tags  # 小写集合，便于快速匹配


class VoiceManager:
    def __init__(self, plugin):
        self.plugin = plugin
        
        # 使用 Path，更优雅且跨平台
        self.base_dir = Path(__file__).parent.resolve()
        self.voice_dir = self.base_dir / "data" / "voices"
        self.index_file = self.voice_dir / "index.json"
        
        # 数据结构
        self.entries: List[VoiceEntry] = []  # 所有语音条目
        self.all_tags: Set[str] = set()      # 全局标签集合（用于 /tags 命令）

    def load_voices(self) -> None:
        """同步加载（实际为同步IO，移除无意义 async）"""
        logger.info("[Echo of Theresia] 正在加载语音资源...")
        logger.info(f"[语音管理] 语音目录: {self.voice_dir}")

        self.entries.clear()
        self.all_tags.clear()

        # 优先从索引加载
        if self.index_file.exists():
            try:
                data = json.loads(self.index_file.read_text(encoding="utf-8"))
                for item in data.get("entries", []):
                    entry = VoiceEntry(
                        rel_path=item["path"],
                        tags=set(item["tags"])
                    )
                    self.entries.append(entry)
                    self.all_tags.update(entry.tags)
                logger.info(f"[语音管理] 从索引加载 {len(self.entries)} 条语音")
                if self.entries:
                    return
            except Exception as e:
                logger.warning(f"[语音管理] 索引加载失败，将重新扫描: {e}")

        # 索引无效或为空，重新扫描
        self._scan_voices()
        logger.info(f"[语音管理] 加载完成，共 {len(self.entries)} 条语音")

    def _scan_voices(self) -> None:
        """扫描语音文件并构建索引"""
        if not self.voice_dir.exists():
            self.voice_dir.mkdir(parents=True, exist_ok=True)
            logger.warning(f"[语音管理] 语音目录不存在，已自动创建: {self.voice_dir}")
            return

        audio_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".silk"}
        files = [f for f in self.voice_dir.iterdir() 
                 if f.is_file() and f.suffix.lower() in audio_extensions and f.name != "index.json"]

        logger.info(f"[语音管理] 发现 {len(files)} 个音频文件")

        for file_path in files:
            rel_path = str(Path("data") / "voices" / file_path.name)  # 相对于插件根目录
            filename_no_ext = file_path.stem
            tags = self._extract_tags(filename_no_ext)
            tags.add("theresia")  # 默认标签

            entry = VoiceEntry(rel_path=rel_path, tags=tags)
            self.entries.append(entry)
            self.all_tags.update(tags)

        if self.entries:
            self._save_index()

    def _extract_tags(self, filename: str) -> Set[str]:
        """智能提取标签（返回小写 set）"""
        tags = set()

        # 1. 下划线分割（常见：生日_问候_01）
        if "_" in filename:
            parts = filename.split("_")
            for part in parts:
                cleaned = part.strip("0123456789 -.")
                if cleaned:
                    tags.add(cleaned.lower())

        # 2. 提取所有中文
        chinese_words = re.findall(r'[\u4e00-\u9fa5]+', filename)
        tags.update(chinese_words)

        # 3. 去掉数字、符号后的干净名称作为标签
        clean_name = re.sub(r'[\d_.\-()]+', ' ', filename).strip()
        if clean_name:
            tags.add(clean_name.lower())

        # 4. 移除空字符串
        return {t for t in tags if t}

    def _save_index(self) -> None:
        """保存完整索引"""
        data = {
            "entries": [
                {
                    "path": entry.rel_path,
                    "tags": sorted(list(entry.tags))  # 排序便于阅读
                }
                for entry in self.entries
            ],
            "total": len(self.entries),
            "generated_at": __import__('time').strftime("%Y-%m-%d %H:%M:%S")
        }
        try:
            self.index_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            logger.info(f"[语音管理] 索引已保存: {self.index_file}")
        except Exception as e:
            logger.error(f"[语音管理] 保存索引失败: {e}")

    def get_voice(self, tag: str | None = None) -> str | None:
        """获取随机语音相对路径"""
        if not self.entries:
            return None

        if tag is None:
            # 无标签：随机返回任意一个
            return random.choice(self.entries).rel_path

        tag_lower = tag.lower()
        candidates = [e for e in self.entries if tag_lower in e.tags]

        if not candidates:
            return None

        return random.choice(candidates).rel_path

    def get_tags(self) -> List[str]:
        """返回排序后的标签列表"""
        return sorted(self.all_tags)

    def get_voice_count(self, tag: str | None = None) -> int:
        """统计指定标签或总数"""
        if tag is None:
            return len(self.entries)

        tag_lower = tag.lower()
        return sum(1 for e in self.entries if tag_lower in e.tags)

    def update_voices(self) -> None:
        """手动触发重新扫描（同步）"""
        logger.info("[语音管理] 手动更新语音资源...")
        self._scan_voices()