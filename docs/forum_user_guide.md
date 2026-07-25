# StructPilot 内置论坛使用指南

## 📖 功能概览

StructPilot 内置了类似 Stack Overflow 的 Q&A 论坛，支持：

✅ **提问/回答/评论** — 完整的讨论功能  
✅ **点赞/采纳最佳答案** — 突出高质量回答  
✅ **标签分类** — 按软件/步骤/类型分类  
✅ **搜索过滤** — 快速找到相关问题  
✅ **Markdown 支持** — 代码高亮、格式化  
✅ **匿名选项** — 保护隐私  

---

## 🎯 使用场景

### **场景1：各实验室独立使用（推荐）**

```
每个实验室独立部署 StructPilot：
├─ 论坛数据：runtime/forum/forum_posts.json
├─ 仅本组成员可见
└─ 私有经验留在本地
```

**适用：** 日常实验室内部讨论

---

### **场景2：跨实验室经验交流（可选）**

**方案A：GitHub Discussions（推荐）**
```
1. 在 GitHub 仓库开启 Discussions
2. 各实验室成员在这里公开提问
3. 精华问答整理后录入各自的论坛
```

**方案B：共享论坛数据文件**
```
1. 将 forum_posts.json 推送到 GitHub
2. 其他实验室定期拉取更新
3. 合并公开的问答到本地
```

**方案C：中央论坛服务器（高级）**
```
1. 部署独立的论坛实例（无IP白名单）
2. 所有实验室都可以访问
3. 仅用于公开经验交流
```

---

## 🚀 快速开始

### **1. 访问论坛**

1. 打开 StructPilot
2. 点击顶部 Tab：**💬 讨论区**
3. 看到问题列表

---

### **2. 提问**

点击右上角 **➕ 提问** 按钮：

![提问表单示例]

**填写内容：**
- **问题标题**（必填）：简洁描述问题
  - ✅ 好：`Motion Correction 报错 local motion too large 如何解决？`
  - ❌ 差：`求助！！！`
  
- **详细描述**（必填）：
  - 问题背景
  - 已尝试的方法
  - 错误信息（如有）
  - 环境信息（软件版本、参数等）
  
- **相关软件**：选择 cryoSPARC / RELION / Chimera 等
  
- **相关步骤**：选择 cp_01 ~ cp_09
  
- **标签**：用逗号分隔，如 `cryosparc, error, motion_correction`
  
- **匿名提问**：勾选后，显示为"匿名用户"

**Markdown 支持：**
```markdown
## 二级标题

**加粗文本**

- 列表项1
- 列表项2

\```python
# 代码块（支持语法高亮）
print("Hello StructPilot")
\```
```

---

### **3. 回答问题**

点击问题卡片进入详情页，在底部填写回答：

**回答建议：**
- ✅ 详细说明解决方案
- ✅ 提供具体参数/命令
- ✅ 说明原理（可选）
- ✅ 附上参考资料（可选）
- ✅ 如有多种方案，分点列出

**示例回答：**
```markdown
我之前也遇到过这个问题！解决方法：

**方案1：增大 B-factor（推荐）**
- 将 B-factor 从 150 调到 **500** 甚至 **800**
- 这个方法在我们实验室试过3次，都有效

**方案2：调整像素大小（如果方案1无效）**
- 在 Import Movies 时，将 pixel size 设为实际值的 **0.8 倍**
- 重新导入，再跑 Motion Correction

**原因：**
这个错误通常是因为漂移过大，B-factor 设置过小导致的。

试试看，有问题再追问！
```

---

### **4. 互动操作**

#### **点赞**
- 点击问题/回答旁的 👍 按钮
- 高质量内容会获得更多点赞，排序靠前

#### **采纳最佳答案**
- **仅提问者可操作**
- 点击回答下方的 **✅ 采纳为最佳答案** 按钮
- 采纳后，问题状态变为"已解决"

#### **评论**
- 在问题/回答下方点击 **💬 添加评论**
- 用于补充说明或追问细节

---

### **5. 搜索和筛选**

**搜索框：**
- 输入关键词，实时搜索标题和内容
- 支持模糊匹配

**标签筛选：**
- 下拉选择标签（如 `cryosparc`, `error`）
- 只显示相关问题

**组合使用：**
```
搜索："motion correction" + 标签："error"
→ 找到所有关于 motion correction 错误的问题
```

---

## 📊 数据管理

### **数据存储位置**

```
runtime/forum/forum_posts.json
```

**数据结构：**
```json
{
  "posts": [...],      // 所有问题
  "answers": [...],    // 所有回答
  "comments": [...],   // 所有评论
  "votes": [...]       // 点赞记录
}
```

