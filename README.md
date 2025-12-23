# Echo of Theresia - 明日方舟特雷西娅语音插件

<div align="center">
  <img src="logo.png" width="200" height="200" alt="Echo of Theresia Logo">
  
  <p>让特雷西娅的声音，永远回荡在你的聊天空间 ✨</p>
  
  <div>
    <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"></a>
    <a href="https://github.com/yourusername/Echo-of-Theresia"><img src="https://img.shields.io/github/stars/yourusername/Echo-of-Theresia?style=social" alt="GitHub Stars"></a>
    <img src="https://img.shields.io/badge/version-1.0.0-green.svg" alt="Version">
  </div>
</div>


## 📖 简介

Echo of Theresia 是一款专为明日方舟粉丝设计的语音插件，旨在通过特雷西娅的经典台词，为你的聊天互动增添更多乐趣与沉浸感。无论是关键词触发、手动指令调用，还是定时自动发送，都能让你随时聆听来自卡兹戴尔的温柔回响。


## ✨ 核心功能

- **关键词智能触发**  
  当聊天中出现「特雷西娅」「特蕾西娅」或「Theresia」等关键词时，自动随机播放一句语音，无缝融入对话场景。

- **手动指令调用**  
  通过 `/theresia` 前缀命令，可手动触发语音播放，支持指定标签筛选特定类型台词（如问候、剧情相关等）。

- **定时任务发送**  
  支持自定义定时发送规则（如每日早8点），向指定会话自动推送语音，让特雷西娅的声音成为日常的一部分。

- **智能标签系统**  
  自动从语音文件名提取标签（中文、关键词、_clean名称），精准匹配你的触发需求。


## 🚀 快速开始

### 安装步骤

1. 克隆仓库到本地
   ```bash
   git clone https://github.com/yourusername/Echo-of-Theresia.git
   cd Echo-of-Theresia
   ```

2. 安装依赖（根据实际环境补充）
   ```bash
   pip install -r requirements.txt
   ```

3. 启动插件并加载至你的聊天平台（如AstrBot等支持的环境）


### 基础使用

- **关键词触发**  
  在聊天中输入包含「特雷西娅」的语句，例如：  
  > "特雷西娅的理念真的很动人"  
  插件将自动响应并播放语音。

- **手动调用**  
  使用命令前缀触发：  
  ```
  /theresia  # 随机播放一句语音
  /theresia 问候  # 播放带「问候」标签的语音
  ```

- **定时发送设置**  
  在配置中启用定时任务，指定时间（如`08:00`）和频率（如`daily`），即可每日收到特雷西娅的晨间问候。


## ⚙️ 配置说明

核心配置项位于插件设置中，可根据需求自定义：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `enabled` | 是否启用插件 | `True` |
| `command.keywords` | 触发关键词列表 | `["特雷西娅", "特蕾西娅", "Theresia"]` |
| `command.prefix` | 手动指令前缀 | `/theresia` |
| `schedule.enabled` | 是否启用定时任务 | `False` |
| `schedule.time` | 定时发送时间 | `08:00` |
| `schedule.frequency` | 定时频率（daily/hourly等） | `daily` |
| `schedule.target_sessions` | 定时发送目标会话ID列表 | `[]` |


## 📜 许可证

本项目采用 [MIT 许可证](LICENSE) 开源，允许自由使用、修改和分发。


## 💬 反馈与贡献

如果发现BUG或有功能建议，欢迎提交 [Issue](https://github.com/yourusername/Echo-of-Theresia/issues) 或 Pull Request，让我们一起完善这个项目！

---

> 「为了卡兹戴尔的未来……」—— 特雷西娅