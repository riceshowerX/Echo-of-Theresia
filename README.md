# AstrBot Echo of Theresia 插件

## 插件介绍
这是一个AstrBot插件，实现了明日方舟特雷西娅角色语音的定时发送和对话触发功能，命名为"Echo of Theresia"（特雷西娅的回响）。

## 功能特性

### 1. 定时发送功能
- 支持自定义发送时间
- 支持多种发送频率（每日、每周、每小时）
- 支持按标签筛选语音范围
- 支持随机或顺序发送模式

### 2. 对话触发功能
- 指令触发：通过特定命令发送语音
- 关键词触发：包含指定关键词自动发送
- 支持按标签发送特定类型语音

### 3. 语音资源管理
- 支持MP3、WAV、OGG等多种音频格式
- 自动扫描和索引语音资源
- 支持语音资源更新
- 按标签分类管理

### 4. 配置管理
- 支持运行时配置修改
- 提供友好的配置命令
- 配置文件自动保存

## 安装方法

### 1. 手动安装
将插件目录 `theresia_voice` 复制到 AstrBot 的插件目录中：

```bash
# 假设AstrBot安装在当前目录
cp -r theresia_voice ./data/plugins/
```

### 2. 重启AstrBot
重启AstrBot服务，插件将自动加载。

## 配置方法

### 1. 配置文件
插件配置文件位于：`data/plugins/theresia_voice/data/config.json`

默认配置：
```json
{
    "enabled": true,
    "schedule": {
        "enabled": false,
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
```

### 2. 命令配置
通过聊天命令可以实时修改配置：

```
/theresia set <配置项> <值>
```

例如：
```
/theresia set schedule.enabled true
/theresia set schedule.time 09:30
/theresia set schedule.frequency weekly
/theresia set schedule.voice_tags greeting,story
```

## 使用命令

| 命令 | 描述 |
|------|------|
| `/theresia` | 显示帮助信息 |
| `/theresia enable` | 启用插件 |
| `/theresia disable` | 禁用插件 |
| `/theresia config` | 查看当前配置 |
| `/theresia set <config> <value>` | 设置配置项 |
| `/theresia voice [tag]` | 发送随机语音，可选指定标签 |
| `/theresia tags` | 查看可用语音标签 |
| `/theresia update` | 更新语音资源 |
| `/theresia help` | 显示帮助信息 |

## 语音资源管理

### 1. 添加语音文件
将语音文件复制到 `data/plugins/theresia_voice/data/voices/` 目录中，支持以下格式：
- MP3
- WAV
- OGG

### 2. 语音文件命名规范
建议使用以下命名规范：
```
theresia_<标签>_<序号>.<格式>
```

例如：
```
theresia_greeting_01.mp3
theresia_story_02.wav
```

### 3. 更新语音索引
添加语音文件后，使用以下命令更新索引：
```
/theresia update
```

## 触发方式

### 1. 指令触发
使用命令直接触发：
```
/theresia voice      # 发送随机语音
/theresia voice greeting  # 发送问候类语音
```

### 2. 关键词触发
当消息中包含配置的关键词时，自动发送语音：
- 特雷西娅
- 特蕾西娅
- Theresia

## 常见问题

### 1. 插件无法加载
- 检查插件目录是否正确
- 检查Python版本是否兼容
- 查看AstrBot日志获取详细错误信息

### 2. 语音发送失败
- 检查语音文件格式是否支持
- 检查语音文件是否损坏
- 检查AstrBot是否有发送语音的权限

### 3. 定时发送不生效
- 检查定时配置是否正确
- 检查插件是否已启用
- 检查系统时间是否准确

## 版本更新

### v1.0.0
- 初始版本
- 实现定时发送功能
- 实现对话触发功能
- 支持语音资源管理
- 提供配置管理功能

## 开发说明

### 插件结构
```
theresia_voice/
├── __init__.py          # 插件主入口
├── config.py            # 配置管理
├── voice_manager.py     # 语音资源管理
├── scheduler.py         # 定时任务管理
├── command_handler.py   # 命令处理
├── data/
│   ├── voices/          # 语音文件存储
│   └── config.json      # 插件配置文件
└── README.md            # 使用说明文档
```

### 开发环境
- Python 3.8+
- AstrBot最新版本

## 许可证

MIT License

## 联系方式

如有问题或建议，欢迎提交Issue或Pull Request。
