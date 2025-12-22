# -*- coding: utf-8 -*-
"""
配置管理模块
"""

import json
import os
from typing import Dict, Any

class Config:
    """配置管理类"""
    
    def __init__(self):
        self.config_file = os.path.join(os.path.dirname(__file__), "data", "config.json")
        self.default_config = {
            "enabled": True,
            "schedule": {
                "enabled": False,
                "time": "08:00",
                "frequency": "daily",  # daily, weekly, hourly
                "voice_tags": []  # 空列表表示所有语音
            },
            "command": {
                "prefix": "/theresia",
                "keywords": ["特雷西娅", "特蕾西娅", "Theresia"]
            },
            "voice": {
                "quality": "high",  # high, medium, low
                "default_tag": ""
            }
        }
        self.config = self.default_config.copy()
    
    def load(self) -> None:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                self.config = self.default_config.copy()
        else:
            self.save()
    
    def save(self) -> None:
        """保存配置文件"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any) -> bool:
        """设置配置项"""
        keys = key.split(".")
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        self.save()
        return True
    
    def reset(self) -> None:
        """重置配置为默认值"""
        self.config = self.default_config.copy()
        self.save()
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self.config.copy()
