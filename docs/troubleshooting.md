# StructPilot 常见问题解决方案

## 🚨 已修复的问题

### **问题1：论坛页面 ImportError**

**错误信息：**
```
ImportError: cannot import name 'render_forum_detail' from 'components.forum_ui'
```

**原因：** 函数名不匹配

**修复：**
- ✅ 已修正为 `render_question_detail`
- ✅ 更新了 main.py 中的导入

**解决方案：** 已在 commit c9232db 中修复

---

### **问题2：论坛模块另一个 ImportError**

**错误信息：**
```
ImportError: cannot import name 'search_questions' from 'utils.forum_data'
```

**原因：** 函数名应为 `search_posts`

**修复：**
- ✅ 添加了缺失的 `has_user_upvoted()` 函数
- ✅ 统一函数命名

**解决方案：** 已在之前的 commit 中修复

---

## 🔍 当前待解决问题

### **问题1：RELION 步骤显示 cryoSPARC 配置**

**症状：**
- 选择 RELION 作为软件
- 在 Motion Correction 步骤时
- 参数面板显示 cryoSPARC 的配置

**可能原因：**
1. 参数向导的软件检测逻辑混淆
2. workflow 模板配置错误
3. checkpoint 定义中软件字段未正确设置

**临时解决方案：**
- 切换到「高级模式」
- 手动配置参数

**调试步骤：**
```python
# 检查当前软件配置
import streamlit as st
print(st.session_state.get("selected_software"))
print(st.session_state.get("recommended_workflow"))
```

**建议：**
需要深入调试入门模式的参数向导逻辑。

---

### **问题2：桌宠未显示**

**症状：**
- 右下角没有显示桌宠（小动物）

**可能原因：**
1. `pet_enabled` 被设置为 False
2. 浏览器缓存问题
3. 桌宠组件渲染失败

**解决步骤：**

#### **步骤1：检查桌宠设置**
1. 打开「设置」Tab
2. 找到「🎨 界面设置」区域
3. 查看「桌宠陪伴（右下角小动物）」是否勾选
4. 如果未勾选：
   - 勾选该选项
   - 选择桌宠类型（🐧 冷冻企鹅 / 🐱 科研小猫 / 🐶 实验小狗）
   - 点击「保存界面设置」
   - 刷新页面（F5）

#### **步骤2：清除浏览器缓存**
```
Chrome：
Ctrl + Shift + Delete → 清除图片和文件 → 清除数据

Edge：
Ctrl + Shift + Delete → 缓存的图像和文件 → 清除

Firefox：
Ctrl + Shift + Delete → 缓存 → 立即清除
```

#### **步骤3：检查控制台错误**
1. 按 F12 打开开发者工具
2. 切换到「Console」标签
3. 查看是否有红色错误信息
4. 截图发送给我

#### **步骤4：手动启用桌宠**
```python
# 在浏览器中打开 Streamlit 后，按 F12，在 Console 中输入：
import streamlit as st
st.session_state["pet_enabled"] = True
st.session_state["pet_type"] = "penguin"
st.rerun()
```

---

## 📝 功能使用指南

### **1. 个人笔记**

**位置：** 「设置」Tab → 「📝 个人笔记」

**使用流程：**
1. **登录**
   - 左侧边栏「👤 用户笔记」
   - 输入用户名（如：`zhang_san`）
   - 点击「登录/切换用户」

2. **新建笔记**
   - 点击「➕ 新建笔记」
   - 填写标题：如 `Motion Correction 参数设置`
   - 填写内容：记录实验心得、参数、问题解决方案
   - 选择相关步骤（可选）
   - 点击「💾 保存笔记」

3. **查看笔记**
   - 在「我的笔记」区域查看所有笔记
   - 点击笔记展开查看详情

4. **删除笔记**
   - 展开笔记
   - 点击「🗑️ 删除」按钮

---

### **2. 实验室共同知识库**

**位置：** 「设置」Tab → 「📚 实验室共同知识库」

**查看已审核经验：**
1. 滚动到「实验室共同知识库」区域
2. 使用「按步骤筛选」下拉框过滤
3. 点击经验卡片展开查看详情

**内容包括：**
- 问题症状
- 解决方案
- 相关步骤
- 贡献者和日期

**说明：**
- 只显示「已审核通过」的经验
- 所有成员都可以查看
- 管理员负责审核（在高级模式中）

---

### **3. 论坛（讨论区）**

**位置：** 顶部 Tab → 「💬 讨论区」

**提问：**
1. 点击「➕ 提问」按钮
2. 填写问题标题和详细描述
3. 选择相关软件和步骤
4. 添加标签（用逗号分隔）
5. 可选：勾选「匿名提问」
6. 点击「✅ 发布问题」

**回答：**
1. 点击问题卡片进入详情页
2. 滚动到底部「📝 你的回答」区域
3. 填写回答内容（支持 Markdown）
4. 点击「✅ 发布回答」

**互动：**
- **点赞**：点击 👍 按钮
- **采纳最佳答案**：点击「✅ 采纳为最佳答案」（仅提问者可操作）
- **添加评论**：点击「💬 添加评论」

**搜索和筛选：**
- 搜索框：输入关键词
- 标签筛选：选择标签（如 `cryosparc`、`error`）
- 组合使用：搜索 + 标签

---

## 🛠️ 开发者调试指南

### **检查论坛数据**

```bash
cd D:\sh-tech\2026-03-01\windsurf_task1_cryoFIB_liftout_auto\final_struct

# 查看论坛数据文件
cat runtime/forum/forum_posts.json

# 或使用 Python
python -c "
import json
data = json.load(open('runtime/forum/forum_posts.json'))
print(f'Posts: {len(data[\"posts\"])}')
print(f'Answers: {len(data[\"answers\"])}')
print(f'Comments: {len(data[\"comments\"])}')
"
```

---

### **检查个人笔记数据**

```bash
# 查看某用户的笔记
python -c "
from utils.user_manager import load_user_notes
notes = load_user_notes('zhang_san')
print(f'User zhang_san has {len(notes)} notes')
for note in notes:
    print(f'- {note.get(\"title\")}: {note.get(\"created_at\")[:10]}')
"
```

---

### **检查实验室知识库**

```bash
python -c "
import json
data = json.load(open('knowledge_base/lab_experience_kb.json'))
entries = data.get('entries', [])
approved = [e for e in entries if e.get('status') == 'approved']
print(f'Total entries: {len(entries)}')
print(f'Approved: {len(approved)}')
"
```

---

### **重置论坛数据（慎用）**

```bash
# 备份当前数据
cp runtime/forum/forum_posts.json runtime/forum/forum_posts.backup.json

# 重置为示例数据
python -c "
import json
default_data = {
    'posts': [],
    'answers': [],
    'comments': [],
    'votes': []
}
with open('runtime/forum/forum_posts.json', 'w', encoding='utf-8') as f:
    json.dump(default_data, f, ensure_ascii=False, indent=2)
print('Forum data reset to empty')
"
```

---

## 📞 获取帮助

**遇到问题时，请提供以下信息：**

1. **错误截图**（包括完整的错误信息）
2. **操作步骤**（如何重现问题）
3. **浏览器和版本**（Chrome 120 / Edge 121 等）
4. **Python 版本**
   ```bash
   python --version
   ```
5. **Streamlit 版本**
   ```bash
   streamlit --version
   ```
6. **控制台日志**（F12 → Console 标签中的错误）

---

**最后更新：** 2025-01-26  
**版本：** v6.0 + 论坛模块
