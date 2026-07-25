# StructPilot RELION 模式 — 完整说明

## 🎯 工作流设计

### **RELION 的定位**

在实际的冷冻电镜数据处理中，很多实验室采用 **混合工作流**：

```
RELION (前期处理)          cryoSPARC (后期处理)
├─ Import                 ├─ CTF Estimation
├─ Motion Correction      ├─ Particle Picking
└─ 导出 STAR 文件 ────────→ ├─ 2D Classification
                           ├─ Ab-initio
                           ├─ 3D Classification
                           └─ 3D Refinement
```

**原因：**
- RELION 的 Motion Correction 参数更灵活
- cryoSPARC 的后期处理更快速
- 两者结合效率最高

---

## 📋 入门模式下的 RELION 支持

### **1. 软件切换后的提示**

当用户在左侧边栏选择「RELION」时，会看到：

```
💡 RELION 使用说明

RELION 工作流说明：

在入门模式下，RELION 主要用于：
✅ 数据导入 (Import)
✅ 运动校正 (Motion Correction)

后续步骤（CTF、颗粒挑选等）建议切换到 cryoSPARC 完成。

如需完整的 RELION 工作流，请切换到「⚙️ 高级模式」。

[ 💡 查看 RELION 详细指南 ]
```

---

### **2. 参数向导页面的拦截**

当 RELION 用户进入「步骤2：运动校正」的参数填写页面时，会看到：

```
⚠️ RELION 工作流限制

入门模式的参数向导主要针对 cryoSPARC 工作流设计。

RELION 用户建议：
1. 在 RELION 中完成「数据导入」和「运动校正」
2. 导出 STAR 文件
3. 切换软件选择为「cryoSPARC」继续后续流程

或切换到「⚙️ 高级模式」使用完整的 RELION 功能。

[ 🔄 切换到 cryoSPARC ]  [ ⚙️ 切换到高级模式 ]

---
💡 如需继续使用 RELION，请参考左侧边栏的「RELION 使用说明」。
```

**设计目的：**
- ✅ 避免用户混淆（不再显示 cryoSPARC 参数）
- ✅ 提供清晰的引导路径
- ✅ 支持一键切换

---

## 🔧 高级模式下的 RELION 支持

### **完整的 RELION 工作流**

在高级模式中，用户可以使用：

1. **RELION 卡片库**
   - 文件：`knowledge_base/flows/relion_stage_cards.json`
   - 包含：Import、Motion Correction、CTF Estimation 等所有步骤的详细说明

2. **RELION 参数预设**
   - 每个步骤的关键参数
   - 常见陷阱和 QC 检查
   - GitHub Issues 和文档引用

3. **对话陪跑**
   - 系统会根据选择的软件（RELION）推荐对应的步骤
   - RAG 检索 RELION 文档和经验

---

## 🛠️ 固定参数可编辑提示

### **问题**

之前的固定参数区域虽然可以编辑，但不够明显，用户可能以为是"禁用"的。

### **解决方案**

在固定参数区域添加提示信息：

```
🔒 固定参数（通常无需修改）
┌────────────────────────────────────────────────────┐
│ 💡 提示： 这些参数通常不需要修改，但如果你需要自│
│ 定义，可以直接编辑下方的值。                       │
├────────────────────────────────────────────────────┤
│ 加速电压 (kV)                                      │
│ 300                                        ▼       │
│                                                    │
│ 球差系数 (mm)                                      │
│ 2.70                                      - +      │
│                                                    │
│ 总剂量 (e⁻/Ų)                                      │
│ 60.00                                     - +      │
└────────────────────────────────────────────────────┘
```

---

## 📚 RELION 指南内容（基于卡片库）

### **1. 数据导入 (cp_01)**

**目标：**  
建立 RELION 项目目录，导入原始 movies 或 micrographs，并确认 pixel size、电压、Cs、文件路径和 STAR/metadata 信息正确。

**输入：**
- 原始 movies 或 micrographs
- 采集参数：pixel size、voltage、Cs、dose 等
- 项目目录和原始数据目录

**关键参数：**
- Pixel size
- Voltage
- Spherical aberration / Cs
- Input files pattern
- Optics group / metadata

**QC 检查：**
- ✅ 导入后的文件数量与原始数据一致
- ✅ STAR 文件中的路径可访问
- ✅ pixel size 和 optics 信息与显微镜记录一致
- ✅ 项目目录结构清晰，后续 job 可复现

