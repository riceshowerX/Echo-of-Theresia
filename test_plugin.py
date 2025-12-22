# -*- coding: utf-8 -*-
"""
特雷西娅语音插件测试脚本
测试插件的核心功能，包括语音资源管理、配置管理等
"""

import os
import sys
import json

# 添加插件目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 模拟AstrBot配置管理
class MockConfig:
    """模拟AstrBot配置管理"""
    def __init__(self):
        self.config = {
            "enabled": True,
            "schedule": {
                "enabled": False,
                "time": "08:00",
                "frequency": "daily",
                "voice_tags": []
            },
            "command": {
                "prefix": "/theresia",
                "keywords": ["特雷西娅", "特蕾西娅", "Theresia"]
            },
            "voice": {
                "quality": "high",
                "default_tag": ""
            }
        }
    
    def get_all_config(self):
        return self.config

# 模拟AstrBot插件实例
class MockPlugin:
    """模拟AstrBot插件实例"""
    def __init__(self):
        self.context = MockContext()
        self.name = "echo_of_theresia"

class MockContext:
    """模拟AstrBot上下文"""
    def __init__(self):
        self.config = MockConfig()

# 测试语音资源管理
def test_voice_manager():
    print("=== 测试语音资源管理 ===")
    
    from voice_manager import VoiceManager
    
    # 创建模拟插件实例
    plugin = MockPlugin()
    voice_manager = VoiceManager(plugin)
    
    # 测试加载语音资源
    voice_manager.load_voices()
    print(f"加载的语音数量: {len(voice_manager.voices)}")
    print(f"可用标签: {voice_manager.get_tags()}")
    
    # 测试获取语音
    voice_path = voice_manager.get_voice()
    print(f"随机语音路径: {voice_path}")
    
    # 测试按标签获取语音
    if voice_manager.get_tags():
        first_tag = voice_manager.get_tags()[0]
        voice_path_by_tag = voice_manager.get_voice(first_tag)
        print(f"按标签 '{first_tag}' 获取的语音: {voice_path_by_tag}")
    
    print("语音资源管理测试完成")

# 测试定时任务
def test_scheduler():
    print("\n=== 测试定时任务 ===")
    
    from scheduler import VoiceScheduler
    
    # 创建模拟插件实例
    plugin = MockPlugin()
    
    # 模拟VoiceManager
    class MockVoiceManager:
        def get_voice(self, tag=""):
            return "mock_voice_path.wav"
    
    voice_manager = MockVoiceManager()
    scheduler = VoiceScheduler(plugin, voice_manager)
    
    # 测试启动和停止定时任务
    scheduler.start()
    print(f"定时任务状态: {'运行中' if scheduler.running else '已停止'}")
    
    scheduler.stop()
    print(f"定时任务状态: {'运行中' if scheduler.running else '已停止'}")
    
    print("定时任务测试完成")

# 运行测试
if __name__ == "__main__":
    test_voice_manager()
    test_scheduler()
    print("\n所有测试完成!")
