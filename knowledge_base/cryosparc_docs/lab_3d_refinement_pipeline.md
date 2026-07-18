# 3D 精修管线详解：Heterogeneous → Homogeneous → Non-uniform

> **来源**: 实验室 cryoSPARC workflow（Excel + 白板）
> **定位**: 弥补现有知识库在 3D 精修管线上的最大空白
> **⚠️**: Heterogeneous → Homogeneous → Non-uniform 三步递进逻辑请参考 cryoSPARC 官方文档理解原理，以下参数为本实验室经验值

---

## 一、为什么需要三步精修？

cryoSPARC 的三步精修管线是现代冷冻电镜数据处理的**标准高分策略**：

```
Ab-Initio（粗糙 3D 模型）
    │
    ├── 问题：颗粒混合了多种构象、噪声多，方向不准
    │
    ▼
Heterogeneous Refinement（3D 分类）
    │   "先把混合的颗粒按构象分开"
    │
    ▼
Homogeneous Refinement（全局精修）
    │   "假设单一构象，精细打磨到极限"
    │
    ▼
Non-uniform Refinement（非均匀精修）
    │   "柔性区域+刚性区域分别处理，最后 push 分辨率"
    │
    ▼
最终高分辨密度图
```

> 只做 Homogeneous 是旧版 cryoSPARC 的做法。三步管线是 v3+ 引入 Heterogeneous + v4+ 引入 Non-uniform 后的标准操作。

---

## 二、Heterogeneous Refinement — 3D 分类

### 核心问题

Ab-Initio 产出的 3D 模型是基于**全部颗粒的平均结果**——但实际上蛋白质可能处于多种构象（开/关、有/无配体、柔性域不同位置）。如果颗粒混在一起直接精修，会导致密度图模糊、分辨率上不去。

### 做了什么

**本质是"有参考的 3D 分类"**：不从头找取向，而是用 Ab-Initio 的粗糙 3D 模型作为参考。每颗 2D 颗粒和所有参考模型中投影最像的那个归为一类，然后在类内同时做对齐和精修。

关键：**不要只输入"最好的那个"Ab-Initio class**，把所有 class 都投进去——包括看起来像垃圾的那个。因为"垃圾"类可以充当海绵，把真的坏颗粒吸走，让好类更干净。

### 实验室参数

| 参数 | 值 | 为什么 |
|------|-----|--------|
| Refinement box size (Voxels) | particle直径÷0.96×1.5~2 | 越小对 GPU 越友好。与 Extract 时的 box size 保持一致 |
| Max alignment resolution (Å) | **3** | 比 Ab-Initio 的 10Å 精细得多，但在分类阶段不必 push 到极限 |
| Cache particle images on SSD | **OFF** | 节省空间 |

### 输出与判断

- 输出每个 3D class 的密度图 + 对应的颗粒子集
- **选最好的 class**：密度图最"像蛋白"（二级结构可见、没有碎片噪声）
- **同时保留其他 class**：如果两个 class 都像真的构象，两个都保留分别进入 Homogeneous
- **不好的 class**：直接舍弃

### 常见陷阱

- **Class similarity 太低**（如 0.03）：分类过于激进，可能把一个好构象硬拆成两个
- **只输入一个 Ab-Initio model**：没有"垃圾"类吸收坏颗粒，好类也混着噪声
- **分辨率设太高**：分类阶段不需要，3Å 足够分辨不同构象

---

## 三、Homogeneous Refinement — 全局精修

### 核心问题

Heterogeneous 分好了类，但每类的颗粒取向还不够精确。需要在一个"所有颗粒都是同一个构象"的假设下，用最精细的算法把每个颗粒的对齐推到极限。

### 做了什么

Homogeneous Refinement 的三大核心算法：

1. **Per-Particle CTF Correction**（逐颗粒 CTF 校正）：每张 micrograph 的 CTF 不同，每个颗粒在 micrograph 上的位置不同 → 每个颗粒的 CTF 也不同。逐颗粒校正比全局 CTF 精确得多。

2. **Gold-Standard FSC**（黄金标准 FSC）：把颗粒随机分成两半，独立重建两个 half map，用 FSC=0.143 标准判定真实分辨率。这避免了"对着噪声反复拟合"导致的假高分辨率。

3. **Ewald Sphere Correction**（Ewald 球校正）：非零频率下 Ewald 球弯曲引入的相位误差。高分辨重建（< 3.5Å）必须校正。

### 实验室参数

