# Batch3 — 实验室真实 CryoSPARC SOP

> **整理日期**: 2026-07-02
> **数据来源**:
> - 腾讯文档智能白板（可视化流程）
> - Excel: `cryosparc lab workflow.xlsx`（101行×9列，完整参数+备注）
> **定位**: 300kV Titan Krios 真实单颗粒数据处理管线，基础款 workflow
> **用户审核**: ✅ 2026-07-02 已审核确认

---

## 目录结构

```
Batch3_0702_实验室真实SOP/
├── README_实验室SOP概述.md               ← 本文件
├── lab_workflow_full.md                  ← ★ 主体：五阶段完整工作流（含两轮2D+RELION桥接）
├── lab_parameters_master.csv             ← 50+条参数总表（含与官方Tutorial差异对比）
├── lab_particle_picking_comparison.md    ← 三种挑颗粒方法（Blob/Topaz/Template）对比与决策指南
├── lab_3d_refinement_pipeline.md         ← Hetero→Homo→Non-uniform三级精修管线详解
├── lab_relion_bridge_guide.md            ← cryoSPARC→RELION互操作完整指南（含shell脚本）
├── lab_troubleshooting_notes.md          ← 10个真实故障排查记录
└── cross_reference_to_batch1_batch2.md   ← 与现有知识库的交叉引用索引
```

---

## 与现有知识库（Batch1+Batch2）的核心差异

这份实验室 SOP 不是"又一个模板"——它是**填入真实参数的完整工作流**：

| 维度 | Batch1+Batch2（原有） | Batch3（新增） |
|------|---------------------|---------------|
| 参数状态 | "待填写"占位符 | 实验室实际值 |
| 显微镜参数 | 200kV / 0.5585 Å/px / 69 e⁻/Å² | **300kV / 0.96 Å/px / 50 e⁻/Å²** |
| 2D策略 | 单轮 | **两轮**（bin粗筛→无bin精挑） |
| 挑颗粒方法 | 仅Blob Picker | **三种**：Blob + Topaz + Template Picker |
| 3D精修 | 仅Homogeneous | **三级**：Heterogeneous→Homogeneous→Non-uniform |
| 跨软件 | 无 | **完整RELION桥接** |
| 故障排查 | 理论模板 | **10个真实生产故障+解决方案** |

---

## 使用建议

### 如果你是 StructPilot 参赛队员

1. **Demo 数据** → 直接用 Batch3 的 300kV 真实参数替代通用的 beta-gal 参数
2. **高频问题** → "怎么挑颗粒" 参考 `lab_particle_picking_comparison.md`（含决策树）
3. **答辩素材** → "我们整合了真实实验室操作惯例" 有据可查

### 如果你是实验室新成员

1. **入门路线**: `lab_workflow_full.md`（通读流程）→ `lab_parameters_master.csv`（查参数含义）→ `lab_troubleshooting_notes.md`（避坑）
2. **遇到具体操作**: 直接跳到对应章节查看参数+note

### 如果你是课题组 PI/Manager

1. **知识沉淀**: 这是课题组 SOP 文档化的起点——有新项目时新增参数行、新故障时追加条目
2. **新人培训**: 用这份文档作为 onboarding 材料，减少一对一教学时间

---

## 快速导航

| 你想做什么？ | 看哪个文件 |
|------------|-----------|
| 完整走一遍数据处理管线 | `lab_workflow_full.md` |
| 查某个 cryoSPARC Job 的参数怎么设 | `lab_parameters_master.csv` |
| 决定用哪种方法挑颗粒 | `lab_particle_picking_comparison.md` |
| 理解 3D 精修为什么分三步 | `lab_3d_refinement_pipeline.md` |
| 把 cryoSPARC 颗粒转到 RELION | `lab_relion_bridge_guide.md` |
| 程序报错了 | `lab_troubleshooting_notes.md`（先查再试） |
| 想对比官方 Tutorial 和实验室的区别 | `cross_reference_to_batch1_batch2.md` |

---

## ⚠️ 注意事项

- 本 workflow 为**基础款**步骤与参数设置，可在此基础上扩展更复杂的处理策略
- 所有参数基于 300kV Titan Krios / 0.96 Å/px 采集条件，使用不同配置时需调整
- 服务器路径已脱敏，实际使用时替换为你的实际路径
- Topaz expected particles 为可调参数，需根据单张 micrograph 的实际颗粒数量灵活调整
- Heterogeneous → Homogeneous → Non-uniform 三步递进逻辑请参考 cryoSPARC 官方文档，参数为本实验室经验值
- csparc2star.py 的 --box 参数需与 cryoSPARC Extract 时的 box size 保持一致
- Blob/Topaz/Template 三种方法的输入/输出关系为实验室标准方案，具体原理请参考官方使用文档
