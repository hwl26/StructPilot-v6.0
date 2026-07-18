# 实验室 CryoSPARC 数据分析真实 SOP（完整版）

> **来源**: `cryosparc lab workflow.xlsx`（101行×9列）+ 腾讯文档白板
> **整理日期**: 2026-07-02
> **原始数据**: 300kV Titan Krios, pixel=0.96 Å/px, dose=50 e⁻/Å²
> **数据项目示例**: `20260521_NLEL_Au_G2 / CS-nlel-card-20260521`
> **⚠️ 注意**: 本文件包含实验室真实参数，请根据你的蛋白和采集条件调整。
> **📌 定位**: 这是当前实验室使用的**基础款** workflow 步骤与参数设置，可在此基础上扩展更复杂的处理策略。

---

## 概览：五阶段流程图

```
一、数据导入与预处理
  ├── 终端赋权 (setfacl)
  ├── Import Micrographs
  ├── Patch CTF
  └── Manual Curate Exposures
        │
二、挑选颗粒（三种方法任选或组合）
  ├── 2.1 Blob Picker ──────────────────────┐
  ├── 2.2 Topaz Picking (Train → Extract) ──┤
  └── 2.3 Template Picker ──────────────────┘
        │
三、第一轮 Extract + 2D（粗筛，有 bin）
  ├── Extract (Fourier crop ≈ 100-120 px)
  ├── 2D Classification (100 classes, res=5Å)
  └── Select 2D
        │
四、第二轮 Extract + 2D（精挑，无 bin）
  ├── Extract (关闭 Fourier crop)
  ├── 2D Classification (50 classes, res=3Å)
  └── Select 2D
        │
五、3D 重构与精修
  ├── Remove Duplicates
  ├── Ab-Initio (3 classes, res=10Å)
  ├── Heterogeneous Refinement (3D 分类)
  ├── Homogeneous Refinement (全局精修)
  └── Non-uniform Refinement (最终 push 分辨率)
```

---

## 一、数据导入与预处理

### 1.0 前置操作：终端赋权

在 MobaXterm 终端执行，为 cryoSPARC 用户赋予原始数据的读权限：

```bash
setfacl -m u:cryosparcuser:rwx -R 【原始数据目录】
```

**操作要点**:
- 需要确认工作站站点编号（225/226/227）
- 注意文件不是软连接过去的，是实际路径
- 需要在 motion correction 之后的 `.eer` 目录赋予权限

### 1.1 Import Micrographs

**cryoSPARC Job Type**: Import Movies

| 参数 | 值 | 备注 |
|------|-----|------|
| Micrographs data path | `../MotionCorr/job002/Movies/*EER.mrc` | 注意输入的是 motion-corrected 之后的 `.mrc`，不是原始 `.eer` |
| Pixel size (Å) | **0.96** | |
| Accelerating Voltage (kV) | **300** | Titan Krios |
| Spherical Aberration (mm) | **2.7** | Cs 值 |
| Total exposure dose (e⁻/Å²) | **50** | |

> 💡 **与官方 Tutorial 的差异**: 官方使用 200kV / pixel=0.5585 / dose=69，实验室是 300kV / pixel=0.96 / dose=50，这是真实数据采集参数。

### 1.2 Patch CTF Estimation

**cryoSPARC Job Type**: Patch CTF Estimation

| 参数 | 值 |
|------|-----|
| Number of GPUs to parallelize | 视情况（根据可用 GPU 调整） |

**作用**: 为每张 micrograph 的每个 patch 估算 CTF（衬度传递函数）参数，是后续所有图像处理的基础。

### 1.3 Manual Curate Exposures

**cryoSPARC Job Type**: Curate Exposures

**操作**: 交互式筛选，删除以下不合格的照片：
- 像散（astigmatism）过高
- 冰层太厚
- 污染/破损/看不清
- CTF fit 质量差

**输出**: 筛选后的高质量 micrographs（含 CTF 信息）