---

### **备份论坛数据**

```bash
# 手动备份
cp runtime/forum/forum_posts.json backup/forum_$(date +%Y%m%d).json

# 推送到 Git（可选）
git add runtime/forum/forum_posts.json
git commit -m "forum: 更新论坛数据"
git push
```

---

### **合并论坛数据（跨实验室）**

**场景：** 实验室A想导入实验室B公开的问答

**步骤：**

1. **导出实验室B的公开问答**
   ```python
   import json
   data = json.load(open("runtime/forum/forum_posts.json"))
   
   # 只保留 visibility="public" 的问题
   public_posts = [p for p in data["posts"] if p.get("visibility") == "public"]
   
   # 同步导出相关回答和评论
   public_ids = [p["id"] for p in public_posts]
   public_answers = [a for a in data["answers"] if a["question_id"] in public_ids]
   answer_ids = [a["id"] for a in public_answers]
   public_comments = [c for c in data["comments"] if c["parent_id"] in public_ids + answer_ids]
   
   export_data = {
       "posts": public_posts,
       "answers": public_answers,
       "comments": public_comments,
       "votes": []
   }
   
   with open("forum_export_public.json", "w", encoding="utf-8") as f:
       json.dump(export_data, f, ensure_ascii=False, indent=2)
   ```

2. **导入到实验室A**
   ```python
   import json
   
   # 加载现有数据
   local_data = json.load(open("runtime/forum/forum_posts.json"))
   
   # 加载导入数据
   import_data = json.load(open("forum_export_public.json"))
   
   # 合并（去重）
   existing_ids = {p["id"] for p in local_data["posts"]}
   for post in import_data["posts"]:
       if post["id"] not in existing_ids:
           local_data["posts"].append(post)
   
   # 同理合并 answers 和 comments
   # ...
   
   # 保存
   with open("runtime/forum/forum_posts.json", "w", encoding="utf-8") as f:
       json.dump(local_data, f, ensure_ascii=False, indent=2)
   ```

---

## 🔒 隐私和权限

### **问题可见性**

| 可见性 | 说明 | 适用场景 |
|--------|------|---------|
| `public` | 所有人可见（默认） | 通用问题、愿意分享的经验 |
| `lab_only` | 仅本实验室可见 | 敏感数据、未发表的蛋白 |

**设置方法：**
- 提问时，暂不支持选择（默认 public）
- 管理员可在数据文件中手动修改 `visibility` 字段

---

### **匿名提问**

勾选"匿名提问"后：
- 显示为"匿名用户"
- 不显示实验室信息
- 仍然记录真实作者（仅管理员可见数据文件）

---

## 🎨 最佳实践

### **提问技巧**

✅ **好问题示例：**
```
标题：Motion Correction 报错 local motion too large 如何解决？

内容：
我在运行 cryoSPARC v4.5 的 Motion Correction 时，有200/500张 micrograph 报错。

**环境：**
- cryoSPARC v4.5.3
- Falcon 4 相机
- 像素大小：0.85 Å/pixel

**已尝试：**
- 调整 B-factor 到 200（默认150）
- 重新导入数据

**错误日志：**
\```
RuntimeError: local motion too large
\```

请问有什么解决办法？
```

❌ **差问题示例：**
```
标题：求助！！！

内容：跑不动，怎么办？
```

---

### **回答技巧**

✅ **好回答示例：**
```
我之前也遇到过！解决方法：

**方案1：增大 B-factor（推荐）**
- 将 B-factor 调到 500-800
- 我们实验室试过3次都有效

**方案2：调整像素大小**
- Import 时 pixel size × 0.8
- 重新跑 Motion Correction

**原理：**
漂移过大时，小的 B-factor 无法容忍。

试试看，有问题再追问！
```

❌ **差回答示例：**
```
我也不知道，试试调参数吧。
```

---

## 🔧 高级功能（未来计划）

[ ] 邮件通知（有人回答你的问题时）  
[ ] RSS 订阅（关注特定标签）  
[ ] 问题关闭/锁定（管理员功能）  
[ ] 用户声望系统（基于点赞数）  
[ ] 徽章奖励（活跃贡献者）  
[ ] Slack/飞书集成（自动推送新问题）  

---

## 📞 技术支持

**问题反馈：**
- GitHub Issues: https://github.com/your-repo/issues
- 论坛提问（吃自己的狗粮 🐶）
- 邮件：your-email@example.com

---

**文档版本：** v1.0  
**最后更新：** 2025-01-25
