# 📚 实战经验集成指南

## 🎉 收到的经验内容

**来源：** 微信文件 `经验+配图_demo.docx`
**包含：** 6 条高质量实战经验 + 6 张配图
**覆盖步骤：** cp_01, cp_03, cp_03b, cp_03c, cp_06

---

## 📋 经验清单

| # | 标题 | 步骤 | 类别 | 配图 |
|---|------|------|------|------|
| 1 | 数据导入：检查图片数量 | cp_01 | checklist | 41.png |
| 2 | CTF Fit Resolution 分布判断 | cp_03 | quality_check | 42.png |
| 3 | 像散与分辨率四大指标 | cp_03 | quality_check | 43.png |
| 4 | Patch CTF 曲面解读 | cp_03b | interpretation | 44.png |
| 5 | Curate Exposures 筛选标准 | cp_03c | checklist | 45.png |
| 6 | 2D Classification 质量初评 | cp_06 | quality_check | 46.png |

---

## 💎 经验价值

每条经验都包含：
1. ✅ **明确的数值阈值**（如 CTF fit < 5 Å，astigmatism < 200 nm）
2. ✅ **Good vs Bad 对比**（图文结合，一目了然）
3. ✅ **操作建议**（删除/保留的具体标准）
4. ✅ **原理解释**（为什么这样判断）

这是**实战级**的经验，不是纸上谈兵！

---

## 🔧 如何集成到 StructPilot

### **方法A：通过 Web UI 贡献（推荐）**

1. **启动应用**
   ```bash
   streamlit run main.py
   ```

2. **以管理员身份登录**
   - 用户名：`admin`
   - 密码：`admin123`

3. **贡献经验**
   - 进入「对话陪跑」Tab
   - 右侧边栏 → 「✍️ 贡献经验」
   - 逐条填写 6 条经验（复制 JSON 中的内容）

4. **审核通过**
   - 进入「设置」Tab
   - 📚 实验室共同知识库 → 🔍 待审核经验
   - 点击「✅ 批准」

5. **上传配图**
   - 将 6 张图片（41-46.png）上传到系统
   - 或者将图片保存到 `runtime/images/experiences/`

---

### **方法B：直接导入 JSON（快速）**

1. **复制经验数据**
   ```bash
   cp contributed_experiences_demo.json runtime/lab_board/imported_experiences.json
   ```

2. **手动合并到主文件**
   - 打开 `runtime/lab_board/posts.json`
   - 将 `contributed_experiences_demo.json` 中的 `entries` 合并进去
   - 修改 `status: "pending"` → `"approved"`（如果管理员已审核）

3. **处理配图**
   - 方案A：将图片上传到图床，更新 JSON 中的图片 URL
   - 方案B：保存到 `runtime/images/experiences/` 目录
   - 方案C：使用占位符，后续管理员补充

---

### **方法C：导入脚本（自动化）**

创建导入脚本 `import_experiences.py`：

```python
import json
from pathlib import Path
from datetime import datetime

# 读取示例经验
demo_file = Path("contributed_experiences_demo.json")
with open(demo_file, 'r', encoding='utf-8') as f:
    demo_data = json.load(f)

# 读取现有经验库
posts_file = Path("runtime/lab_board/posts.json")
if posts_file.exists():
    with open(posts_file, 'r', encoding='utf-8') as f:
        posts_data = json.load(f)
else:
    posts_data = {"entries": []}

# 合并经验（避免重复）
existing_ids = {e["id"] for e in posts_data["entries"]}
new_entries = [e for e in demo_data["entries"] if e["id"] not in existing_ids]

# 更新状态（管理员已审核）
for entry in new_entries:
    entry["status"] = "approved"  # 或保持 "pending" 等待审核
    entry["date"] = datetime.now().strftime("%Y-%m-%d")

# 添加到经验库
posts_data["entries"].extend(new_entries)

# 保存
with open(posts_file, 'w', encoding='utf-8') as f:
    json.dump(posts_data, f, ensure_ascii=False, indent=2)

print(f"✅ 成功导入 {len(new_entries)} 条经验")
print(f"📊 经验库总计：{len(posts_data['entries'])} 条")
```

运行：
```bash
python import_experiences.py
```

---

## 📷 配图处理

### **当前状态**
- 图片已保存在 Claude 的 image cache
- 路径：`C:\Users\17706\.claude\image-cache\a6558aff-b50b-4474-aab4-ac8115bc8507\41-46.png`

### **处理方案**

**方案A：复制到项目目录**
```bash
# 创建目录
mkdir -p runtime/images/experiences/

# 复制图片
cp C:\Users\17706\.claude\image-cache\a6558aff-b50b-4474-aab4-ac8115bc8507\41.png runtime/images/experiences/
cp C:\Users\17706\.claude\image-cache\a6558aff-b50b-4474-aab4-ac8115bc8507\42.png runtime/images/experiences/
# ... 依此类推 43-46.png
```

**方案B：使用图床**
1. 上传到图床（如 imgur、GitHub、自建图床）
2. 更新 JSON 中的 `images` 字段为图片 URL

**方案C：嵌入 Base64（不推荐，文件大）**
- 将图片转为 Base64 编码
- 嵌入到 JSON 中

---

## 🎯 集成后效果

### **知识库页面展示**
```
📚 实验室共同知识库

🔍 按步骤筛选: [cp_03 CTF估计]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ CTF Fit Resolution 分布判断数据质量
   分类：quality_check  |  步骤：cp_03

   症状：不知道 CTF 计算结果是否良好

   解决方案：
   判断标准：CTF Fit Resolution 条形图的分布

   ✅ 好数据（Good）：
   - 峰形尖锐，大部分 micrograph 集中在 3.0-4.0 Å
   - 单峰分布，表示数据高度均一性
   
   ❌ 需警惕（Bad）：
   - 大量 micrograph 在 7 Å 以上
   - 条形图分散，表示数据异质性高

   [查看配图 42.png]

   贡献者：实验室经验 · 2026-07-25

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### **对话陪跑 AI 引用**
```
用户：我的 CTF fit resolution 条形图很分散，是否正常？

AI：根据实验室共享经验，CTF Fit Resolution 条形图的分布是判断
数据质量的重要指标：

✅ 好数据：峰形尖锐，集中在 3.0-4.0 Å 狭窄范围
❌ 需警惕：大量 micrograph 在 7 Å 以上，表示数据异质性高

如果您的数据呈现分散的条形图，建议：
1. 回头检查制样环节（冰层厚度、vitrification）
2. 检查数据采集参数（defocus 范围、剂量）
3. 考虑重新制样

[来源：实验室经验库 - CTF Fit Resolution 分布判断]
[查看配图]
```

---

## ✅ 总结

这 6 条经验是非常宝贵的**实战资料**，建议：

1. **立即集成**：使用方法A或B导入到经验库
2. **配图处理**：复制图片到项目目录或使用图床
3. **管理员审核**：确保所有经验 status 为 "approved"
4. **测试展示**：查看知识库页面和 AI 对话引用效果
5. **持续积累**：鼓励实验室成员继续贡献类似的实战经验

**这些经验将极大提升 StructPilot 的实用价值！** 🎉✨
