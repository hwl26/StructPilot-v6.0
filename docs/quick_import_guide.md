# 🚀 快速导入实战经验到 StructPilot

## 📋 当前状态

- ✅ **经验数据已准备：** `contributed_experiences_demo.json`（6 条经验）
- ✅ **配图已保存：** Claude image cache 中有 6 张图片（41-46.png）
- ❌ **还未导入到 Web 系统**

---

## ⚡ 快速导入（3 步）

### **第1步：运行导入脚本**

```bash
cd D:\sh-tech\2026-03-01\windsurf_task1_cryoFIB_liftout_auto\final_struct

python tools/import_experiences.py
```

**脚本会自动：**
1. 读取 `contributed_experiences_demo.json`
2. 合并到 `runtime/lab_board/posts.json`
3. 避免重复导入
4. 设置状态为 `approved`（已审核）
5. 复制 6 张配图到 `runtime/images/experiences/`

---

### **第2步：启动 Web 应用**

```bash
streamlit run main.py
```

---

### **第3步：查看经验库**

1. 使用通过私有 Secrets 初始化的管理员账号登录
2. 进入「设置」Tab
3. 向下滚动到「📚 实验室共同知识库」
4. 查看新导入的 6 条经验

---

## 📊 导入后的效果

### **知识库页面展示：**

```
📚 实验室共同知识库

📖 共 6 条已验证经验

🔍 按步骤筛选: [cp_03 CTF估计]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ CTF Fit Resolution 分布判断数据质量

   分类：quality_check  |  步骤：cp_03

   症状：不知道 CTF 计算结果是否良好

   解决方案：
   判断标准：CTF Fit Resolution 条形图的分布

   ✅ 好数据（Good）：
   - 峰形尖锐，集中在 3.0-4.0 Å 狭窄范围
   - 单峰分布，表示数据高度均一性

   ❌ 需警惕（Bad）：
   - 大量 micrograph 在 7 Å 以上
   - 条形图分散，表示异质性高

   贡献者：实验室经验 · 2026-07-25

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### **AI 对话引用：**

```
用户：我的 CTF fit resolution 很分散，怎么办？

AI：根据实验室共享经验，CTF Fit Resolution 分布是判断数据质量的重要指标：

✅ 好数据：峰形尖锐，集中在 3.0-4.0 Å
❌ 需警惕：大量 micrograph 在 7 Å 以上

建议：
1. 回头检查制样环节（冰层厚度、vitrification）
2. 检查数据采集参数
3. 考虑重新制样

[来源：实验室经验库]
```

---

## 🛠️ 手动导入（如果脚本出错）

### **方法1：直接编辑 JSON**

1. 打开 `runtime/lab_board/posts.json`
2. 复制 `contributed_experiences_demo.json` 中的所有 `entries`
3. 粘贴到 `posts.json` 的 `entries` 数组中
4. 修改 `status: "pending"` → `"approved"`
5. 保存文件

### **方法2：通过 Web UI 逐条添加**

1. 启动 Web 应用
2. 登录管理员账号
3. 进入「对话陪跑」Tab
4. 右侧边栏 → 「✍️ 贡献经验」
5. 逐条复制粘贴 6 条经验
6. 在「设置」中审核通过

---

## 📷 配图处理

### **方案A：使用导入脚本（自动）**
脚本会自动复制图片从：
```
C:\path\to\image-cache\
```
到：
```
runtime/images/experiences/
```

### **方案B：手动复制**
```bash
# 创建目录
mkdir runtime\images\experiences

# 复制图片
copy "C:\path\to\image-cache\41.png" runtime\images\experiences\
copy "C:\path\to\image-cache\42.png" runtime\images\experiences\
# ... 依此类推 43-46.png
```

---

## ✅ 验证导入成功

1. 打开 `runtime/lab_board/posts.json`
2. 确认包含 6 条新经验（`exp_import_001` 到 `exp_2d_class_001`）
3. 确认 `status: "approved"`
4. 启动 Web 应用，查看知识库页面

---

## 🎯 6 条经验一览

| ID | 标题 | 步骤 | 配图 |
|----|------|------|------|
| exp_import_001 | 数据导入：检查图片数量 | cp_01 | 41.png |
| exp_ctf_001 | CTF Fit Resolution 分布判断 | cp_03 | 42.png |
| exp_ctf_002 | 像散与分辨率四大指标 | cp_03 | 43.png |
| exp_patch_ctf_001 | Patch CTF 曲面解读 | cp_03b | 44.png |
| exp_curate_001 | Curate Exposures 筛选标准 | cp_03c | 45.png |
| exp_2d_class_001 | 2D Classification 质量初评 | cp_06 | 46.png |

---

## 💡 提示

- 导入后，这些经验会对**所有成员**可见（公共级别）
- AI 对话时可以引用这些经验
- 管理员可以继续添加更多实战经验
- 建议定期备份 `runtime/lab_board/posts.json`

---

**立即运行导入脚本，3 分钟完成集成！** 🚀✨
