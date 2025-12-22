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
    
    def __init__(self, config):
        self.config = config
        self.voice_dir = os.path.join(os.path.dirname(__file__), "data", "voices")
        self.voice_index_file = os.path.join(self.voice_dir, "index.json")
        self.voices = {}
        self.tags = set()
    
    def load_voices(self) -> None:
        """加载语音资源"""
        self.voices = {}
        self.tags = set()
        
        # 如果索引文件存在，加载索引
        if os.path.exists(self.voice_index_file):
            try:
                with open(self.voice_index_file, "r", encoding="utf-8") as f:
                    self.voices = json.load(f)
                    # 提取所有标签
                    for voice_info in self.voices.values():
                        for tag in voice_info.get("tags", []):
                            self.tags.add(tag)
                return
            except Exception as e:
                print(f"加载语音索引失败: {e}")
        
        # 否则扫描语音文件目录
        self._scan_voice_files()
    
    def _scan_voice_files(self) -> None:
        """扫描语音文件目录"""
        for root, dirs, files in os.walk(self.voice_dir):
            for file in files:
                if file.endswith((".mp3", ".wav", ".ogg")) and file != "index.json":
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.voice_dir)
                    
                    # 从文件名提取标签（示例：theresia_greeting_01.mp3 -> ["greeting"]）
                    filename = os.path.splitext(file)[0]
                    tags = []
                    if "_" in filename:
                        # 假设文件名格式为：角色名_标签_序号
                        parts = filename.split("_")
                        if len(parts) >= 3:
                            tags.append(parts[1])
                    
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
    
    def _save_index(self) -> None:
        """保存语音索引"""
        try:
            with open(self.voice_index_file, "w", encoding="utf-8") as f:
                json.dump(self.voices, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存语音索引失败: {e}")
    
    def get_voice(self, tag: str = "") -> str:
        """获取随机语音文件路径"""
        # 过滤符合条件的语音
        filtered_voices = []
        for voice_path, voice_info in self.voices.items():
            if not tag or tag in voice_info.get("tags", []):
                # 检查质量要求
                if voice_info.get("quality") >= self.config.get("voice.quality", "high"):
                    filtered_voices.append(voice_path)
        
        if not filtered_voices:
            return ""
        
        # 随机选择一个
        selected = random.choice(filtered_voices)
        return os.path.join(self.voice_dir, selected)
    
    def get_tags(self) -> List[str]:
        """获取所有可用标签"""
        return sorted(list(self.tags))
    
    def add_voice(self, file_path: str, tags: List[str] = []) -> bool:
        """添加语音文件"""
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
