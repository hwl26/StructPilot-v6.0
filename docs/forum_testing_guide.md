# StructPilot 论坛模块测试

## 快速测试

### 1. 启动 StructPilot

```bash
cd D:\sh-tech\2026-03-01\windsurf_task1_cryoFIB_liftout_auto\final_struct
streamlit run main.py
```

### 2. 访问论坛

1. 打开浏览器：http://localhost:8501
2. 点击顶部 Tab：**💬 讨论区**
3. 应该看到3个示例问题

### 3. 测试功能

#### **查看问题列表**
- ✅ 看到3个示例问题
- ✅ 显示标题、作者、标签、状态
- ✅ 显示点赞数、回答数、浏览数

#### **搜索功能**
- 在搜索框输入："motion"
- 应该只显示包含"motion"的问题

#### **标签筛选**
- 选择标签："cryosparc"
- 应该只显示 cryosparc 相关的问题

#### **查看问题详情**
- 点击任一问题卡片
- 应该进入详情页
- 显示：问题内容 + 所有回答 + 评论
- Markdown 应该正确渲染（加粗、列表、代码块）

#### **点赞功能**
- 点击问题旁的 👍 按钮
- 点赞数应该 +1
- 再点击一次，点赞数 -1（取消点赞）
- 同理测试回答的点赞

#### **采纳最佳答案**
- 在"Motion Correction"问题的详情页
- 王师兄的回答应该显示 ✅ 已采纳

#### **发布新问题**
- 点击 ➕ 提问
- 填写标题和内容
- 点击发布
- 应该跳转到新问题的详情页

#### **回答问题**
- 在问题详情页底部
- 填写回答内容
- 点击发布
- 回答应该显示在列表中

#### **添加评论**
- 点击问题/回答下方的"💬 添加评论"
- 填写评论内容
- 点击发布
- 评论应该显示出来

---

## 检查数据文件

```bash
cat runtime/forum/forum_posts.json
```

应该看到 JSON 格式的论坛数据。

---

## 常见问题

### **Q1: 论坛 Tab 没有显示**

**检查：**
```python
# main.py 中应该有：
tab_labels = ["对话陪跑", "💬 讨论区", "设置"]
tab_chat, tab_forum, tab_settings = st.tabs(tab_labels)
```

### **Q2: 点击提问按钮没反应**

**检查：**
- 是否已登录？（需要 username 在 session_state 中）
- 浏览器控制台是否有报错？

### **Q3: Markdown 没有正确渲染**

**原因：** Streamlit 的 `st.markdown()` 默认支持 Markdown

**检查：** 代码中是否用了 `st.markdown(content)` 而不是 `st.text(content)`

### **Q4: 数据没有保存**

**检查：**
```bash
ls -lh runtime/forum/forum_posts.json
```

应该有文件且大小 > 0

---

## 集成测试脚本

```python
# test_forum.py
import sys
sys.path.insert(0, ".")

from utils.forum_data import (
    load_forum_data,
    create_question,
    create_answer,
    upvote,
    search_questions
)

def test_forum():
    print("=== 论坛模块测试 ===\n")
    
    # 测试1：加载数据
    print("测试1：加载数据...")
    data = load_forum_data()
    assert "posts" in data
    assert "answers" in data
    print(f"✅ 成功加载 {len(data['posts'])} 个问题\n")
    
    # 测试2：创建问题
    print("测试2：创建问题...")
    qid = create_question(
        author="test_user",
        author_display="测试用户",
        title="测试问题",
        content="这是一个测试问题",
        tags=["test"],
        software="cryoSPARC"
    )
    print(f"✅ 创建问题成功，ID: {qid}\n")
    
    # 测试3：回答问题
    print("测试3：回答问题...")
    aid = create_answer(
        question_id=qid,
        author="test_user2",
        author_display="测试用户2",
        content="这是一个测试回答"
    )
    print(f"✅ 创建回答成功，ID: {aid}\n")
    
    # 测试4：点赞
    print("测试4：点赞...")
    upvote("test_user3", qid, "question")
    upvote("test_user3", aid, "answer")
    print("✅ 点赞成功\n")
    
    # 测试5：搜索
    print("测试5：搜索...")
    results = search_questions("motion")
    print(f"✅ 搜索 'motion' 找到 {len(results)} 个结果\n")
    
    print("=== 所有测试通过 ===")

if __name__ == "__main__":
    test_forum()
```

运行测试：
```bash
python test_forum.py
```

---

## 性能测试

### **负载测试**

```python
# 测试创建 1000 个问题的性能
import time
from utils.forum_data import create_question

start = time.time()
for i in range(1000):
    create_question(
        author=f"user{i}",
        author_display=f"用户{i}",
        title=f"测试问题 {i}",
        content=f"内容 {i}",
        tags=["test"]
    )
end = time.time()

print(f"创建 1000 个问题耗时: {end - start:.2f} 秒")
```

**预期：** < 5 秒

---

## 已知限制

1. **文件存储性能**
   - 当前使用 JSON 文件存储
   - 1000+ 问题后可能变慢
   - 解决方案：升级为 SQLite

2. **实时同步**
   - 多个实例同时写入可能冲突
   - 需要文件锁或数据库

3. **富文本编辑器**
   - 当前是纯文本输入框
   - 未来可集成 Markdown 编辑器

4. **图片上传**
   - 当前不支持在问题中上传图片
   - 可用外部图床 + Markdown 链接

---

## 下一步优化

### **短期（1周）**
- [ ] 增加"我的问题"/"我的回答"页面
- [ ] 优化移动端显示
- [ ] 增加问题编辑功能

### **中期（1月）**
- [ ] 升级为 SQLite 存储
- [ ] 邮件通知
- [ ] 用户声望系统

### **长期（3月）**
- [ ] 实时评论（WebSocket）
- [ ] AI 自动回答（基于经验库）
- [ ] 多语言支持

---

**测试通过后，可以开始使用论坛了！**
