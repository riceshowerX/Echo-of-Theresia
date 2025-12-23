
# Echo of Theresia - 明日方舟特雷西娅语音插件

> **稳定运行版** - Echo of Theresia v1.0.5

一个为 **AstrBot** 量身打造的特雷西娅角色语音插件，让特雷西娅的温柔声音随时陪伴你的聊天群。

## ✨ 功能特性

- 🕒 **定时发送**：每日/每周/每小时准时推送特雷西娅语音
- 💬 **关键词触发**：消息中提到「特雷西娅」即可随机播放语音
- 🎯 **指令播放**：支持按标签手动点播特定类型语音
- 📁 **自动管理**：开箱即用，自动扫描、索引语音文件
- 🔄 **热更新**：新增语音后一键刷新即可生效
- 📱 **全平台兼容**：QQ、Telegram、WebUI 等均可直接播放真实语音

## 🚀 安装方法

### 推荐方式：通过 GitHub 仓库直接安装

```bash
 https://github.com/riceshowerX/Echo-of-Theresia
```

### 或者手动下载安装
1. 访问仓库：https://github.com/riceshowerX/Echo-of-Theresia
2. 下载 ZIP 包并解压
3. 将解压得到的文件夹重命名为 `echo_of_theresia` 并放入 AstrBot 的插件目录：
   ```
   AstrBot/data/plugins/echo_of_theresia
   ```

安装完成后，重启 AstrBot 或在 Web 控制台点击 **重载插件** 即可。

## 📋 使用命令（前缀统一为 `/theresia`）

| 命令                          | 功能描述                              |
|-------------------------------|---------------------------------------|
| `/theresia`                   | 显示插件状态与简要命令列表            |
| `/theresia enable`            | 启用插件                              |
| `/theresia disable`           | 禁用插件                              |
| `/theresia voice`             | 播放一条随机语音（使用默认标签）      |
| `/theresia voice [标签]`      | 播放指定标签的随机语音（如 `/theresia voice 问候`） |
| `/theresia tags`              | 查看所有可用标签及语音数量            |
| `/theresia update`            | 重新扫描语音文件夹，刷新索引          |
| `/theresia set_target`        | 将当前会话设为定时发送目标            |
| `/theresia unset_target`      | 取消当前会话的定时发送                |
| `/theresia help`              | 显示完整帮助信息                      |

**关键词触发**：在普通消息中包含「特雷西娅」「特蕾西娅」「Theresia」即可自动播放随机语音（插件启用时有效）。

## 🎵 语音资源准备

1. 将语音文件放入插件目录：
   ```
   AstrBot/data/plugins/echo_of_theresia/data/voices/
   ```
2. 支持格式：`.mp3`、`.wav`、`.ogg`、`.m4a`

3. **推荐命名规范**（便于标签自动识别）：
   - `问候_早安.wav`
   - `生日_祝福.mp3`
   - `戳一下_互动.ogg`
   - `精英化二_升级.m4a`

   插件会自动从文件名中提取中文、下划线分隔词等作为标签。

4. 添加新语音后执行：
   ```
   /theresia update
   ```

## ⚙️ 定时发送配置（可选）

定时功能默认关闭，如需使用：

1. 先启用插件：`/theresia enable`
2. 设置当前群/私聊为目标：`/theresia set_target`
3. 在 Web 控制台或配置文件中开启并调整定时参数（推荐 Web 控制台更直观）

**主要定时配置项**：
- `schedule.enabled`：`true` / `false`
- `schedule.time`：发送时间（如 `"09:00"`）
- `schedule.frequency`：`"daily"`（每日） / `"weekly"`（每周） / `"hourly"`（每小时）
- `schedule.voice_tags`：限定标签数组，如 `["早安", "问候"]`

## 📁 插件目录结构

```
echo_of_theresia/
├── main.py              # 主入口
├── voice_manager.py     # 语音管理
├── scheduler.py         # 定时任务
├── data/
│   └── voices/          # ← 放语音文件的地方
└── README.md
```

## ⚠️ 注意事项

- 请使用合法来源的语音资源，尊重版权。
- 关键词触发已优化避免与 `/theresia` 命令冲突。
- 大量语音文件（>200）时首次加载可能稍慢，后续启动会很快（索引缓存）。
- 如遇问题，可查看 AstrBot 日志中的 `[echo_of_theresia]` 相关记录。

## 📄 更新日志

- **v1.0.5**（2025-12）  
  完全适配最新 AstrBot，修复所有命令冲突与加载问题，性能与稳定性大幅提升。

## 🤝 贡献 & 反馈

欢迎在 GitHub 仓库提交 Issue 或 Pull Request：  
https://github.com/riceshowerX/Echo-of-Theresia

## 📄 许可证

MIT License

---

让特雷西娅的声音永远回荡在你的聊天中 ♪