import re
from typing import Set, List, Dict, Optional
import random
import logging

logger = logging.getLogger(__name__)

class VoiceManager:
    def __init__(self, plugin):
        self.plugin = plugin
        self.voices = self._load_voices()  # 加载所有语音文件信息

    def _load_voices(self) -> List[Dict]:
        """加载所有语音文件并提取标签（实际实现需根据存储方式调整）"""
        voices = []
        # 假设语音文件存储在plugin_root/voices目录下
        voice_dir = self.plugin.plugin_root / "voices"
        if not voice_dir.exists():
            logger.warning("语音文件目录不存在：%s", voice_dir)
            return voices
        
        for file in voice_dir.glob("*.*"):
            if file.suffix in [".mp3", ".wav", ".ogg"]:  # 支持的音频格式
                tags = self._extract_tags(file.stem)  # 提取文件名中的标签
                voices.append({
                    "path": str(file),
                    "filename": file.name,
                    "tags": tags
                })
        logger.info(f"成功加载 {len(voices)} 个语音文件")
        return voices

    def _extract_tags(self, filename: str) -> Set[str]:
        """智能提取文件名中的标签（返回小写集合）"""
        tags = set()
        if not filename:
            return tags

        # 1. 下划线分割提取（处理类似"生日_问候_01"的命名）
        if "_" in filename:
            parts = filename.split("_")
            for part in parts:
                # 清理数字、常见分隔符（保留字母和中文）
                cleaned = re.sub(r'[\d\-.()_]+', '', part).strip()
                if cleaned and len(cleaned) >= 1:  # 允许单字标签
                    tags.add(cleaned.lower())

        # 2. 提取所有中文（支持单字和连续词语）
        chinese_chars = re.findall(r'[\u4e00-\u9fa5]', filename)  # 匹配单个汉字
        tags.update([char.lower() for char in chinese_chars if char])

        # 3. 整体清理后的文件名作为标签（去除所有特殊符号）
        clean_name = re.sub(r'[^\w\u4e00-\u9fa5]+', '', filename).strip()
        if clean_name and len(clean_name) >= 2:  # 至少2个字符避免过短标签
            tags.add(clean_name.lower())

        # 移除空值和重复项
        return {tag for tag in tags if tag}

    def get_matched_voice(self, target_tags: Optional[List[str]] = None) -> Optional[Dict]:
        """根据目标标签匹配语音，无匹配则随机返回"""
        target_tags = [tag.lower() for tag in (target_tags or [])]
        all_voices = self.voices.copy()
        
        if not all_voices:
            logger.error("没有可用的语音文件")
            return None

        # 筛选匹配标签的语音
        matched_voices = []
        for voice in all_voices:
            if any(tag in voice["tags"] for tag in target_tags):
                matched_voices.append(voice)

        if matched_voices:
            logger.debug(f"找到 {len(matched_voices)} 个匹配标签的语音")
            return random.choice(matched_voices)
        else:
            logger.warning(f"未找到匹配标签 {target_tags} 的语音，将随机选择")
            return random.choice(all_voices)