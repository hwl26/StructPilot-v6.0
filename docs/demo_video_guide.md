# 操作短视频上传演示指南

## 使用方法

1. 打开 StructPilot → 切换到「高级模式」
2. 点击「💡 贡献经验」tab
3. 填写经验表单时，找到「📸 截图 + 🎬 操作视频」区域

### 方式1：上传本地视频
- 点击「操作演示视频」上传按钮
- 选择你的 .mp4 / .mov / .avi / .webm 文件（<50MB）
- 表单内会立即预览视频

### 方式2：填写外链
- 在「或填写外链」输入框粘贴视频地址
- 支持：
  - B站：`https://www.bilibili.com/video/BV1xx411c7XZ`
  - YouTube：`https://www.youtube.com/watch?v=xxxxx`
  - 腾讯视频：`https://v.qq.com/x/page/xxxxx.html`

### 保存位置
- 本地视频存储在：`runtime/experience_media/`
- 经验条目 JSON 字段：
  ```json
  {
    "video_path": "cp_02_20260724_114530.mp4",
    "video_url": "https://www.bilibili.com/video/..."
  }
  ```

## 示例场景

**场景**：录制 CryoSPARC Motion Correction 的操作演示

1. 用 OBS / 手机录屏软件录制操作过程（2-5分钟）
2. 导出为 .mp4 文件
3. 在贡献经验时上传这个视频
4. 填写标题「Motion Correction 完整操作流程」
5. 提交后，其他人查看经验时能直接播放视频学习
