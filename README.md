# Echo of Theresia - 明日方舟特雷西娅语音插件

> **开发测试中** - Echo of Theresia

## 📖 插件介绍

AstrBot 明日方舟特雷西娅角色语音插件，支持定时发送和对话触发功能，让特雷西娅的声音回荡在您的聊天环境中。

## ✨ 功能特性

### 🕒 定时发送功能
- ✅ 支持自定义发送时间和频率（每日、每周、每小时）
- ✅ 支持按标签筛选语音范围
- ✅ 支持随机或顺序发送模式

### 💬 对话触发功能
- ✅ 指令触发：通过特定命令发送语音
- ✅ 关键词触发：包含指定关键词自动发送
- ✅ 支持按标签发送特定类型语音

### 🎵 语音资源管理
- ✅ 支持 MP3、WAV、OGG 等多种音频格式
- ✅ 自动扫描和索引语音资源
- ✅ 支持语音资源更新
- ✅ 按标签分类管理

### ⚙️ 配置管理
- ✅ 支持运行时配置修改
- ✅ 配置项自动持久化
- ✅ 支持配置更新

## 🚀 安装方法

### 1. 手动安装
将插件目录 `Echo-of-Theresia` 复制到 AstrBot 的插件目录中：

```bash
# 假设 AstrBot 安装在当前目录
cp -r Echo-of-Theresia ./data/plugins/
```

### 2. 重启 AstrBot
重启 AstrBot 服务，插件将自动加载。

## 📋 使用命令

### 核心命令
| 命令 | 描述 |
|------|------|
| `/theresia enable` | 启用插件 |
| `/theresia disable` | 禁用插件 |
| `/theresia config` | 查看配置 |
| `/theresia set <config> <value>` | 设置配置 |
| `/theresia voice [tag]` | 发送随机语音 |
| `/theresia tags` | 查看可用标签 |
| `/theresia update` | 更新语音资源 |
| `/theresia help` | 显示帮助信息 |

### 配置示例
```
/theresia set schedule.enabled true
/theresia set schedule.time 09:00
/theresia set schedule.frequency daily
/theresia set voice.quality high
/theresia set schedule.voice_tags greeting,story
```

## ⚙️ 配置说明

### 配置文件
插件配置文件位于：`data/config/echo_of_theresia_config.json`

### 配置项

| 配置项 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `enabled` | bool | `true` | 插件启用状态 |
| `schedule.enabled` | bool | `false` | 定时发送开关 |
| `schedule.time` | string | `08:00` | 发送时间 |
| `schedule.frequency` | string | `daily` | 发送频率 |
| `schedule.voice_tags` | array | `[]` | 语音标签 |
| `command.prefix` | string | `/theresia` | 命令前缀 |
| `command.keywords` | array | `["特雷西娅", "特蕾西娅", "Theresia"]` | 触发关键词 |
| `voice.quality` | string | `high` | 语音质量 |
| `voice.default_tag` | string | `""` | 默认标签 |

## 🎵 语音资源管理

### 1. 添加语音文件
将语音文件复制到 `data/plugins/Echo-of-Theresia/data/voices/` 目录中，支持以下格式：
- MP3
- WAV
- OGG

### 2. 语音文件命名规范
建议使用以下命名规范：
```
theresia_greeting_01.mp3
交谈1.wav
任命助理.wav
```

### 3. 更新语音索引
添加语音文件后，使用以下命令更新索引：
```
/theresia update
```

## 🎯 触发方式

### 1. 指令触发
```
/theresia voice      # 发送随机语音
/theresia voice greeting  # 发送问候类语音
```

### 2. 关键词触发
当消息中包含以下关键词时，自动发送语音：
- 特雷西娅
- 特蕾西娅
- Theresia

## 📊 开发状态

| 项目 | 状态 | 描述 |
|------|------|------|
| 当前版本 | v1.0.0 | 初始版本 |
| 开发阶段 | 测试中 | 基本功能已实现 |
| 稳定性 | 基本稳定 | 可能存在少量bug |
| 功能完成度 | 90% | 核心功能已实现 |

## ⚠️ 注意事项

1. 本插件处于开发测试阶段，可能存在不稳定因素
2. 语音资源需自行准备，建议使用合法获取的资源
3. 定时相关配置依赖系统时间的准确性
4. 关键词触发可能会在某些情况下误触发

## 📁 插件结构

```
Echo-of-Theresia/
├── main.py                 # 插件主入口
├── metadata.yaml           # 插件元数据
├── _conf_schema.json       # 配置定义
├── voice_manager.py        # 语音资源管理
├── scheduler.py            # 定时任务管理
├── data/
│   └── voices/             # 语音文件存储
├── test_plugin.py          # 测试脚本
└── README.md              # 使用说明文档
```

## 🛠️ 开发说明

### 开发环境
- Python 3.8+
- AstrBot 最新版本

### 开发流程
1. 克隆插件仓库
2. 安装依赖
3. 配置开发环境
4. 开发功能
5. 测试插件
6. 提交代码

### 插件注册
使用 `@register` 装饰器注册插件：
```python
@register(
    name="astrbot_plugin_theresia_voice",
    author="AstrBot Dev",
    description="明日方舟特雷西娅角色语音插件",
    version="1.0.0",
    repo=""
)
class TheresiaVoicePlugin(Star):
    pass
```

### 指令注册
使用 `@filter.command` 装饰器注册指令：
```python
@filter.command("voice")
async def send_voice(self, event: AstrMessageEvent, tag: str = ""):
    # 指令实现
    pass
```

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 或 Pull Request 来帮助改进插件！

---

> **提示**：由于插件处于开发测试阶段，建议定期查看更新，以获取最新的功能和修复。
