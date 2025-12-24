

<div align="center">

# 👑 Echo of Theresia  
### 明日方舟 · 特雷西娅语音插件

[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-purple?style=flat-square)](https://github.com/Soulter/AstrBot)
[![Version](https://img.shields.io/badge/Version-2.2.0-pink?style=flat-square)](https://github.com/riceshowerX/Echo-of-Theresia)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Arknights](https://img.shields.io/badge/Arknights-Theresia-black?style=flat-square)](https://ak.hypergryph.com/)

*“博士，夜已经很深了……还在工作吗？我会陪着你，但也希望你能照顾好自己。”*

[功能特性](#-功能特性--features) • [安装指南](#-安装方法--installation) • [语音列表](#-收录语音--voice-list) • [配置说明](#-配置说明--configuration)

</div>

---

## 📖 简介 | Introduction

**Echo of Theresia** 是为 **AstrBot** 打造的高拟真角色语音插件。

v2.2 版本引入了 **拟人化算法**，旨在通过情感惯性与自适应决策系统，完美适配官方语音包的每一句台词，还原角色“温柔、包容”的性格特质。

---

## ✨ 功能特性 | Features

| 核心算法 | 详细说明 |
| :--- | :--- |
| 🧠 **情感惯性引擎 (EI)** | 模拟真实情绪延续性。如果检测到用户情绪低落，会在一定时间内保持“安慰/陪伴”模式，不会突兀地切换语气。 |
| ⚡ **自适应决策 (ACD)** | 动态调整响应速度。普通闲聊保持 15s 冷却；检测到高危情绪（如“救命/痛苦”）时冷却缩短至 5s，实现“紧急秒回”。 |
| 🎭 **像素级语义映射** | 针对官方语音包进行了逐句解析。能精准识别“害怕”并回复“*别怕，我在*”（选中干员2）；识别“难过”并回复“*别哭...*”（作战中4）。 |
| 🌙 **理智护航** | 深夜（默认 01:00-05:00）互动时，优先触发“闲置”语音进行劝睡。 |
| 🎲 **动态熵减去重** | 播放次数越多的语音权重越低，保证语音随机性；内置短期记忆屏蔽，拒绝复读机。 |
| ⏰ **拟人化定时任务** | **时间抖动**：定时发送时引入随机延迟，模拟真人操作。<br>**断点补偿**：若因掉线错过时间，重启后自动补发。<br>**多态分发**：多群环境下，每个群收到的语音内容可能不同。 |

---

## 🚀 安装方法 | Installation

### 前置要求
请确保系统已安装 **ffmpeg**，否则无法发送语音。

### 方式一：GitHub 仓库安装（推荐）
```
https://github.com/riceshowerX/Echo-of-Theresia
```

### 方式二：上传 ZIP
1. 点击仓库首页 → **Download ZIP**  
2. 在 AstrBot 面板 → 插件管理 → 上传插件  
3. 重载插件或重启 AstrBot

> **提示**：安装完成后建议发送指令 `/theresia update` 以刷新语音索引。

---

## 📂 收录语音 | Voice List

插件核心逻辑已针对以下 **官方语音** 进行了深度适配与情感绑定：

| 语音标题 | 情感标签 | 触发场景示例 |
| :--- | :--- | :--- |
| **闲置** | sanity | "累了"、"想睡觉"、深夜互动 |
| **选中干员2** | comfort | "我好怕"、"救命" |
| **作战中4** | dont_cry | "我好难过"、"想哭"、"破防了" |
| **部署2** | company | "好孤独"、"没人理我" |
| **信赖触摸** | trust/love | "喜欢你"、"老婆" |
| **行动失败** | fail | "搞砸了"、"输了" |
| **戳一下** | poke | 戳一戳头像 |
| **问候** | morning | "早上好"、"早安" |
| **信赖提升后交谈3** | forgive | "我好内疚"、"对不起" |
| **晋升后交谈2** | hope | "绝望"、"未来" |

*以及：任命助理、交谈1/2/3、晋升后交谈1、观看作战记录、精英化晋升1/2、编入队伍、任命队长、行动出发、行动开始、选中干员1、部署1、作战中1/2/3、完成高难行动、3星/非3星结束行动、进驻设施、标题、新年祝福、生日、周年庆典等全量语音。*

---

## 💬 交互指南 | Interaction Guide

### 🟢 唤醒式交互
只有包含触发词（默认：特雷西娅 / Theresia）时才会触发语音。

**场景演示：**

*   **用户**：「特雷西娅，方案又被毙了，好痛苦...」  
    *   **判定**：`dont_cry` (高优先级) + `ACD` (紧急)  
    *   **回应**：“*别哭，很快就结束了。*”

*   **用户**：「特雷西娅，今晚好安静。」  
    *   **判定**：`lonely`  
    *   **回应**：“*我在这儿呢，我会一直陪着你。*”

---

## ⚙️ 配置说明 | Configuration

建议在 AstrBot Web 面板修改 `config.json`。

| 配置项 | 说明 |
| :--- | :--- |
| `features.mood_inertia` | **情感惯性 (EI)** 开关 |
| `features.sanity_mode` | **理智护航** 开关 |
| `params.high_emotion_cd` | **紧急冷却**：高情绪下的响应间隔（默认 5s） |
| `schedule.frequency` | **定时频率**：daily / weekly / hourly / once |
| `schedule.target_sessions` | **目标会话**：接收定时语音的群号/私聊ID |

---

## 📢 免责声明与版权声明 | Disclaimer & Credits

本插件为粉丝自制开源项目，仅供学习与交流使用，**严禁用于任何商业用途**。

### 语音资源来源  
本插件使用的语音文件均来自 **《明日方舟》官方语音包**，由玩家从 **PRTS Wiki** 下载整理。  
插件本身 **不生成、不合成、不修改** 任何语音，仅负责播放与管理。

> 本网站（PRTS Wiki）由《明日方舟》游戏爱好者使用免费开源的 MediaWiki 程序制作。  
> 网站所涉及的公司名称、商标、产品等均为其各自所有者的资产，仅供识别。  
> 网站内使用的游戏图片、动画、音频、文本原文，其版权属于 **上海鹰角网络科技有限公司** 及其关联公司。

---

<div align="center">
Made with ❤️ for Theresia & Doctor  
</div>