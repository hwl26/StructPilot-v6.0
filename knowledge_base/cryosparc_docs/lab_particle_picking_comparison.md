# 三种挑颗粒方法对比与决策指南

> **来源**: 实验室 cryoSPARC workflow（Excel + 白板）
> **定位**: 为 StructPilot 提供"帮用户选择挑颗粒方法"的决策知识
> **⚠️**: 具体原理和底层算法请参考 cryoSPARC 官方使用文档

---

## 一、方法速览

| | Blob Picker | Topaz Picking | Template Picker |
|---|---|---|---|
| **方法类型** | 传统图像处理 | 深度学习（监督） | 模板匹配 |
| **是否需要训练/模板** | 否 | 需要先训练 U-Net 模型 | 需要已有 3D 模型生成 2D 投影 |
| **计算速度** | 快 | 训练慢、推理快 | 中等 |
| **对噪声的鲁棒性** | 差（低 SNR 容易漏） | 好 | 中等 |
| **倾向性（bias）** | 有一定取向偏差 | 较小 | 取决于模板的取向覆盖 |
| **典型阶段** | 第一轮初挑 | 第二轮大规模挑 | 补全取向劣势方向 |
| **输入要求** | 只需要 micrograph + CTF | Blob 结果作为 GT + 高质量 micrographs | 已有 3D 模型 + micrographs |
| **输出** | 颗粒坐标 + CTF 元数据 | 颗粒坐标 | 颗粒坐标 |

---

## 二、Blob Picker — 传统初挑

### 原理（简述）

带通滤波 → 局部极值检测 → 按阈值输出候选坐标。

假设：颗粒比背景显著亮或暗，且大小在合理范围内。不依赖模板，完全无监督。

> 具体原理和参数调优细节请参考 cryoSPARC 官方使用文档。

### 适用场景

- ✅ 数据初筛，快速获取候选颗粒
- ✅ 蛋白形状规则、snr 较好的照片
- ✅ 作为 Topaz 的"训练数据生成器"
- ❌ 低对比度、蛋白很小或形状复杂的样本
- ❌ 构象异质性大、取向分布不均

### 实验室参数

| 参数 | 值 | 理由 |
|------|-----|------|
| Min/Max diameter (Å) | Pymol 测定值 (max=min) | 从已知结构测量蛋白外接圆 |
| Min separation (diameters) | 0.6 | 控制相邻颗粒最小间距 |
| Max local maxima | 400 | 视颗粒数量灵活调整 |

### 质控要点

- Blob 挑完后做一轮快速 2D（100 类、res=5Å），看 class average 是否清晰
- 如果 2D 中大量 class 模糊，说明 Blob 参数不合适或数据 SNR 太低

---

## 三、Topaz Picking — 深度学习挑颗粒

### 原理（简述）

**监督学习**：用 Blob + Select 2D 选出的高质量颗粒坐标作为"标准答案（ground truth）"，训练 U-Net 网络学习"什么位置有蛋白颗粒"。训练完成后用模型对所有微图做推理，输出高精度颗粒坐标。

三步走：Train（训练）→ Extract（推理提取坐标）→ 下游处理。

> 具体原理、网络架构和训练策略请参考 Topaz 官方论文和文档。

### 适用场景

- ✅ 低 SNR 数据（深度学习比 Blob 鲁棒得多）
- ✅ 大规模数据集需要自动化挑颗粒
- ✅ 蛋白形态多变、大小不均
- ❌ 数据量太小（< 500 张 micrographs），训练不足
- ❌ 没有 GPU 资源（训练阶段需要 GPU）

### 实验室参数

| 步骤 | 参数 | 值 | 理由 |
|------|------|-----|------|
| 数据准备 | 训练集大小 | ~1000 张好照片 | 通过 Curate Exposures 的 Threshold 筛选 |
| Topaz Train | Expected particles | 450（可调） | 根据单张 micrograph 颗粒数量灵活调整——颗粒多则加、少则减 |
| Topaz Train | Parallel processes | 16（默认） | 并行数，保持默认 |
| Topaz Train | Topaz 路径 | `/home/software/miniconda3/envs/topaz/bin/topaz` | 服务器安装路径 |
| Topaz Extract | Parallel processes | 16（默认） | 推理阶段并行数 |

### 训练质控

- **观察 loss 曲线**：理想状态是 training loss 和 validation loss 都持续下降并收敛
- **过拟合信号**：training loss 很低但 validation loss 不降反升 → 数据量不够或模型太复杂
- **颗粒数量初估**：Expected particles 设太高 → 很多假阳性；设太低 → 漏挑真颗粒