---

## 二、挑选颗粒（三种方法）

> 三种方法可独立使用或组合使用。实验室常用路径：Blob 初挑 → 选好 class → 作为 Topaz 训练数据 → Topaz 大规模挑 → 或直接用 Template Picker 做取向补全。
> 
> **三种方法的输入/输出关系为当前实验室标准化方案，具体原理和底层算法请参考 cryoSPARC 官方使用文档。**

---

### 2.1 Blob Picker

**cryoSPARC Job Type**: Blob Picker

**原理**: 带通滤波 → 找局部极值 → 输出坐标。不依赖模板，纯粹基于"颗粒比背景亮/暗、大小在已知范围内"的假设。具体原理和高级用法请参考 cryoSPARC 官方使用文档。

**Input**: Manual Curate Exposures 筛选后的照片（含 CTF 信息）

**Output**: 候选颗粒坐标 + CTF 参数和得分元数据（透传原图 + CTF 信息）

| 参数 | 值 | 备注 |
|------|-----|------|
| Minimum particle diameter (Å) | **Pymol 测定值** (max=min) | 通过数据库结构模型在 PyMOL 中测定蛋白外接圆直径 |
| Maximum particle diameter (Å) | **同 min** | |
| Min. separation dist (diameters) | **0.6** | 相邻颗粒最小间距（以颗粒直径为单位） |
| Maximum number of local maxima to consider | **400** | 视颗粒数量灵活调整 |

---

### 2.2 Topaz Picking

> Topaz（深度学习挑颗粒）分三步：先手动选好照片做训练集 → 训练 U-Net 模型 → 用训练好的模型大规模挑颗粒。

#### 2.2.1 Manual Curate Exposures（为 Topaz 训练准备数据）

| 参数 | 值 | 备注 |
|------|-----|------|
| Threshold (Number of particles) | 调整至约 **1000 张**好照片 | 太多计算慢，太少训练不足 |

**说明**: 从 Blob Picker 的结果中选择约 1000 张质量好的 exposures 作为 Topaz 训练集。

#### 2.2.2 Topaz Train

**cryoSPARC Job Type**: Topaz Train

**原理**: **监督学习**——用你已经挑好的颗粒坐标当"标准答案（ground truth）"，训练一个 U-Net 卷积神经网络学会识别"什么位置长着蛋白颗粒"。训练好之后就是"AI 挑颗粒专家"，比 Blob 聪明得多。

**Input**: 2.2.1 选出的精英照片 + Blob Picker 后 Select 2D 选出的好颗粒坐标

**Output**: 训练好的 Topaz 模型

| 参数 | 值 | 备注 |
|------|-----|------|
| Path to Topaz executable | `/home/software/miniconda3/envs/topaz/bin/topaz` | Topaz 可执行文件路径 |
| Number of parallel processes | **16**（默认） | Topaz 并行进程数，一般保持默认 |
| Expected number of particles | **450**（可调） | 根据单张 micrograph 的颗粒数量灵活调整——颗粒多则适当加、少则减。一般设 400 左右起步 |

**质控**: 
- 观察训练曲线：理想状态是 loss 持续下降并收敛
- 警惕**过度拟合**——训练 loss 很低但验证 loss 不降反升

#### 2.2.3 Topaz Extract

**cryoSPARC Job Type**: Topaz Extract

**原理**: 用训练好的 model 作为模板，在所有原始照片里把长得像颗粒的地方圈出来。这一步只输出颗粒坐标信息，还没裁切。

**Output**: 颗粒坐标信息

| 参数 | 值 |
|------|-----|
| Path to Topaz executable | `/home/software/miniconda3/envs/topaz/bin/topaz` |
| Number of parallel processes | **16** |

---

### 2.3 Template Picker

> 基于已有 3D 模型生成 2D 投影模板，用于补全取向劣势方向的颗粒。

#### 2.3.1 Create Templates

