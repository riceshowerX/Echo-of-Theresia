# voice_manager.py
import os
import json
import random
from astrbot.api import logger

class VoiceManager:
    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
        # 使用插件目录下的 voices 文件夹绝对路径
        self.voices_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "voices"))
        self.index_path = os.path.join(self.voices_dir, "index.json")
        self.voices = {}      # tag -> [absolute_path1, ...]
        self.all_voices = []  # 所有语音的绝对路径列表

    async def load_voices(self):
        await self.update_voices()

    async def update_voices(self):
        logger.info("[语音管理] 手动更新语音资源...")

        if not os.path.exists(self.voices_dir):
            os.makedirs(self.voices_dir)

        files = os.listdir(self.voices_dir)
        logger.info(f"[语音管理] voices 目录内容: {files}")

        self.voices.clear()
        self.all_voices.clear()

        # 扫描音频文件
        for file in files:
            if file.lower().endswith(('.wav', '.mp3', '.ogg', '.m4a', '.silk')):
                full_path = os.path.abspath(os.path.join(self.voices_dir, file))
                self.all_voices.append(full_path)
                logger.info(f"[语音管理] 发现语音: {full_path}")

        # 加载 index.json（支持标签分组）
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
                for tag, file_list in index_data.items():
                    tagged_paths = []
                    for filename in file_list:
                        path = os.path.abspath(os.path.join(self.voices_dir, filename))
                        if os.path.exists(path):
                            tagged_paths.append(path)
                        else:
                            logger.warning(f"[语音管理] index.json 引用文件不存在: {filename}")
                    if tagged_paths:
                        self.voices[tag] = tagged_paths
            except Exception as e:
                logger.error(f"[语音管理] 加载 index.json 失败: {e}")

        # 若无标签分组，至少创建一个默认组
        if not self.voices and self.all_voices:
            self.voices[""] = self.all_voices[:]

        logger.info(f"[语音管理] 扫描结束，共发现 {len(self.all_voices)} 个有效语音文件")

    def get_voice(self, tag: str = None):
        if tag and tag in self.voices and self.voices[tag]:
            return random.choice(self.voices[tag])
        elif self.all_voices:
            return random.choice(self.all_voices)
        return None

    def get_tags(self):
        return [t for t in self.voices.keys() if t]  # 排除空字符串标签

    def get_voice_count(self, tag: str = None):
        if tag and tag in self.voices:
            return len(self.voices[tag])
        return len(self.all_voices)

    def get_total_count(self):
        return len(self.all_voices)