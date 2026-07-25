# cryoSPARC Workflow 格式分析（基于真实导出文件）

## 1. 顶层结构

```json
{
  "_id": "workflow唯一ID",
  "title": "workflow显示名称",
  "category": "分类（Default/空字符串）",
  "description": "描述文本",
  "workflowVersion": "1.0.0",
  "csVersion": "v4.4.1 / v4.7.1 / v5.0.3",
  "createdAt": "ISO时间戳",
  "createdBy": "用户ID",
  "updatedAt": "ISO时间戳（可选）",
  "updatedBy": "用户ID（可选）",
  "jobs": { ... },       // 核心：job定义字典
  "parents": { ... }     // 可选：外部输入占位符
}
```

## 2. jobs 字典结构

每个 job 的 key 为 `J1`, `J2`, ... `Jn`（顺序编号）

```json
"J1": {
  "title": "可选标题",
  "description": "可选描述",
  "jobType": "job类型（必需）",
  "groups": [            // 输入连接（必需，可为空数组）
    ["源job.输出slot", "本job输入名"]
  ],
  "individualResults": [],  // 通常为空
  "parameters": {        // 参数字典（必需）
    "参数名": {
      "value": 实际值,
      "locked": bool,    // 是否锁定（灰显）
      "visible": bool,   // 是否可见
      "flagged": bool,   // 是否标记为关键参数
      "notes": "备注"
    }
  }
}
```

## 3. 真实 jobType 列表（从样本中提取）

### 导入类
- `import_movies` — 导入电影（EER/TIFF）
- `import_micrographs` — 导入显微图（RELION接力时用）
- `import_volumes` — 导入体积图

### 预处理类
- `patch_motion_correction_multi` — Motion Correction（多GPU）
- `patch_ctf_estimation_multi` — CTF估计（多GPU）
- `curate_exposures_v2` — 人工筛选显微图
- `denoise_train` — 降噪训练

### 挑选类
- `blob_picker_gpu` — Blob Picker（自动挑选）
- `template_picker_gpu` — Template Picker（模板匹配）
- `topaz_train` — Topaz深度学习训练
- `topaz_extract` — Topaz深度学习挑选
- `inspect_picks_v2` — 人工检查挑选结果

### 提取类
- `extract_micrographs_multi` — 提取颗粒（多GPU）
- `extract_micrographs_cpu_parallel` — 提取颗粒（CPU并行）

### 分类/重建类
- `class_2D_new` — 2D分类（新版）
- `select_2D` — 2D分类结果筛选
- `homo_abinit` — 同源初始模型
- `hetero_refine` — 异源精修
- `homo_refine_new` — 同源精修（新版）
- `nonuniform_refine_new` — 非均匀精修
- `ctf_refinement` — CTF精修
- `sharpen` — 锐化
- `local_resolution` — 局部分辨率

### 辅助类
- `create_templates` — 从体积图创建模板
- `remove_duplicate_particles` — 去重

## 4. groups 连接规则

格式：`[["源job编号.输出slot名", "目标输入名"]]`

常见连接：
```json
// Motion Correction 接收导入的电影
["J1.imported_movies", "movies"]

// CTF估计 接收 Motion Correction 的显微图
["J2.micrographs", "exposures"]

// Blob Picker 接收筛选后的显微图
["J3.exposures_accepted", "micrographs"]

// Extract 接收显微图和颗粒坐标
["J5.micrographs", "micrographs"],
["J5.particles", "particles"]

// 2D分类 接收提取的颗粒
["J6.particles", "particles"]

// 精修 接收颗粒和体积图
["J8.particles", "particles"],
["J8.volume", "volume"]
```

## 5. 常见参数及其值域

### import_movies / import_micrographs
```json
"blob_paths": {"value": "/path/to/*.tif", "flagged": true},  // 必填
"psize_A": {"value": 0.41, "flagged": true},                 // 必填
"accel_kv": {"value": 300, "locked": true},                  // 通常锁定
"cs_mm": {"value": 2.7, "locked": true},                     // 通常锁定
"total_dose_e_per_A2": {"value": 60, "locked": true}         // 通常锁定
```

### patch_motion_correction_multi
```json
"bfactor": {"value": 150, "locked": true},
"output_fcrop_factor": {"value": "1/2", "locked": true},     // 字符串格式！
"compute_num_gpus": {"value": 4, "locked": true},
"output_f16": {"value": true, "locked": true}                // 半精度输出
```

### blob_picker_gpu
```json
"diameter": {"value": 110, "locked": false},                 // 核心参数
"diameter_max": {"value": 160, "locked": false},             // 核心参数
"max_num_hits": {"value": 300, "locked": false},
"min_distance": {"value": 0.6, "locked": false},
"use_denoised": {"value": true, "locked": true}
```