**cryoSPARC Job Type**: Create Templates

**原理**: 用已有的 3D 模型生成各个方向的 2D 投影，作为捞颗粒的"标准像"。

**Input**: 之前 Blob + Topaz 去重后颗粒重构生成的 3D 模型

**Output**: 所有方向的 2D 投影图像

| 参数 | 值 | 备注 |
|------|-----|------|
| Number of equally-spaced templates | **50** | 默认 50，生成全部方向的投影 |
| Zeropadding factor for interpolation | **2** | 在傅里叶空间给模板"补零"，让实空间插值得更精细 |

#### 2.3.2 Template Picking

**cryoSPARC Job Type**: Template Picker

**原理**: 模板做 FFT → 在微图上滑窗扫描（同时尝试不同旋转角度）→ 计算互相关系数 → 分数超阈值的输出为颗粒坐标。

**Input**: 上一步生成的投影 + Accept 的所有 micrographs

**Output**: 颗粒坐标信息

| 参数 | 值 | 备注 |
|------|-----|------|
| Particle diameter (Å) | Pymol 测定值 (max=min) | 同 Blob |
| Min. separation dist (diameters) | **0.6** | |
| Maximum number of local maxima | **100~400** | 投影像少的面设低，颗粒多/优势构象设高 |

> 💡 **取向补全策略**: 用 Select 2D 识别出劣势取向方向，选择那些方向的投影作为模板。Template Picker 可以专门补全 Blob/Topaz 方法倾向性遗漏的方向。

---

## 三、第一轮 Extract + 2D Classification（粗筛）

### 3.1 Extract From Micrographs (Round 1)

**cryoSPARC Job Type**: Extract From Micrographs

**Input**: 上一阶段 particle picking 的颗粒坐标信息

**Output**: 从 micrographs 中按 box size 裁切下来的颗粒小图

| 参数 | 值 | 备注 |
|------|-----|------|
| Number of GPUs to parallelize | 视情况 | |
| Extraction box size (pix) | **particle直径(Å) ÷ 0.96(Å/pix) × 1.5~2** | 关键公式！ |
| Fourier crop to box size (pix) | **100~120**（2的幂） | ⚠️ **第一轮有 bin**，像素合并加速计算。一般不超过 2^8=128 方可保证计算效率 |

> 📐 **Box size 计算公式**（实验室实用版）：
> ```
> box_size = particle_diameter_Å / pixel_size_Å × (1.5 ~ 2.0)
> 例：直径 120Å / 0.96 Å/pix × 1.5 ≈ 188 pix → 取 192（64 的倍数）
> ```

### 3.2 2D Classification (Round 1)

**cryoSPARC Job Type**: 2D Classification

**原理**: 按长得像不像分成 100 堆，每堆拼一张"平均脸"——清晰的 face 是真蛋白颗粒，模糊的那堆是垃圾直接扔掉。

**Input**: 上一步 Extract 的颗粒小图

**Output**: 分类后的颗粒 + 各类的 2D class average 图像

| 参数 | 值 | 备注 |
|------|-----|------|
| Number of 2D classes | **100** | 第一轮多分类，根据颗粒数量级确定。数量多 → 多分类（但计算久） |
| Maximum resolution (Å) | **5** | 低频信号分出大概轮廓即可 |
| Circular mask diameter (Å) | **particle直径 ÷ 0.9** | 限制颗粒信号范围，alignment 中间的信号圈 |
| Number of online-EM iterations | **40** | 分类迭代轮次，越多收敛可能性越大 |
| Cache particle images on SSD | **OFF** | 减少运算缓存占空间 |
| Number of GPUs to parallelize | 视情况 | |

### 3.3 Select 2D (Round 1)

**cryoSPARC Job Type**: Select 2D Classes

**操作**: 交互式选择，挑出以下特征的好 class：
- 不同 view（取向）都覆盖
- 轮廓清晰
- 二级结构明显的

