
<div align="center">

# 👑 Echo of Theresia
### 明日方舟 · 特雷西娅语音插件

[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-purple?style=flat-square)](https://github.com/Soulter/AstrBot)
[![Version](https://img.shields.io/badge/Version-1.0.5-pink?style=flat-square)](https://github.com/riceshowerX/Echo-of-Theresia)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Arknights](https://img.shields.io/badge/Arknights-Theresia-black?style=flat-square)](https://ak.hypergryph.com/)

*“博士，工作辛苦了。稍微休息一下吧，我会一直在这里陪着你的。”*

[功能特性](#-功能特性) • [安装指南](#-安装方法) • [指令列表](#-使用命令) • [配置说明](#-配置说明)

</div>

---

## 📖 简介 | Introduction

**Echo of Theresia** 是为 **AstrBot** 量身打造的角色语音插件。
它采用了全新的架构设计，完美适配 AstrBot (2025) 标准，支持 **WebUI 可视化配置**、**热重载** 以及 **智能标签识别**。

无论是日常的关键词触发，还是准时的早安问候，特雷西娅都会用她温柔的声音回应你的期待。

## ✨ 功能特性 | Features

| 功能模块 | 详细说明 |
| :--- | :--- |
| 🛡️ **智能防冲突** | 独家算法优化，彻底解决「关键词触发」与「指令输入」的冲突问题。 |
| 💬 **自然交互** | 聊天中自然提到「特雷西娅」即可触发随机语音，无需刻意输入指令。 |
| 🕒 **精准定时** | 支持 **每日/每周/每小时/仅一次** 四种频率，支持配置热更新（无需重启）。 |
| 🏷️ **智能标签** | 自动解析文件名中的中文和下划线生成标签，文件管理从未如此简单。 |
| ⚙️ **可视化配置** | 提供 `config_schema.json`，支持在 AstrBot Web 管理面板直接修改设置。 |
| 🔄 **零停机更新** | 放入新语音文件后，执行 update 指令即可实时生效。 |

---

## 🚀 安装方法 | Installation

### 前置要求
请确保服务器/本地环境已安装 **ffmpeg**，否则无法发送语音消息。

### 方式一：通过 GitHub 仓库链接安装（推荐）

1. 打开 AstrBot 管理面板或控制台。
2. 找到 **插件管理** -> **安装插件**。
3. 在「仓库链接」处输入以下地址并安装：
   ```
   https://github.com/riceshowerX/Echo-of-Theresia
   ```

### 方式二：上传 ZIP 文件安装

1. 访问本仓库首页，点击 **Code** -> **Download ZIP**。
2. 打开 AstrBot Web 管理面板。
3. 进入 **插件管理**，点击 **上传插件**，选择下载好的 ZIP 文件。
4. 安装完成后，请点击 **重载插件** 或重启 AstrBot。

---

## 🎵 资源准备 | Resources

本插件不自带语音文件，需要您自行准备。

### 1. 存放位置
安装完成后，请将 `.mp3`, `.wav`, `.ogg`, `.m4a` 等音频文件放入以下目录：
```text
data/plugins/echo_of_theresia/data/voices/
```

### 2. 命名与标签 (Smart Tagging)
插件会自动识别文件名中的 **中文** 和 **下划线分隔词** 作为标签。

| 文件名示例 | 自动识别的标签 | 触发指令示例 |
| :--- | :--- | :--- |
| `Morning_Call.mp3` | `morning`, `call` | `/theresia voice morning` |
| `问候_早安.wav` | `问候`, `早安` | `/theresia voice 早安` |
| `Battle_Start_01.mp3` | `battle`, `start` | `/theresia voice battle` |
| `Theresia_Pure.mp3` | `pure` | `/theresia voice pure` |

> **提示**：文件名越规范，点播越精准。添加文件后请务必发送 `/theresia update` 刷新索引。

---

## 🎮 使用命令 | Commands

插件采用单一入口设计，主指令默认为 `/theresia`。

| 命令 | 参数 | 功能描述 |
| :--- | :--- | :--- |
| `/theresia` | - | 显示插件菜单与状态 |
| `/theresia help` | - | 查看详细帮助文档 |
| `/theresia voice` | `[标签]` | 发送语音。不填则全随机，填标签则发送指定类型 |
| `/theresia tags` | - | 查看当前所有可用标签及语音数量 |
| `/theresia update` | - | **热更新**：重新扫描语音库并重建索引 |
| `/theresia set_target` | - | **定时**：将当前群/会话设为定时推送目标 |
| `/theresia unset_target` | - | **定时**：取消当前会话的推送 |
| `/theresia enable` | - | 启用插件功能 |
| `/theresia disable` | - | 禁用插件功能 |

---

## ⚙️ 配置说明 | Configuration

得益于 `config_schema.json` 的加入，您可以在 AstrBot 的 **Web 管理面板** -> **插件配置** 中直接修改，无需编辑文件。

### 核心配置项详解

#### 1. 基础设置
*   **指令前缀 (`command.prefix`)**: 默认为 `/theresia`。
*   **触发关键词 (`command.keywords`)**: 默认为 `["特雷西娅", "特蕾西娅", "Theresia"]`。

#### 2. 定时任务 (`schedule.*`)
*   **启用 (`schedule.enabled`)**: 总开关。
*   **时间 (`schedule.time`)**: 24小时制，如 `08:00`。
*   **频率 (`schedule.frequency`)**:
    *   `daily`: 每天固定时间发送（最常用）。
    *   `weekly`: 每周发送一次。
    *   `hourly`: 每小时整点发送。
    *   `once`: **仅发送一次**（发送后自动停止，适合测试或单次提醒）。
*   **标签限制 (`schedule.voice_tags`)**: 指定定时任务只能播放哪些标签的语音（例如 `["早安", "起床"]`）。留空则随机播放所有。

---

## 📂 目录结构

```text
echo_of_theresia/
├── main.py              # 核心逻辑入口
├── voice_manager.py     # 资源索引与缓存管理
├── scheduler.py         # 异步定时任务调度器
├── metadata.yaml        # 插件元数据
├── config_schema.json   # WebUI 配置定义
└── data/
    └── voices/          # [在此放入语音文件]
```

## ⚠️ 常见问题

1.  **Q: 为什么定时任务没反应？**
    *   A: 请检查三点：1. 插件是否启用；2. `schedule.enabled` 是否开启；3. 是否使用了 `/theresia set_target` 设置了目标群。
2.  **Q: 修改了配置需要重启吗？**
    *   A: **不需要**。本插件支持热重载，修改配置或添加文件后，系统会在 30 秒内自动应用变更。
3.  **Q: 关键词触发了但没声音？**
    *   A: 请确保您安装了 **ffmpeg**，且 `data/voices` 目录下有有效的音频文件。

## 📄 更新日志

#### v1.0.5 (Latest)
- **重构**: 严格适配 AstrBot 核心 API，使用标准 `Star` 基类。
- **新增**: 完整的 WebUI 配置支持 (`config_schema.json`)。
- **优化**: 定时任务支持 `once` 模式与热更新机制。
- **修复**: 解决了指令参数被误识别为关键词的 Bug，修复了导入兼容性问题。

## 🤝 贡献与反馈

欢迎提交 [Issue](https://github.com/riceshowerX/Echo-of-Theresia/issues) 或 Pull Request 帮助特雷西娅变得更完美。

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE) 开源。

---
<div align="center">
Made with ❤️ for Theresia & Doctor
</div>