**常见陷阱：**
- ❌ 从错误目录启动 RELION GUI，导致相对路径混乱
- ❌ pixel size 写错，后续 CTF、重构尺度都会受影响
- ❌ 重复或不一致的 mdoc/STAR metadata 导致导入异常

---

### **2. 运动校正 (cp_02)**

**目标：**  
校正 beam-induced motion 和帧间漂移，得到可用于 CTF 估计与颗粒挑选的 corrected micrographs。

**输入：**
- 导入后的 movies
- dose/frame、pixel size、gain reference 等采集信息

**关键参数：**
- Dose per frame
- Patch/grid settings
- Binning
- Gain reference
- Output micrograph STAR

**QC 检查：**
- ✅ 校正后 micrograph 无明显拖影
- ✅ 运动轨迹合理，没有大面积异常漂移
- ✅ 输出文件和 STAR 路径完整
- ✅ 坏帧或异常电影被记录或排除

**常见陷阱：**
- ❌ gain reference 或像素尺寸不匹配
- ❌ dose 信息错误导致后续 dose weighting 或 polishing 受影响
- ❌ 异常 movies 混入后续流程

---

## 🚀 使用流程示例

### **场景：混合工作流（RELION + cryoSPARC）**

#### **步骤1：在 RELION 中处理前期**

1. **启动 StructPilot**
   ```bash
   streamlit run main.py
   ```

2. **选择软件**
   - 左侧边栏 → 软件 → 选择「RELION」
   - 查看「RELION 使用说明」

3. **选择模式**
   - 高级模式（推荐）或入门模式

4. **开始流程**
   - 步骤1：数据导入
     - 填写 pixel size、voltage、Cs
     - 指定 movies 路径
     - 确认 STAR 文件生成
   
   - 步骤2：运动校正
     - 设置 dose per frame
     - 配置 gain reference
     - 运行 RELION Motion Correction
     - 检查 QC 图（运动轨迹、校正效果）

5. **导出 STAR 文件**
   - 运动校正完成后，导出 `corrected_micrographs.star`

---

#### **步骤2：切换到 cryoSPARC**

1. **在 StructPilot 中切换软件**
   - 左侧边栏 → 软件 → 选择「cryoSPARC」

2. **导入 RELION 数据**
   - 在 cryoSPARC 中创建新项目
   - Import → Import Movies（从 RELION 导出的路径）
   - 或直接导入 corrected micrographs

3. **继续后续流程**
   - CTF Estimation
   - Particle Picking
   - 2D Classification
   - Ab-initio
   - 3D Classification
   - 3D Refinement

---

## 🎓 决赛演示建议

### **演示混合工作流的优势**

```
【0:00-1:00】问题背景
  "很多实验室使用混合工作流：RELION 前期 + cryoSPARC 后期。
   但缺少统一的管理平台。"

【1:00-2:00】解决方案
  "StructPilot 支持 RELION 和 cryoSPARC 两种软件。
   入门模式：清晰的工作流引导
   高级模式：完整的参数配置"

【2:00-3:00】现场演示
  - 选择 RELION
  - 查看「使用说明」
  - 进入参数向导（入门模式）
  - 显示限制提示和切换选项

【3:00-4:00】高级模式演示
  - 切换到高级模式
  - 查看 RELION 卡片库
  - 对话陪跑推荐 RELION 步骤

【4:00-5:00】技术亮点
  - 混合工作流支持
  - 智能引导和切换
  - 统一的知识库和经验管理
```

---

## ✅ 总结

**已实现：**
✅ RELION 模式使用说明（左侧边栏）  
✅ 入门模式限制提示和切换按钮  
✅ 固定参数可编辑提示  
✅ RELION 卡片库集成（高级模式）  
✅ 混合工作流引导  

**设计原则：**
- **入门模式：** 简化流程，引导用户使用主流工具（cryoSPARC）
- **高级模式：** 完整支持，让有经验的用户自由选择
- **混合工作流：** 提供清晰的切换路径和数据衔接建议

**决赛优势：**
1. **实用性强** — 符合真实科研场景
2. **灵活性高** — 支持多种工作流组合
3. **引导清晰** — 避免用户混淆

🎉 **RELION 模式开发完成！**