**Input**: 上一轮 particles + class average 信息

**Output**: 选出的好 class 对应的颗粒子集

---

## 四、第二轮 Extract + 2D Classification（精挑）

> 🔑 **两轮策略的核心逻辑**: 第一轮有 bin（Fourier crop）→ 快速粗筛，扔掉明显垃圾。第二轮无 bin（关闭 crop）→ 在高分辨率下精细挑选。

### 4.1 Extract From Micrographs (Round 2)

| 参数 | 值 | 备注 |
|------|-----|------|
| Number of GPUs to parallelize | 视情况 | |
| Extraction box size (pix) | 同第一轮 | 公式不变 |
| Fourier crop to box size (pix) | **关闭（不 bin）** | ⚠️ 第二轮精细挑，保留原始分辨率 |

### 4.2 2D Classification (Round 2)

| 参数 | 值 | 备注 |
|------|-----|------|
| Number of 2D classes | **50** | 第一轮已分走坏的，减少 class 加快计算 |
| Maximum resolution (Å) | **3** | ⚠️ **push 高频信号**，比第一轮精细得多 |
| Circular mask diameter (Å) | particle直径 ÷ 0.9 | 同第一轮 |
| Number of online-EM iterations | **40** | 同第一轮 |
| Cache particle images on SSD | **OFF** | 同第一轮 |
| Number of GPUs to parallelize | 视情况 | |

### 4.3 Select 2D (Round 2)

操作同第一轮，在更高分辨率下进一步精选。

---

## 五、3D 重构与精修

> **Heterogeneous → Homogeneous → Non-uniform 三步递进为当前实验室标准精修管线。原理请参考 cryoSPARC 官方文档理解各算法细节，以下参数为本实验室总结的经验值。**

### 5.1 Remove Duplicates

**cryoSPARC Job Type**: Remove Duplicates

**原理**: 把距离小于阈值（通常为颗粒直径的 0.5-1 倍）的重复坐标合并。不合并会导致一个颗粒被反复计算，污染 2D 分类，下游 3D 重建出现过度拟合、分辨率虚高。

**Input**: 以上三种 picking 路线选出的 Select 2D 颗粒集合

**Output**: 去重合并后的好颗粒全集

| 参数 | 值 |
|------|-----|
| 所有参数 | default |

---

### 5.2 Ab-Initio Reconstruction

**cryoSPARC Job Type**: Ab-Initio Reconstruction

**原理**: 从数十万张 2D 颗粒小图反推出蛋白 3D 密度图——不需要任何先验结构。cryoSPARC 通过随机梯度下降（SGD）生成随机模型，与投影叠加，找最像的角度，反复迭代直到收敛。

> "Ab-Initio 就是从无数张模糊的 2D 照片，反推出拍摄对象的 3D 形状——核心难题是每张照片的角度未知，算法通过迭代猜测角度+反向投影来逐步逼近真相，就像拼一幅没有参考图的 10 万块拼图。"

**Input**: 去重合并后的好颗粒

**Output**: 3 个初始 3D 模型 + 颗粒集

| 参数 | 值 | 备注 |
|------|-----|------|
| Number of Ab-Initio classes | **3** | 一般设 3 类 |
| Maximum resolution (Å) | **10** | 初始模型分辨率设低 |
| Symmetry | **视蛋白而定** | 不对称选 C1 |
| Class similarity | **0.1** | default=0.1；想分得更开可调到 0.03 |

---

### 5.3 Heterogeneous Refinement（异质性精修 = 3D 分类）

**cryoSPARC Job Type**: Heterogeneous Refinement

**原理**: 用多个已有 3D 模型当"种子"，把混合的颗粒按真实 3D 构象分到不同类，同时从头细化每个类。本质就是 **3D 分类**。

关键：Heterogeneous Refinement 不从头找朝向。它拿 Ab-Initio 产出的粗糙 3D 模型作为参考，每颗 2D 颗粒和所有参考模型中投影最像的那个归为一类。

