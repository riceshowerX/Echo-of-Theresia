# -*- coding: utf-8 -*-
"""
语音资源管理模块 - 修复与增强版
修复：
- 解决 update_voices 导致的列表重复倍增 Bug
- 优化路径计算，使用 relative_to 替代硬编码
- 增强 update 逻辑，确保强制刷新
"""

import json
import random
import re
from pathlib import Path
from typing import List, Set, Optional

from astrbot.api import logger


class VoiceEntry:
    """单个语音条目"""
    __slots__ = ('rel_path', 'tags')  # 使用 slots 减少内存占用

    def __init__(self, rel_path: str, tags: Set[str]):
        self.rel_path = rel_path
        self.tags = tags  # 小写集合


class VoiceManager:
    def __init__(self, plugin):
        self.plugin = plugin
        
        # 基础路径定义
        self.base_dir = Path(__file__).parent.resolve()
        self.voice_dir = self.base_dir / "data" / "voices"
        self.index_file = self.voice_dir / "index.json"
        
        # 内存数据
        self.entries: List[VoiceEntry] = []
        self.all_tags: Set[str] = set()

    def load_voices(self) -> None:
        """
        初始化加载：优先读取索引文件以提高速度
        """
        logger.info("[Echo of Theresia] 正在初始化语音库...")
        
        # 确保清理旧数据
        self.entries.clear()
        self.all_tags.clear()

        # 1. 尝试加载索引
        if self.index_file.exists():
            try:
                content = self.index_file.read_text(encoding="utf-8")
                data = json.loads(content)
                
                # 校验索引版本或路径有效性（可选），这里直接加载
                for item in data.get("entries", []):
                    entry = VoiceEntry(
                        rel_path=item["path"],
                        tags=set(item["tags"])
                    )
                    self.entries.append(entry)
                    self.all_tags.update(entry.tags)
                
                logger.info(f"[语音管理] 索引命中！已加载 {len(self.entries)} 条语音数据")
                return # 索引加载成功直接返回
                
            except Exception as e:
                logger.warning(f"[语音管理] 索引文件损坏或读取失败: {e}，将转为全盘扫描")

        # 2. 索引不存在或加载失败，执行扫描
        self._scan_voices()

    def update_voices(self) -> None:
        """
        强制更新：忽略索引，重新扫描磁盘并生成新索引
        对应指令: /theresia update
        """
        logger.info("[语音管理] 正在执行强制全盘扫描...")
        # 【关键修复】必须先清空列表，否则 update 会导致数据倍增
        self.entries.clear()
        self.all_tags.clear()
        
        self._scan_voices()
        logger.info(f"[语音管理] 更新完成，当前共 {len(self.entries)} 条语音")

    def _scan_voices(self) -> None:
        """核心扫描逻辑"""
        if not self.voice_dir.exists():
            try:
                self.voice_dir.mkdir(parents=True, exist_ok=True)
                logger.warning(f"[语音管理] 目录不存在，已自动创建: {self.voice_dir}")
                # 创建后是空的，直接返回
                return
            except Exception as e:
                logger.error(f"[语音管理] 无法创建目录: {e}")
                return

        audio_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".silk", ".aac", ".flac"}
        
        # 遍历文件
        files = [
            f for f in self.voice_dir.iterdir() 
            if f.is_file() and f.suffix.lower() in audio_extensions
        ]

        logger.info(f"[语音管理] 扫描到 {len(files)} 个音频文件，正在解析元数据...")

        for file_path in files:
            # 【优化】动态计算相对路径，不依赖硬编码
            # 结果类似: data/voices/hello.mp3 (适配当前OS分隔符)
            try:
                rel_path_obj = file_path.relative_to(self.base_dir)
                rel_path = str(rel_path_obj)
            except ValueError:
                # 理论上不会发生，除非文件不在 base_dir 下
                rel_path = str(file_path.name)

            # 提取标签
            tags = self._extract_tags(file_path.stem)
            tags.add("theresia")  # 基础标签

            entry = VoiceEntry(rel_path=rel_path, tags=tags)
            self.entries.append(entry)
            self.all_tags.update(tags)

        # 扫描结束后保存新索引
        if self.entries:
            self._save_index()

    def _extract_tags(self, filename: str) -> Set[str]:
        """智能标签提取算法"""
        tags = set()
        
        # 预处理：转小写
        filename = filename.lower()

        # 1. 拆分下划线 (e.g. "ask_morning_01" -> "ask", "morning")
        parts = filename.split("_")
        for part in parts:
            # 去除纯数字和杂质
            cleaned = re.sub(r'^\d+|\d+$', '', part) 
            if len(cleaned) > 1: # 忽略单个字母
                tags.add(cleaned)

        # 2. 提取中文 (e.g. "特雷西娅_问候" -> "特雷西娅", "问候")
        chinese_words = re.findall(r'[\u4e00-\u9fa5]+', filename)
        tags.update(chinese_words)

        # 3. 完整清理名 (作为精确匹配备选)
        clean_full_name = re.sub(r'[_\-\d.]+', ' ', filename).strip()
        if clean_full_name:
            tags.add(clean_full_name)

        return tags

    def _save_index(self) -> None:
        """持久化索引到 JSON"""
        data = {
            "version": "1.0",
            "generated_at": str(import_time()), # 动态获取时间
            "entries": [
                {
                    "path": entry.rel_path,
                    "tags": sorted(list(entry.tags))
                }
                for entry in self.entries
            ]
        }
        try:
            # ensure_ascii=False 保证中文可读
            self.index_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            logger.debug(f"[语音管理] 索引缓存已写入: {self.index_file.name}")
        except Exception as e:
            logger.error(f"[语音管理] 索引保存失败: {e}")

    # ================= 对外接口 =================

    def get_voice(self, tag: Optional[str] = None) -> Optional[str]:
        """
        获取语音路径
        :param tag: 标签名称 (None 表示随机)
        :return: 相对路径 str 或 None
        """
        if not self.entries:
            return None

        if not tag:
            # 全随机
            return random.choice(self.entries).rel_path

        tag_lower = tag.lower()
        
        # 1. 精确匹配
        candidates = [e for e in self.entries if tag_lower in e.tags]
        
        # 2. 模糊匹配 (如果精确匹配没结果，尝试匹配文件名包含)
        if not candidates:
             candidates = [e for e in self.entries if tag_lower in str(Path(e.rel_path).stem).lower()]

        if not candidates:
            return None

        return random.choice(candidates).rel_path

    def get_tags(self) -> List[str]:
        """获取所有可用标签 (字母序)"""
        return sorted(list(self.all_tags))

    def get_voice_count(self, tag: Optional[str] = None) -> int:
        if not tag:
            return len(self.entries)
        tag_lower = tag.lower()
        return sum(1 for e in self.entries if tag_lower in e.tags)

# 辅助函数：避免顶层 import time 导致命名污染
def import_time():
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S")