# Telegram Bot 经验记录 - 完整配置指南

## 为什么用 Telegram（比微信/QQ 简单）

- ✅ **无需企业认证**：个人即可创建 Bot
- ✅ **5分钟配置完成**：不需要服务器/域名
- ✅ **手机随时用**：和微信一样方便
- ✅ **国际通用**：支持全球访问
- ✅ **API 免费**：无限制调用

## 配置步骤（5分钟）

### 第1步：创建 Telegram Bot

1. 在 Telegram 搜索 `@BotFather`（官方机器人）
2. 发送 `/newbot` 命令
3. 按提示操作：
   ```
   BotFather: Alright, a new bot. How are we going to call it?
   你回复：StructPilot Lab Bot
   
   BotFather: Good. Now let's choose a username for your bot.
   你回复：StructPilot_YourLabName_bot  （必须以 _bot 结尾）
   ```
4. 创建成功后，BotFather 会给你一个 **Token**：
   ```
   Use this token to access the HTTP API:
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567
   ```
5. **复制这个 Token**（很重要！）

### 第2步：在 StructPilot 中配置

1. 打开 StructPilot → 高级模式 → 设置 tab
2. 找到「📱 Telegram Bot 经验记录」区域
3. 粘贴刚才复制的 Token
4. （可选）填写允许的 Chat ID（留空表示所有人都能用）
5. 点击「✅ 启用 Bot」

### 第3步：开始使用

1. 在 Telegram 搜索你刚创建的 Bot（`@StructPilot_YourLabName_bot`）
2. 点击 **Start** 按钮
3. Bot 会回复使用说明

## 使用方法

### 方式1：结构化记录（推荐）

发送格式：
```
#经验 [cp_02] Motion Correction 漂移过大
症状：drift plot 超出阈值，很多 micrograph 被丢弃
解决：增大 B-factor 从 150 调到 300，同时检查样品制备是否有冰层过厚
标签：运动校正, 漂移, B-factor
```

### 方式2：自由文本（AI 会帮你整理）

直接发：
```
#经验 今天跑 Particle Picking 发现自动挑的颗粒很多都是冰污染，
后来调整了 minimum diameter 参数就好了，记录一下
```

### 方式3：快速记录

```
#经验 CTF 拟合不好时记得检查 Cs 值是否正确
```

## 查看记录的经验

- 所有通过 Telegram 记录的经验会自动进入「待审核」状态
- 在 StructPilot 的「管理员审核面板」中查看并通过
- 通过后就会出现在知识库中，所有人可检索

## 常见问题

**Q：Token 泄露了怎么办？**
A：在 BotFather 发送 `/token`，选择你的 Bot，点击 `Revoke current token` 重新生成

**Q：如何限制只有实验室成员能用？**
A：在配置时填写「允许的 Chat ID」。成员第一次和 Bot 聊天时，Bot 会告诉他的 Chat ID

**Q：能同时记录图片吗？**
A：目前仅支持文字，图片可以在审核通过后在网页端补充上传

**Q：Telegram 在国内能用吗？**
A：需要科学上网工具，或者使用备选方案「邮件转经验」

## 备选方案：如果不想用 Telegram

如果你觉得 Telegram 不方便，可以用：
- 📧 **邮件转经验**：发邮件到指定邮箱，主题含 `#经验` 自动记录
- 💬 **课题组留言板**：在 StructPilot 网页内部直接发帖

## 演示 GIF

（配置完成后，你可以录个屏演示给组内成员看）

1. 打开 Telegram
2. 搜索你的 Bot
3. 发送 `#经验 [cp_05] Extract 参数调优经验`
4. 立即收到确认回复：「✅ 已记录到经验库（待审核）」
5. 在 StructPilot 网页端审核面板看到这条记录
6. 点击「通过」，经验正式入库