**Input**: 去重后的颗粒 + Ab-Initio 生成的所有初始模型（好坏都要）

**Output**: 更精细分类的模型 + 颗粒集

| 参数 | 值 | 备注 |
|------|-----|------|
| Refinement box size (Voxels) | **particle直径 ÷ 0.96 × 1.5~2** | 同之前的 box size，越小对 GPU 越友好 |
| Max alignment resolution (Å) | **3** | 比初始模型的 10Å 精细得多 |
| Cache particle images on SSD | **default OFF** | 减少运算缓存 |

---

### 5.4 Homogeneous Refinement（同质性精修 = 全局精修）

**cryoSPARC Job Type**: Homogeneous Refinement

**原理**: 假设所有颗粒来自同一个 3D 构象，用最精细的算法打磨到极限分辨率。三大核心算法：
1. **Per-Particle CTF Correction**（逐颗粒 CTF 校正）
2. **Gold-Standard FSC**（黄金标准分辨率评估）
3. **Ewald Sphere Correction**（Ewald 球校正）

**Input**: 只选上一个 Heterogeneous 中最好的 class + volume

**Output**:

| 输出 | 说明 |
|------|------|
| Half Map A + Half Map B | 两半独立重建，用于 FSC 计算 |
| Full Map | A+B 合并 + 锐化后的最终密度图 |
| FSC Curve | 分辨率评估曲线 |
| alignments3D | 每颗颗粒的最终精确朝向 (φ, θ, ψ) + 平移 |

| 参数 | 值 | 备注 |
|------|-----|------|
| Maximum align resolution (Å) | **3** | 同质对齐，push 分辨率 |
| Cache particle images on SSD | **default OFF** | |

---

### 5.5 Non-uniform Refinement（非均匀精修 = 最终 push）

**cryoSPARC Job Type**: Non-uniform Refinement

**原理**: Homogeneous Refinement 的进化版——用数据驱动的逐频点权重替代一刀切的 B-factor 锐化，一步输出最终密度图 + 局部分辨率。对结构柔性区域友好，是**高分辨率重建最关键的最后一步**。

> "Non-uniform Refinement 是 Homogeneous 的进化版——用数据驱动的逐频点权重替代一刀切的 B-factor 锐化。"

**Input**: 上一个 Homogeneous 中最好的 class + volume + mask

**Output**: 最终精修 map

| 参数 | 值 | 备注 |
|------|-----|------|
| Maximum align resolution (Å) | **3** | 刚性和柔性区域同步精修，push 最终分辨率 |
| Dynamic mask use absolute value | **OFF** | 常规 off。算法会自动计算软掩膜（soft mask），排除溶剂噪声 |
| Cache particle images on SSD | **default OFF** | |

---

## 附：RELION 桥接流程

> 当需要将 cryoSPARC 中选好的颗粒拿到 RELION 继续处理时，使用以下流程。

### 环境准备

```bash
conda activate pyem
```

需要安装 `pyem` 工具包（`csparc2star.py` 来自该工具包）。

### 步骤 1：找到 RELION 端的 motion-corrected movies 路径

```bash
cd 【motion correction 输出目录】
# 例：cd /fs/pool/pool-train/EM_data/.../MotionCorr/job002/Movies
```

### 步骤 2：cryoSPARC 颗粒坐标 → RELION star 格式转换

```bash
csparc2star.py \
  --box 240 \
  --swapxy \
  --inverty \
  【cryoSPARC颗粒坐标.cs】 \
  【cryoSPARC颗粒结构信息_passthrough.cs】 \
  【输出star文件名】 \
  --strip-uid
```

**各参数含义**:

