# Batch3 → Batch1/Batch2 交叉引用索引

> **目的**: 标注 Batch3 实验室真实 SOP 的每个内容在 Batch1（基础知识库与模板）和 Batch2（完整知识库模板体系）中的对应关系和补充价值。

---

## 索引表

| Batch3 内容 | Batch1 对应 | Batch2 对应 | 补充价值 |
|------------|------------|------------|---------|
| **五阶段完整 workflow**（lab_workflow_full.md） | `01_sop/cryosparc_official_sop.md`（仅通用 14 步） | `Batch2/` 各 Job 分文件 SOP 模板 | ⭐⭐⭐ 填入真实参数+两轮2D+三类精修+RELION桥接 |
| **参数总表**（lab_parameters_master.csv） | `02_parameters/cryosparc_official_parameters.csv`（17条通用参数） | `02_parameters/` 参数模板 | ⭐⭐⭐ 从17条扩展到50+条，全部填入实验室实际值并标注与官方的差异 |
| **挑颗粒方法对比**（lab_particle_picking_comparison.md） | ❌ 无（仅 Blob Picker 的通用说明） | ❌ 无 | ⭐⭐⭐ 填补了整个挑颗粒决策领域空白 |
| **3D精修管线**（lab_3d_refinement_pipeline.md） | `01_sop/cryosparc_official_sop.md` 仅到 Homogeneous | ⚠️ Batch2 有各精修步骤的独立模板但未串联 | ⭐⭐⭐ 将三步串联为完整管线，含参数演进全景表 |
| **RELION桥接**（lab_relion_bridge_guide.md） | ❌ 无 | ❌ 无 | ⭐⭐⭐ 跨软件互操作全新领域 |
| **故障排查**（lab_troubleshooting_notes.md） | `06_review/missing_information.md`（23个Gap） | 部分在 Batch2 troubleshooting 模板中 | ⭐⭐ 从"Gap列表"升级到"已解决的10个真实故障" |
| **运维记录**（lab_workflow_full.md 附录A） | ❌ 无 | ❌ 无 | ⭐⭐ MobaXterm命令、路径结构、权限设置等运维知识 |

---

## 关键补充点详解

### 补充 1：两轮 2D 策略 → 填补 Batch1 最大空白

- Batch1 的 `cryosparc_official_sop.md` 只描述了一轮 2D 分类（100 类）
- Batch3 提供了完整的"第一轮 bin 粗筛 + 第二轮无 bin 精挑"策略，包括：
  - Fourier crop 的加速决策（100~120px、不超过 2^8=128）
  - 两轮的参数差异（res=5Å vs 3Å、class=100 vs 50）
  - 实验室实际效果验证

### 补充 2：Topaz + Template Picker → 全新领域

- Batch1 和 Batch2 都只覆盖了 Blob Picker
- Batch3 新增了两个主流挑颗粒方法：
  - Topaz：含完整的 Train → Extract 流程、模型路径、训练质控
  - Template Picker：含 Create Templates → Template Picking 流程、取向补全策略

### 补充 3：Heterogeneous + Non-uniform → 升级到现代标准

- Batch1 的 SOP 只到 Homogeneous Refinement
- Batch3 补齐了前一步（Heterogeneous 3D分类）和后一步（Non-uniform 非均匀精修）
- 参数从"待填写模板"升级为"实验室经验值"

### 补充 4：RELION 桥接 → 跨软件互操作

- Batch1 和 Batch2 完全没有涉及 cryoSPARC → RELION 的颗粒坐标转换
- Batch3 提供了完整四步流程 + 3 个常见故障的解决方案
- 包含可直接运行的 shell 脚本模板

---

## 使用建议

### 对 StructPilot 竞赛

| 使用场景 | 优先级 | 推荐参考 |
|---------|--------|---------|
| Demo 展示数据 | P0 | Batch3 `lab_workflow_full.md` → 真实 300kV 参数 |
| "怎么挑颗粒" | P0 | Batch3 `lab_particle_picking_comparison.md` → 决策树 |
| "3D精修参数怎么设" | P0 | Batch3 `lab_3d_refinement_pipeline.md` → 全景参数表 |
| "cryoSPARC→RELION" | P1 | Batch3 `lab_relion_bridge_guide.md` → 四步流程 |
| "报错了怎么办" | P1 | Batch3 `lab_troubleshooting_notes.md` → 10个真实故障 |

### 对团队成员培训

- **新人入门**: 先看 Batch2 的分步骤模板（了解每个 Job 是干什么的）→ 再看 Batch3 的完整 workflow（在实际数据上怎么串起来）
- **参数调优**: 对照 Batch3 的 `lab_parameters_master.csv` 中的 `diff_from_official` 列，理解为什么实验室参数和官方 Tutorial 不同
- **故障排查**: 遇到问题直接查 Batch3 的 `lab_troubleshooting_notes.md`，先看有无对应故障

### 对课题组知识积累

Batch3 是**最小可持续维护的知识库**模板：
1. 每个新项目的数据采集参数记录在 `lab_parameters_master.csv`（新增行即可）
2. 每次遇到新故障记录在 `lab_troubleshooting_notes.md`（追加新条目）
3. 每年 review 一次参数是否最优

---

## 三个批次的关系图

```
Batch1 (通用模板)          Batch2 (完整框架)          Batch3 (实验室真实SOP)
─────────────────         ─────────────────         ─────────────────────
14步通用SOP结构     →     18个Job分步骤模板   →     填入了实验室实际参数
17条通用参数        →     参数模板字段         →     50+条真实参数（含diff_from_official）
仅Blob Picker       →     无其他挑颗粒方法     →     Blob+Topaz+Template三方法完整对比
仅Homogeneous       →     各精修独立模板       →     Hetero→Homo→Non-uniform串联管线
无跨软件内容        →     无跨软件内容         →     完整RELION桥接指南
23个Gap             →     空模板               →     10个真实故障+解决方案
```

**一句话**: Batch1 = 骨架，Batch2 = 器官，Batch3 = 血肉（填入真实数据）。