---

## 四、Template Picker — 取向补全

### 原理（简述）

先基于已有 3D 模型生成各方向的 2D 投影（Create Templates），然后用这些投影在微图上做滑窗傅里叶互相关匹配（Template Picking）。分数超过阈值的像素位置输出为候选颗粒坐标。

> 具体原理请参考 cryoSPARC 官方使用文档中关于 Template Matching 的说明。

### 适用场景

- ✅ **取向补全**：Blob/Topaz 倾向性遗漏的取向方向，用对应方向的模板专门补全
- ✅ 已有 3D 初始模型后做第二轮/第三轮精细挑颗粒
- ✅ 蛋白有优势取向（preferred orientation）需要拉回劣势方向的颗粒
- ❌ 没有可靠的 3D 初始模型
- ❌ 模板取向覆盖不全

### 实验室参数

| 步骤 | 参数 | 值 | 理由 |
|------|------|-----|------|
| Create Templates | Num templates | 50 | 默认 50，生成全部方向的投影 |
| Create Templates | Zeropadding factor | 2 | 傅里叶空间补零，实空间插值更精细 |
| Template Picker | Particle diameter (Å) | Pymol 测定值 | 同 Blob |
| Template Picker | Min separation (diameters) | 0.6 | 同 Blob |
| Template Picker | Max local maxima | 100~400 | 劣势取向面颗粒少 → 设低；优势构象颗粒多 → 设高 |

### 取向补全策略

1. 先跑 Blob + Topaz → 跑 2D → Select 2D
2. 观察 class average 的**取向分布**：哪些 Euler 角方向出现得少？
3. 用 Ab-Initio 产出的 3D 模型生成这些**劣势取向方向**的投影作为模板
4. Template Picker 专门在这些方向捕捞，补全取向空间

---

## 五、三方法对比决策树

```
你当前的阶段是？
├── 完全没有颗粒坐标？
│   └── 用 Blob Picker 初挑 → 快速 2D（100类, res=5Å）→ Select 2D
│       ↓ 选出好颗粒后
│       ├── 数据 SNR 高、蛋白简单？→ 直接用 Blob 结果继续
│       └── 数据 SNR 低、样本复杂？→ 进入 Topaz 流程
│
├── 已有 Blob 初挑结果 + Select 2D 的好颗粒？
│   └── 用 Topaz Train（以好颗粒为 GT）→ Topaz Extract 大规模挑
│       ↓
│       注意：Blob + Topaz 结果需 Remove Duplicates 合并
│
├── 已有初始 3D 模型？
│   └── 检查 2D class average 的取向分布
│       ├── 取向均匀？→ 直接进入 3D 精修
│       └── 存在取向劣势？→ Create Templates → Template Picker 补全
│
└── 跨软件需求（cryoSPARC → RELION）？
    └── 挑完后 Remove Duplicates → csparc2star.py 转换 → RELION 端处理
```

---

## 六、组合策略（实验室推荐）

### 标准路径（最常用）

```
Blob Picker (初挑) 
  → 2D Class (100类, 5Å) 
  → Select 2D 
  → Topaz Train（以好class为GT） 
  → Topaz Extract（大规模挑） 
  → Remove Duplicates（合并去重）
```

### 取向补全路径（有优势取向时追加）

```
标准路径结果 
  → Ab-Initio → 3D模型
  → 识别取向劣势方向
  → Create Templates（劣势方向投影） 
  → Template Picker（补全） 
  → Remove Duplicates（与标准路径结果合并）
```

---

## 七、常见问题

### Q: 什么时候该用 Topaz 而不是 Blob？
**A**: 当数据 SNR 低、颗粒小（<100 kDa）、或者 Blob 挑完的 2D class 大量模糊时。Topaz 的学习能力在低 SNR 场景下显著优于 Blob。

### Q: Topaz 训练需要多少数据？
**A**: 实验室经验——约 1000 张好的 micrographs，颗粒总量在数万到数十万级即可。太少（< 500 张）训练不足，太多计算资源浪费。

### Q: Template Picker 和 Topaz 冲突吗？
**A**: 不冲突。Template Picker 的定位是"取向补全"，解决 Blob/Topaz 可能系统性遗漏的取向方向。最佳实践是 Topaz 挑完 → 检查取向分布 → Template Picker 补全劣势方向。

### Q: 三种方法的结果能否直接合并？
**A**: 不能直接拼接——必须过 **Remove Duplicates** 去重后再合并。三种方法可能反复挑到同一个颗粒，不去重会导致下游 3D 重建出现过度拟合和分辨率虚高。