| 参数 | 含义 |
|------|------|
| `--box 240` | 告诉 RELION 颗粒框大小（像素）。**注意：此值取决于你最初在 cryoSPARC 中 Extract 时设置的 box size，需要保持一致**。240 为示例值 |
| `--swapxy` | 交换 X/Y 坐标（cryoSPARC 和 RELION 坐标系兼容处理） |
| `--inverty` | 翻转 Y 坐标（cryoSPARC 和 RELION 的 Y 轴方向不同） |
| 输入 1 | 颗粒坐标信息（`particles_kept.cs`） |
| 输入 2 | 颗粒结构信息（`_passthrough_particles_kept.cs`） |
| 输出 | 生成的 `.star` 文件名 |
| `--strip-uid` | 去掉 UID 字段，让输出更干净 |

### 步骤 3：修改 star 文件路径

将 cryoSPARC 的路径格式改为 RELION 的路径格式：

```bash
vi 【生成的star文件】
:%s #【cryoSPARC路径前缀】#【RELION路径前缀】#g
:wq
```

**例**:
```bash
vi J25_particle.star
# 查看图片路径格式
:%s #J3/Import/ #MotionCorr/job002/Movies/ #g
gg      # 快速回到文件开头
:wq     # 保存退出
```

### 步骤 4：RELION 端 CTF 重算

之前的 CTF 是在 cryoSPARC 里算的，到 RELION 后需要重算一次用于后续精修。

### 故障排查：opticsGroup 命名不一致

**问题**: 第二套数据导入后 `opticsGroup1` 命名变化导致 RELION 报错。

**解决**: 检查并统一所有 star 文件中的 opticsGroup 命名。

---

## 参数速查表

### 所有参数汇总（含两轮 2D 对比）

| 参数 | 数据导入 | Blob | Topaz | Template | Extract 1st | 2D 1st | Extract 2nd | 2D 2nd | Ab-Initio | Hetero | Homo | Non-uniform |
|------|---------|------|-------|----------|------------|--------|-------------|--------|-----------|--------|------|-------------|
| Pixel size (Å) | **0.96** | — | — | — | — | — | — | — | — | — | — | — |
| Voltage (kV) | **300** | — | — | — | — | — | — | — | — | — | — | — |
| Cs (mm) | **2.7** | — | — | — | — | — | — | — | — | — | — | — |
| Dose (e⁻/Å²) | **50** | — | — | — | — | — | — | — | — | — | — | — |
| Min diameter (Å) | — | Pymol | — | Pymol | — | — | — | — | — | — | — | — |
| Max diameter (Å) | — | =min | — | =min | — | — | — | — | — | — | — | — |
| Separation (diam) | — | **0.6** | — | **0.6** | — | — | — | — | — | — | — | — |
| Max local maxima | — | **400** | — | **100~400** | — | — | — | — | — | — | — | — |
| Expected particles | — | — | **450** | — | — | — | — | — | — | — | — | — |
| Parallel processes | — | — | **16** | — | — | — | — | — | — | — | — | — |
| Templates | — | — | — | **50** | — | — | — | — | — | — | — | — |
| Zeropadding | — | — | — | **2** | — | — | — | — | — | — | — | — |
| Extraction box | — | — | — | — | **公式** | — | 同 | — | — | — | — | — |
| Fourier crop | — | — | — | — | **100~120** | — | **OFF** | — | — | — | — | — |
| Number of classes | — | — | — | — | — | **100** | — | **50** | **3** | — | — | — |
| Max resolution (Å) | — | — | — | — | — | **5** | — | **3** | **10** | **3** | **3** | **3** |
| Mask diameter | — | — | — | — | — | **diam/0.9** | — | **diam/0.9** | — | — | — | — |
| EM iterations | — | — | — | — | — | **40** | — | **40** | — | — | — | — |
| Cache particles | — | — | — | — | — | **OFF** | — | **OFF** | — | **OFF** | **OFF** | **OFF** |
| Class similarity | — | — | — | — | — | — | — | — | **0.1** | — | — | — |
| Symmetry | — | — | — | — | — | — | — | — | **C1/视蛋白** | — | — | — |
| Refine box (voxels) | — | — | — | — | — | — | — | — | — | **公式** | — | — |
| Dynamic mask | — | — | — | — | — | — | — | — | — | — | — | **OFF** |