| 参数 | 值 | 为什么 |
|------|-----|--------|
| Max alignment resolution (Å) | **3** | push 分辨率，Homogeneous 阶段 vs Heterogeneous 的区别在于用了全频带信号 |
| Cache particle images on SSD | **OFF** | |

### 输出解读

| 输出 | 含义 | 怎么用 |
|------|------|--------|
| Half Map A + B | 两半独立重建 | 用于 FSC 计算，判断真实分辨率 |
| Full Map | A+B 合并+锐化 | 最终密度图（Homogeneous 版本） |
| **FSC Curve** | **分辨率评估** | FSC=0.143 处的横坐标 = 报告分辨率 |
| alignments3D | 每颗粒的精确 (φ, θ, ψ) | 传给 Non-uniform 继续用 |

> 如何看 FSC 曲线是否有问题：如果曲线在低分辨率处震荡或突然下降，说明数据有问题（如颗粒方向不准、分类没分干净）。

---

## 四、Non-uniform Refinement — 非均匀精修（最终 push）

### 核心问题

Homogeneous 假设蛋白是**刚体**——但真实蛋白总有柔性区域（loop、domain 的微小转动）。一刀切的 B-factor 锐化会同时放大高频信号 + 柔性区域噪声。Non-uniform 用**数据驱动、逐频点加权**替代一刀切 B-factor，对柔性区域更友好。

### 做了什么

- **逐频率点加权锐化**：不是用一个 B-factor 整张图一起锐化，而是每个频率 bin 独立计算最佳权重
- **局部分辨率估计**：输出每一体素的分辨率热力图（local resolution map），方便判断哪些区域好、哪些区域需要改进
- **动态软掩膜**（Dynamic Mask）：自动识别蛋白 vs 溶剂区域，排除溶剂噪声的干扰——不需要手动生成静态 mask

### 实验室参数

| 参数 | 值 | 为什么 |
|------|-----|--------|
| Max alignment resolution (Å) | **3** | 刚性+柔性区域同步精修 |
| Dynamic mask use absolute value | **OFF** | 常规 OFF。算法自动计算软掩膜，排除溶剂噪声 |
| Cache particle images on SSD | **OFF** | |

### 输出

Non-uniform 直接输出**最终精修 map**——通常分辨率比 Homogeneous 提高 0.1-0.3 Å，柔性区域的局部分辨率改善最明显。

---

## 五、三步管线参数演进全景

| | Heterogeneous | Homogeneous | Non-uniform |
|---|---|---|---|
| **目的** | 3D 分类（分构象） | 全局精修（push 分辨率） | 非均匀精修（最终 push） |
| **假设** | 颗粒来自不同的构象 | 颗粒是同一构象的刚体 | 蛋白有柔性区域 |
| **对齐分辨率** | 3Å | 3Å | 3Å |
| **输入** | 全部 Ab-Initio models | 选最好的 Hetero class | Homogeneous 最佳 class |
| **CTF 校正** | Per-particle | Per-particle（全频带） | 继承 Homogeneous |
| **掩膜** | 无 | 可选静态 mask | 动态软掩膜（自动） |
| **锐化** | 无 | B-factor（一刀切） | 逐频点加权 |
| **关键输出** | 分好类的颗粒子集 | Half Maps + FSC Curve | 最终 map + local resolution |

---

## 六、常见问题

### Q: 三步都要做吗？能不能跳过 Non-uniform？
**A**: 都可以跳过，但有代价：
- 跳过 Heterogeneous → 颗粒混在一起，分辨率上限被构象异质性卡住
- 跳过 Non-uniform → 对柔性蛋白来说损失 0.1-0.3 Å 分辨率，但刚体蛋白影响较小

### Q: Heterogeneous 的 class similarity 设多少？
**A**: 默认 0.1 适合大多数情况。如果知道样本有明显不同的构象（如 apo vs holo），可以调低到 0.03 让分类更激进。

### Q: Homogeneous 的 FSC 曲线显示分辨率 4.5Å，Non-uniform 能做到多少？
**A**: 一般提升 0.1-0.3 Å。不会发生"从 4.5 跳到 3.0"的魔法——Non-uniform 消化的是 B-factor 锐化的误差和柔性区域的模糊，真正的物理极限还是由颗粒数量和信噪比决定。

### Q: 跑 Homogeneous 时要不要输入 mask？
**A**: cryoSPARC 推荐——可选，但如果有可靠 mask 输入会让结果更干净。如果没有，Homogeneous 也能跑，但 Non-uniform 必须跑（因为它自带动态 soft mask）。