### extract_micrographs_multi
```json
"compute_num_gpus": {"value": 2, "locked": false},
"box_size_pix": {"value": 320, "locked": false},             // 核心参数
"bin_size_pix": {"value": 120, "locked": false},             // 可选
"output_f16": {"value": true, "locked": true},
"update_location": {"value": true, "locked": false},         // Re-extract时用
"update_alignments2D": {"value": true, "locked": false}
```

### class_2D_new
```json
"class2D_K": {"value": 100, "locked": false},                // 类别数（核心）
"class2D_max_res": {"value": 5, "locked": false},            // 最大分辨率
"class2D_window_inner_A": {"value": 245, "locked": false},   // 窗口大小
"class2D_force_max": {"value": false, "locked": false},
"class2D_num_full_iter_batch": {"value": 40, "locked": false},
"compute_num_gpus": {"value": 2, "locked": false},
"compute_use_ssd": {"value": false, "locked": false}
```

### homo_abinit
```json
"abinit_K": {"value": 3, "locked": false},                   // 初始类别数
"abinit_max_res": {"value": 10, "locked": false}
```

### homo_refine_new
```json
"refine_res_align_max": {"value": 3, "locked": false},       // 对齐分辨率
"compute_use_ssd": {"value": false, "locked": false}
```

## 6. parents 结构（外部输入）

用于需要用户提供初始数据的 workflow（如模板）

```json
"parents": {
  "P1": {
    "jobType": "create_templates",
    "groups": {
      "template": {
        "name": "templates",
        "connections": ["templates"],
        "required": ["blob"]
      }
    }
  }
}
```

在 job 的 groups 中引用：
```json
["P1.templates", "templates"]
```

## 7. 两种常见路线对应的 job 序列

### 路线1：全流程 cryoSPARC（从电影开始）
```
J1: import_movies
  ↓
J2: patch_motion_correction_multi
  ↓
J3: patch_ctf_estimation_multi
  ↓
J4: curate_exposures_v2 (可选)
  ↓
J5: blob_picker_gpu / template_picker_gpu
  ↓
J6: inspect_picks_v2 (可选)
  ↓
J7: extract_micrographs_multi
  ↓
J8: class_2D_new
  ↓
J9: select_2D
  ↓
J10: homo_abinit
  ↓
J11: hetero_refine / homo_refine_new
  ↓
J12: nonuniform_refine_new / ctf_refinement
```

### 路线2：RELION→cryoSPARC 接力（从显微图开始）
```
J1: import_micrographs (RELION Motion Correction输出)
  ↓
J2: patch_ctf_estimation_multi (重新估计CTF，或跳过)
  ↓
J3: curate_exposures_v2
  ↓
J4: template_picker_gpu (需提供模板)
  ↓
后续同路线1（J7开始）
```

## 8. 关键发现总结

1. **flagged 参数** — 标记为关键参数，应在UI中高亮/默认展开
2. **locked 参数** — 通常是固定参数（如电压、Cs），应折叠或灰显
3. **参数值类型多样** — 有数值、字符串（如 "1/2"）、布尔值、路径
4. **groups 数组顺序重要** — 决定输入连接的匹配关系
5. **job编号连续** — J1, J2, ..., Jn 必须连续，不能跳号
6. **必需顶层字段** — `_id`, `title`, `workflowVersion`, `jobs`
7. **csVersion 兼容性** — v4.4+ 到 v5.0 格式一致

## 9. 入门模式 UI 设计建议

### 参数分层策略
```python
# 基于 flagged 和 locked 字段自动分层
if param["flagged"]:
    # 🔥 核心参数 — 默认展开，大号输入框
    render_key_param(name, value, help_text)
elif param["locked"]:
    # 🔒 固定参数 — 折叠，灰色背景
    render_locked_param(name, value)
else:
    # ⚙️ 高级参数 — 可折叠区域
    render_advanced_param(name, value)
```

### 分步填写流程
```
第1步：选择分析路线
  - 全流程 cryoSPARC（从电影开始）
  - RELION→cryoSPARC 接力（从显微图开始）

第2步：采集参数（Import Job）
  🔥 数据路径：/path/to/*.tif
  🔥 像素大小：0.41 Å
  🔒 电压：300 kV（已锁定）
  🔒 Cs：2.7 mm（已锁定）

第3步：Motion Correction（可选跳过）
  ⚙️ B-factor：150（折叠）
  ⚙️ GPU数量：4（折叠）

第4步：颗粒挑选
  🔥 最小直径：110 Å
  🔥 最大直径：160 Å
  ⚙️ 最大挑选数：300（折叠）

...（后续步骤）

最后一步：导出 Workflow JSON
  - 显示预览（可视化DAG图）
  - 下载按钮
  - 一键导入到 cryoSPARC 的说明
```