> 📐 **Box size 公式**: `particle直径(Å) ÷ 0.96(Å/pix) × (1.5 ~ 2.0)` → 取整到 64 的倍数
> 📐 **Mask diameter 公式**: `particle直径(Å) ÷ 0.9`

---

## 附录 A：实验室运维记录

### MobaXterm 操作
```bash
# 赋权
setfacl -m u:cryosparcuser:rwx -R 【数据目录】

# 确认工作站站点（225/226/227）
# 注意：文件不是软连接，是实际路径
```

### 数据目录结构
```
/fs/pool/pool-train/EM_data/
└── 【日期_项目名_样品名】/
    ├── MotionCorr/
    │   └── job002/Movies/  ← motion-corrected EER (.mrc)
    ├── cryoSPARC projects/
    │   └── CS-【项目】-【日期】/
    │       ├── J112/       ← 项目编号示例
    │       └── J25/        ← 项目编号示例
    └── RELION/
```

### 常用命令备忘
```bash
# 激活 pyem 环境（cryoSPARC → RELION 转换）
conda activate pyem

# 查看 micrograph 文件列表
ls MotionCorr/job002/Movies/*EER.mrc

# vi 快速全局替换
:%s #旧路径#新路径#g
gg   # 跳到文件开头
:wq  # 保存退出
```

---

## 附录 B：与官方 Tutorial 的关键差异

| 方面 | 官方 Tutorial (NCCAT beta-gal) | 实验室真实 SOP | 影响 |
|------|-------------------------------|---------------|------|
| 显微镜 | 200 kV | **300 kV** Titan Krios | 信号更强，参数需要相应调整 |
| Pixel size | 0.5585 Å/px | **0.96 Å/px** | Box size 计算公式完全不同 |
| 电子剂量 | 69 e⁻/Å² | **50 e⁻/Å²** | 对 CTF 和颗粒信噪比有影响 |
| 2D 策略 | 单轮 | **两轮**（bin 粗筛 → 无 bin 精挑） | 实验室标准操作，兼顾速度与精度 |
| 挑颗粒 | 仅 Blob Picker | **三种方法**（Blob + Topaz + Template） | 深度学习挑颗粒已成为主流 |
| 3D 精修 | Homogeneous only | **三级：Hetero → Homo → Non-uniform** | modern cryoSPARC 标准管线 |
| RELION 桥接 | 无 | **完整流程**（pyem + star 修改 + CTF 重算） | 跨软件互操作的真实需求 |

---

> **✅ 用户审核状态（2026-07-02）**：
> - [x] Pixel size (0.96) — 确认为常用单颗粒数据采集模式，核实通过
> - [x] Box size 公式系数（1.5~2.0）— 确认为常用范围，通过
> - [x] 第一轮 Fourier crop (100~120 px) — 确认，不超过 128 保证计算效率
> - [x] Topaz expected particles — 已标注为可调参数（根据单张 micrograph 颗粒数量灵活调整）
> - [x] parallel=16 — 确认为默认参数
> - [x] 两轮 2D 策略（bin 粗筛 → 无 bin 精挑）— 描述准确，通过
> - [x] 三种挑颗粒方法的输入/输出关系 — 确认为实验室标准方案，原理需参考官方文档
> - [x] Heterogeneous → Homogeneous → Non-uniform 三步递进 — 参数为实验室经验值，原理需参考官方文档
> - [x] RELION 桥接：csparc2star.py --box 参数 — 已标注需根据实际 box size 值确定
> - [x] star 文件 `:%s` 路径替换命令 — 正确
> - [x] opticsGroup1 故障描述 — 准确
> - [x] 服务器路径脱敏 — 已完成
> - [x] 定位标注 — 已标注为"基础款" workflow
