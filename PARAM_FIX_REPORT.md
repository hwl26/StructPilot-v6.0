# 参数显示修复报告

**修复时间**：2026-07-14  
**问题**：参数 Tab 显示 `**—**` 而非实际参数值  
**优先级**：高（影响用户体验）

---

## 🔍 问题根因

### 数据不一致
`pipeline_checkpoints.json` 和 `guide_cards.json` 使用不同的参数命名：

| pipeline_checkpoints.json | guide_cards.json | 匹配结果 |
|--------------------------|------------------|---------|
| `accelerating_voltage` | `voltage` | ❌ 不匹配 |
| `acceleration_voltage` | `voltage` | ❌ 不匹配 |
| `pixel_size` | `pixel_size` | ✅ 匹配 |
| `bfactor` | `b_factor` | ❌ 不匹配 |
| `spherical_aberration` | `spherical_aberration` | ✅ 匹配 |

### 代码逻辑
`stage_workspace.py` 中的 `_collect_param_details` 函数只进行**精确匹配**：
```python
gc = _gc_params.get(pn_lower)  # 只查找小写的参数 ID
```

如果找不到匹配，就返回空值 `""`，最终渲染为 `**—**`。

---

## ✅ 修复方案（方案 1）

### 1. 为 guide_cards.json 添加别名

使用 Python 脚本批量添加 `aliases` 字段：

**脚本**：`add_aliases.py`

**别名映射表**：
```python
ALIASES = {
    "pixel_size": ["apix", "angpix", "pixel_spacing"],
    "voltage": ["accelerating_voltage", "acceleration_voltage", "kv"],
    "spherical_aberration": ["cs", "cs_value"],
    "dose_per_frame": ["total_dose", "dose"],
    "b_factor": ["bfactor", "b_factor_motioncorr"],
    "box_size": ["boxsize"],
    "defocus_range_min": ["defocus_range", "min_defocus"],
    "defocus_range_max": ["max_defocus"],
    "num_classes": ["number_of_classes", "n_classes"],
    "num_iterations": ["number_of_iterations", "n_iterations"],
    "circular_mask_diameter": ["mask_diameter", "particle_diameter"],
    "min_separation": ["min_separation_dist"],
    "max_diameter": ["max_particle_diameter"],
    "min_diameter": ["min_particle_diameter"],
    "fourier_crop": ["fourier_crop_box_size"],
    "use_gpu": ["num_gpus"],
}
```

**执行结果**：
```
[SUCCESS] Modified 16 parameters
[SUCCESS] Saved to: knowledge_base/guides/guide_cards.json
```

**示例（修改后的 guide_cards.json）**：
```json
{
  "id": "voltage",
  "name": "Accelerating Voltage (kV)",
  "name_cn": "加速电压",
  "type": "number",
  "default": "300",
  "unit": "kV",
  "aliases": ["accelerating_voltage", "acceleration_voltage", "kv"],
  "meaning": "电子显微镜的加速电压",
  ...
}
```

### 2. 修改参数匹配逻辑

修改 `stage_workspace.py` 的 `_collect_param_details` 函数，增加别名查找：

**修改位置**：第 552-558 行

**原代码**：
```python
# 2. Enrich from guide card parameters
gc = _gc_params.get(pn_lower)
if gc:
    entry["name_cn"] = gc.get("name_cn") or gc.get("name", param_name)
    ...
```

**修改后**：
```python
# 2. Enrich from guide card parameters
# Try exact match first
gc = _gc_params.get(pn_lower)
# If not found, search through aliases
if not gc:
    for _pid, _param in _gc_params.items():
        _aliases = _param.get("aliases", [])
        if pn_lower in [a.lower() for a in _aliases]:
            gc = _param
            break

if gc:
    entry["name_cn"] = gc.get("name_cn") or gc.get("name", param_name)
    ...
```

**逻辑说明**：
1. 先尝试精确匹配 `_gc_params.get(pn_lower)`
2. 如果失败，遍历所有参数的 `aliases` 列表
3. 如果 `pn_lower` 在某个参数的别名中，使用该参数的数据

---

## 🧪 测试验证

### 测试步骤
1. 访问 http://localhost:8501
2. 在侧边栏选择 **cp_01 数据导入**
3. 切换到 **参数** Tab
4. 检查关键参数是否显示具体值（不再是 `**—**`）

### 预期结果
- `pixel_size` → **0.96** Å/px
- `accelerating_voltage` → **300** kV
- `spherical_aberration` → **2.7** mm
- `total_dose` → **50** e⁻/Å²

### 实际效果
（等待用户反馈）

---

## 📦 修改文件清单

| 文件路径 | 修改类型 | 说明 |
|---------|---------|-----|
| `knowledge_base/guides/guide_cards.json` | ✏️ 数据修改 | 为 16 个参数添加 `aliases` 字段 |
| `ui/components/stage_workspace.py` | 🔧 代码优化 | 修改参数匹配逻辑，支持别名查找 |
| `add_aliases.py` | 🆕 新增脚本 | 批量添加别名的工具脚本 |
| `knowledge_base/guides/guide_cards.json.backup` | 📦 备份 | 原始文件备份 |

---

## 🚀 部署建议

### 立即生效
修改已生效，重启 Streamlit 服务后即可看到效果：
```bash
cd /path/to/StructPilot_v5.1
python -m streamlit run main.py --server.port 8501
```

### 后续维护
1. **新增参数时**：在 `guide_cards.json` 中同时定义 `aliases` 字段
2. **统一命名**：长期建议统一两个 JSON 文件的参数命名规范
3. **文档更新**：在开发文档中说明参数命名约定

---

## 💡 其他方案对比

### 方案 2：修改 pipeline_checkpoints.json
- **优点**：一次性修改，代码无需改动
- **缺点**：需要手动修改 12 个检查点的参数名，容易遗漏

### 方案 3：代码中硬编码映射表
- **优点**：不改数据文件
- **缺点**：维护成本高，每次新增参数都要改代码

**选择方案 1 的原因**：
- 数据驱动，灵活扩展
- 修改局部（只改有别名的参数）
- 代码改动最小（只增加 6 行）

---

## ✅ 修复确认

- [x] `guide_cards.json` 添加别名完成
- [x] `stage_workspace.py` 修改完成
- [x] 服务重启成功
- [ ] **等待用户验收**：参数是否正常显示

---

**修复人**：Claude (Kiro CLI)  
**状态**：等待用户验收  
**下一步**：确认参数显示正常后，更新验收检查单
