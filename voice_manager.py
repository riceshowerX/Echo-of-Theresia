# -*- coding: utf-8 -*-
"""
语音资源管理模块
"""

import os
import random
import json
from typing import List, Dict, Tuple

class VoiceManager:
    """语音资源管理类"""
    
    def __init__(self, plugin):
        self.plugin = plugin
        
        # 使用AstrBot推荐的数据存储位置
        # 语音资源作为大文件，存储在插件目录下的data目录
        self.voice_dir = os.path.join(os.path.dirname(__file__), "data", "voices")
        self.voice_index_file = os.path.join(self.voice_dir, "index.json")
        
        # 初始化语音数据
        self.voices = {}
        self.tags = set()
        
        # 插件实例，用于获取配置
        self._plugin = plugin
        
        # 配置缓存
        self._config_cache = {}
    
    def load_voices(self) -> None:
        """加载语音资源"""
        self.voices = {}
        self.tags = set()
        
        # 尝试从文件系统加载语音索引（兼容旧版本）
        if os.path.exists(self.voice_index_file):
            try:
                with open(self.voice_index_file, "r", encoding="utf-8") as f:
                    self.voices = json.load(f)
                    
                # 检查加载的语音数量，如果为空，执行扫描
                if not self.voices:
                    print("语音索引为空，执行扫描...")
                    self._scan_voice_files()
                else:
                    # 提取所有标签
                    for voice_info in self.voices.values():
                        for tag in voice_info.get("tags", []):
                            self.tags.add(tag)
                    return
            except Exception as e:
                print(f"加载语音索引失败: {e}")
        
        # 索引文件不存在或加载失败，扫描语音文件目录
        self._scan_voice_files()
    
    def _scan_voice_files(self) -> None:
        """扫描语音文件目录"""
        for root, dirs, files in os.walk(self.voice_dir):
            for file in files:
                if file.endswith((".mp3", ".wav", ".ogg")) and file != "index.json":
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.voice_dir)
                    
                    # 从文件名提取标签
                    filename = os.path.splitext(file)[0]
                    tags = []
                    
                    # 处理中文文件名（如：交谈1.wav -> ["交谈"]）
                    if "_" in filename:
                        # 处理英文命名格式：theresia_greeting_01.mp3 -> ["greeting"]
                        parts = filename.split("_")
                        if len(parts) >= 3:
                            tags.append(parts[1])
                    else:
                        # 处理中文命名格式：交谈1.wav -> ["交谈"]
                        # 提取中文标签（去掉数字和特殊字符）
                        import re
                        chinese_tag = re.sub(r'[^\u4e00-\u9fa5]', '', filename)
                        if chinese_tag:
                            tags.append(chinese_tag)
                        # 如果没有提取到中文标签，使用原文件名（去掉数字）
                        elif filename:
                            clean_tag = re.sub(r'\d+', '', filename)
                            if clean_tag:
                                tags.append(clean_tag)
                    
                    # 添加通用标签
                    tags.append("theresia")
                    
                    # 添加到语音列表
                    self.voices[rel_path] = {
                        "path": rel_path,
                        "filename": file,
                        "tags": tags,
                        "size": os.path.getsize(file_path),
                        "quality": self._detect_quality(file_path)
                    }
                    
                    # 更新标签集合
                    for tag in tags:
                        self.tags.add(tag)
        
        # 保存索引
        self._save_index()
    
    def _detect_quality(self, file_path: str) -> str:
        """检测语音质量"""
        # 简单实现：根据文件大小判断质量
        size = os.path.getsize(file_path)
        if size > 1024 * 1024:  # 大于1MB
            return "high"
        elif size > 512 * 1024:  # 大于512KB
            return "medium"
        else:
            return "low"
    
    def _is_quality_sufficient(self, current_quality: str, required_quality: str) -> bool:
        """检查语音质量是否满足要求"""
        quality_levels = {"low": 1, "medium": 2, "high": 3}
        current_level = quality_levels.get(current_quality, 1)
        required_level = quality_levels.get(required_quality, 1)
        return current_level >= required_level
    
    def _save_index(self) -> None:
        """保存语音索引"""
        try:
            # 使用文件系统存储语音索引（大文件适合文件系统存储）
            with open(self.voice_index_file, "w", encoding="utf-8") as f:
                json.dump(self.voices, f, ensure_ascii=False, indent=4)
            
            # 同时尝试使用AstrBot官方存储API存储语音索引（可选，用于备份）
            try:
                # 由于put_kv_data是异步方法，我们无法在同步方法中直接调用
                # 这里仅作为示例，实际使用中需要在异步上下文中调用
                # await self._plugin.put_kv_data("voice_index", self.voices)
                pass
            except Exception as e:
                print(f"使用官方存储API保存语音索引失败: {e}")
        except Exception as e:
            print(f"保存语音索引失败: {e}")
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """更新配置缓存"""
        self._config_cache = config
    
    def get_voice(self, tag: str = "") -> str:
        """获取随机语音文件路径"""
        # 过滤符合条件的语音
        filtered_voices = []
        for voice_path, voice_info in self.voices.items():
            if not tag or tag in voice_info.get("tags", []):
                # 获取语音质量要求，默认为"low"
                quality_requirement = self._config_cache.get("voice", {}).get("quality", "low")
                if self._is_quality_sufficient(voice_info.get("quality"), quality_requirement):
                    filtered_voices.append(voice_path)
        
        if not filtered_voices:
            return ""
        
        # 随机选择一个
        selected = random.choice(filtered_voices)
        return os.path.join(self.voice_dir, selected)
    
    def get_tags(self) -> List[str]:
        """获取所有可用标签"""
        return sorted(list(self.tags))
    
    def add_voice(self, file_path: str, tags: List[str] = None) -> bool:
        """添加语音文件"""
        if tags is None:
            tags = []
        if not os.path.exists(file_path):
            return False
        
        # 复制文件到语音目录
        filename = os.path.basename(file_path)
        dest_path = os.path.join(self.voice_dir, filename)
        
        try:
            import shutil
            shutil.copy2(file_path, dest_path)
            
            # 更新索引
            rel_path = os.path.relpath(dest_path, self.voice_dir)
            self.voices[rel_path] = {
                "path": rel_path,
                "filename": filename,
                "tags": tags,
                "size": os.path.getsize(dest_path),
                "quality": self._detect_quality(dest_path)
            }
            
            # 更新标签集合
            for tag in tags:
                self.tags.add(tag)
            
            self._save_index()
            return True
        except Exception as e:
            print(f"添加语音文件失败: {e}")
            return False
    
    def update_voices(self) -> bool:
        """更新语音资源"""
        # 重新扫描语音目录
        self._scan_voice_files()
        return True
    
    def get_voice_count(self, tag: str = "") -> int:
        """获取语音数量"""
        if not tag:
            return len(self.voices)
        
        count = 0
        for voice_info in self.voices.values():
            if tag in voice_info.get("tags", []):
                count += 1
        return count
