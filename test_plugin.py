#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
插件加载测试脚本
"""

import sys
import os

# 添加插件目录到Python路径
plugin_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, plugin_dir)

try:
    # 尝试导入插件
    from main import TheresiaVoicePlugin
    print("✅ 插件导入成功")
    
    # 检查插件类是否存在
    if hasattr(TheresiaVoicePlugin, 'on_load'):
        print("✅ 插件类包含on_load方法")
    
    # 检查语音管理器
    from voice_manager import VoiceManager
    print("✅ VoiceManager导入成功")
    
    # 检查调度器
    from scheduler import VoiceScheduler
    print("✅ VoiceScheduler导入成功")
    
    # 检查命令处理器
    from command_handler import CommandHandler
    print("✅ CommandHandler导入成功")
    
    # 检查配置管理
    from config import Config
    print("✅ Config导入成功")
    
    print("\n测试完成：插件结构正确，可以正常加载")
    
except ImportError as e:
    print(f"❌ 插件导入失败: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ 测试过程中出现错误: {e}")
    sys.exit(1)