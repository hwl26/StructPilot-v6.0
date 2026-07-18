# StructPilot v3.0 增强执行计划

> 基于 v2_plus 代码库现状 + WorkBuddy 两份方案文档（v5→v6 Integration Plan + Agent Architecture Enhanced）
> 制定日期：2026-07-07 | 版本：v1.0

---

## 一、核心判断

| 维度 | 结论 |
|------|------|
| 当前架构 vs 方案目标 | v2_plus（Streamlit + LangGraph）**已超越**方案描述的 HTML v5/v6 系统 |
| 方案价值所在 | **知识内容**（KB 数据结构），而非架构方案 |
| 方案 Phase 6（Chat Sidebar） | **不需要**——当前全屏 Chat UI 更优 |
| 核心瓶颈 | 知识库内容稀疏：12 站仅 1 站完整、故障库仅 1 条、规则库仅 1 条 |
| 最优策略 | **吸收方案的知识内容，灌入当前架构，零破环** |

---

## 二、五个增强模块总览

```
┌─────────────────────────────────────────────────────────────────┐
│  A. 官方知识整合      补全 cp_02–cp_12 的所有空字段              │
│  B. 图表解读引擎      新增 9 种图表解读规则 + PlotAgent           │
│  C. 上下文推荐引擎    新增用户上下文采集 + 6 参数推荐规则          │
│  D. 决策引导问卷      在 cp_04 增加 Picker 选择决策树             │
│  E. 智能排障引擎      用 5 场景结构化 KB 替换单条 fault            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、实施阶段

### Phase 0：基础数据补全（优先级最高，1 天）

> 目标：把实验室已有的 knowledge_base/cryosparc_docs/ 中的知识内容，结构化填入 pipeline_checkpoints.json。

#### Step 0.1：补全 pipeline_checkpoints.json

**当前状态**：cp_01 完整，cp_02–cp_12 仅骨架（key_steps: [], qc_check: [], common_pitfalls: [], coach_prompt: ""）

**改动文件**：`knowledge_base/flows/pipeline_checkpoints.json`（和根目录同名副本同步更新）

**数据来源**：`knowledge_base/cryosparc_docs/lab_workflow_full.md`（已有 23KB 实验室 SOP）

**每个检查站需补充的字段**：

| 字段 | 说明 | 示例（cp_06 2D 分类） |
|------|------|----------------------|
| `key_steps` | 操作步骤 | `["选择上游 Extract job 的输出颗粒", "设置 Number of classes: 100", ...]` |
| `key_params` | 关键参数列表 | `["num_classes", "max_resolution", "force_max_over_poses", "batchsize_per_class", "online_em_iterations"]` |
| `qc_check` | QC 检查项 | `["类别平均图应可见清晰二级结构", "ESS 直方图中多数类应接近 1", ...]` |
| `common_pitfalls` | 常见坑 | `["条纹类过多→关闭 Force max", "垃圾类过多→增大 ICUF", ...]` |
| `coach_prompt` | 开场引导语 | `"现在来做 2D 分类。目的是把好颗粒和坏颗粒/污染分开..."` |

#### Step 0.2：扩展参数结构

**改动文件**：`graph/state.py` — `PipelineState` 增加字段：

```python
# 新增字段
user_context: Dict[str, Any] = field(default_factory=dict)
# user_context 结构示例:
# {
#     "microscope": "Titan Krios",
#     "voltage_kv": 300,
#     "detector": "K3",
#     "pixel_size_A": 0.96,
#     "sample_type": "globular_protein",
#     "estimated_mass_kda": 400,
#     "estimated_particles": 300000,
#     "has_reference": False,
# }
```

**改动文件**：`knowledge_base/flows/pipeline_checkpoints.json` — 每个参数从简单字符串升级为结构化对象：

```jsonc
// 当前 v2（cp_01 示例）
"key_params": ["pixel_size", "accelerating_voltage"]

// v3 升级：增加参数详情子表
"params_detail": [
    {
        "name_en": "Pixel size (Å/px)",
        "name_cn": "像素尺寸",
        "type": "number",
        "unit": "Å/px",
        "default_value": null,
        "official_desc": "",
        "official_url": "",
        "version_changes": "",
        "lab_value": "根据数据采集参数设定（如 K3 super-resolution 模式物理像素 / 2）",
        "mistake": "像素尺寸填错会导致后续 CTF 估计和重构全部偏差",
        "recommendation_rule": null  // Phase C 填入
    }
]
```

---

### Phase A：官方知识整合（1 天）

> 目标：爬取 CryoSPARC 官方 Guide，结构化存入 JSON KB，让每个参数卡片展示四层信息。

#### Step A.1：爬取脚本

**新建文件**：`scripts/crawl_guide.py`

**爬取目标**：13 个核心 Job 页面 + 2 个教程页面

```python
CRAWL_URLS = {
    "import_movies": "https://guide.cryosparc.com/.../job-import-movies",
    "patch_motion": "https://guide.cryosparc.com/.../job-patch-motion-correction",
    "patch_ctf": "https://guide.cryosparc.com/.../job-patch-ctf-estimation",
    "blob_picker": "https://guide.cryosparc.com/.../job-blob-picker",
    "template_picker": "https://guide.cryosparc.com/.../job-template-picker",
    "topaz_picker": "https://guide.cryosparc.com/.../job-topaz-train-extract-pick",
    "extract": "https://guide.cryosparc.com/.../job-extract-from-micrographs",
    "2d_classification": "https://guide.cryosparc.com/.../job-2d-classification",
    "select_2d": "https://guide.cryosparc.com/.../job-select-2d-classes",
    "ab_initio": "https://guide.cryosparc.com/.../job-ab-initio-reconstruction",
    "heterogeneous": "https://guide.cryosparc.com/.../job-heterogeneous-refinement",
    "homogeneous": "https://guide.cryosparc.com/.../job-homogeneous-refinement",
    "non_uniform": "https://guide.cryosparc.com/.../job-non-uniform-refinement-new",
    "common_plots": "https://guide.cryosparc.com/.../tutorial-common-cryosparc-plots",
    "orientation_diag": "https://guide.cryosparc.com/.../tutorial-orientation-diagnostics",
}
```

**输出文件**：`knowledge_base/sources/official_guide_kb.json`

**数据结构**：每个 Job 包含 `source_url`, `last_crawled`, `content_hash`, `version_tag`, `description`, `inputs`, `outputs`, `parameters[]`, `warnings[]`, `version_changes{}`

#### Step A.2：NavigatorAgent 引用官方知识

**改动文件**：`agents/navigator_agent.py`

- 在 `__init__` 中加载 `official_guide_kb.json`
- 在 `get_stage_guide()` 中，当检查站有对应官方知识时，追加：

```python
# 伪代码
guide_kb = self.official_guide.get(cp_id)
if guide_kb:
    lines.append("\n### 📘 官方文档")
    lines.append(guide_kb["description"])
    lines.append(f"\n[查看 CryoSPARC Guide 原文 ↗]({guide_kb['source_url']})")
```

#### Step A.3：Settings Tab 增加刷新按钮

**改动文件**：`main.py`（Settings Tab 区域）

- 增加 "🔄 刷新官方知识" 按钮
- 点击后调用 `crawl_guide.py` 或直接 `import scripts.crawl_guide`
- 完成后显示更新摘要（"3 个 Job 有更新"）
- 更新后的内容标记 `version_tag`

---

### Phase B：图表解读引擎（2 天）

> 目标：用户做完 2D/3D 后，系统能解读 FSC、取向、ESS 等图表，给出三级诊断。

#### Step B.1：图表解读 KB

**新建文件**：`knowledge_base/plots/plot_interp_kb.json`

**覆盖图表**（9 类）：

| 图表类型 | 出现步骤 | 规则数 | 严重级别 |
|---------|---------|--------|---------|
| `fsc_curve` | cp_08, cp_09, cp_10 | 5 条 | 🟢/⚠️/❌ |
| `orientation_distribution` | cp_07, cp_08, cp_09 | 2 条 | 🟢/❌ |
| `class_ess` | cp_06 | 2 条 | 🟢/⚠️ |
| `class_average` | cp_06 | 2 条 | 🟢/❌ |
| `ncc_power` | cp_04 | 2 条 | 🟢/⚠️ |
| `guinier` | cp_09 | 2 条 | 🟢/⚠️ |
| `noise_model` | cp_06, cp_07 | 2 条 | 🟢/⚠️ |
| `best_class_prob` | cp_06 | 1 条 | 🟢 |
| `posterior_precision` | cp_08, cp_09 | 1 条 | 🟢/⚠️ |

**数据结构**：

```json
{
  "fsc_curve": {
    "name": "Fourier Shell Correlation (FSC)",
    "name_cn": "FSC 曲线",
    "appears_in": ["cp_08", "cp_09", "cp_10"],
    "rules": [
      {
        "pattern": "fsc_crosses_0.143",
        "severity": "good",
        "icon": "🟢",
        "meaning_cn": "分辨率达标，金标准验证通过",
        "action_cn": "继续下一步精修",
        "source": "CryoSPARC Guide: Common Plots",
        "source_url": "https://guide.cryosparc.com/..."
      }
    ]
  }
}
```

#### Step B.2：新增 PlotAgent

**新建文件**：`agents/plot_agent.py`

```python
class PlotAgent:
    """图表解读智能体：根据图表类型 + 当前步骤 → 匹配规则 KB → 输出诊断"""
    
    def __init__(self, kb_path: str):
        self.plot_kb = self._load_kb(kb_path)
    
    def interpret(self, plot_type: str, current_cp_id: str) -> str:
        """返回 Markdown 格式的诊断报告"""
        kb = self.plot_kb.get(plot_type)
        if not kb:
            return "未找到该图表类型的解读规则。"
        
        # 筛选当前步骤适用的规则
        # 按 severity 排序（problem > warning > info > good）
        # 格式化为 Markdown
```

#### Step B.3：LangGraph 增加 plot_interp 节点

**改动文件**：`graph/app.py`

```python
# 新增节点
graph.add_node("plot_interp", self._plot_interp_node)

# 新增路由
if tag == "plot_interpretation":
    return "plot_interp"

# 节点实现
def _plot_interp_node(self, state: PipelineState) -> PipelineState:
    # 从 user_input 中解析图表类型
    plot_type = self._parse_plot_type(state.user_input or "")
    reply = self.plot_agent.interpret(plot_type, state.current_cp_id)
    state.agent_reply = self._polish_reply(state, reply)
    self._record_assistant(state, state.agent_reply, "plot_interpretation")
    return state
```

#### Step B.4：NavigatorAgent 增加图表关键词路由

**改动文件**：`agents/navigator_agent.py`

```python
# 在 handle_input() 中，expert_triggers 之前添加：
plot_triggers = [
    "解读", "怎么看", "分析", "FSC", "fsc", "取向", "orientation",
    "ESS", "ess", "guinier", "Guinier", "类别平均", "class average",
    "NCC", "噪声模型", "noise model", "posterior", "帮我看看",
]
if any(k in state.user_input_lower for k in plot_triggers):
    return "", "plot_interpretation"
```

#### Step B.5：UI 集成

**改动文件**：`main.py`

- 在 `render_guide_card()` 中，针对 cp_06/cp_07/cp_08/cp_09/cp_10，增加"📊 解读结果"快捷按钮
- 点击后自动发送对应关键词（如"帮我解读 FSC 曲线"）

---

### Phase C：上下文感知参数推荐（1.5 天）

> 目标：用户配置实验条件后，参数卡片显示个性化推荐值。

#### Step C.1：用户上下文采集 UI

**改动文件**：`main.py`（Settings Tab）

在 Settings Tab 中新增 "🧪 实验条件" section：

```python
with st.expander("🧪 实验条件配置", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        microscope = st.selectbox("显微镜型号", 
            ["Titan Krios (300kV)", "Arctica (200kV)", "Glacios (200kV)", "其他"])
        detector = st.selectbox("探测器",
            ["K3 (super-resolution)", "Falcon 4i", "K2", "其他"])
        pixel_size = st.number_input("像素尺寸 (Å/px)", value=0.96, step=0.01)
    with col2:
        sample_type = st.selectbox("样品类型",
            ["球状蛋白", "膜蛋白", "复合体", "纤维/棒状", "其他"])
        estimated_mass = st.number_input("估计分子量 (kDa)", value=400, step=10)
        estimated_particles = st.number_input("估计颗粒数", value=300000, step=10000)
    
    if st.button("💾 保存实验条件"):
        st.session_state.user_context = {...}
        state.user_context = {...}
```

#### Step C.2：推荐规则 KB

**新建文件**：`knowledge_base/rules/recommendation_rules.json`

支持 6 个参数的上下文推荐：

| 参数 | 依赖上下文 | 推荐公式 |
|------|-----------|---------|
| `box_size` | estimated_mass_kda, pixel_size_A | `直径 ≈ 2×(mass×1.21×3/4π)^(1/3)` → `box ≈ 直径/pixel×1.8` → round to efficient sizes |
| `num_2d_classes` | estimated_particles | `>200k → 100; 50k-200k → 50; <50k → 20-30` |
| `max_resolution` | round_number | `round1 → 5Å; round2 → 3Å` |
| `voltage_kv` | microscope | Titan Krios → 300; Arctica/Glacios → 200 |
| `pixel_size_A` | detector | K3 SR → 物理像素/2; Falcon → 物理像素 |
| `spherical_aberration` | microscope | Titan Krios → 2.7mm; 200kV → 2.0mm |

#### Step C.3：推荐计算引擎

**新建文件**：`agents/recommend_agent.py`

```python
class RecommendAgent:
    def recommend(self, param_name: str, user_context: Dict, round_number: int = 1) -> Optional[Dict]:
        """返回 {value, reason, formula} 或 None（无推荐时）"""
```

#### Step C.4：NavigatorAgent 注入推荐值

**改动文件**：`agents/navigator_agent.py`

在 `get_stage_guide()` 中：
```python
if state.user_context:
    for param in cp.get("key_params", []):
        rec = self.recommend_agent.recommend(param, state.user_context)
        if rec:
            lines.append(f"- 💡 **推荐: {rec['value']}** (基于你的 {rec['reason']})")
```

---

### Phase D：决策引导问卷（0.5 天）

> 目标：在 cp_04（颗粒挑选）提供交互式 Picker 选择引导，而非简单罗列三种 Picker。

#### Step D.1：决策规则数据

**改动文件**：`knowledge_base/flows/pipeline_checkpoints.json`（cp_04）

```json
{
  "checkpoint_id": "cp_04",
  "decision_tree": {
    "title": "选择颗粒挑选方法",
    "questions": [
      {
        "id": "q_sample_type",
        "text": "你的样品类型是什么？",
        "options": [
          {"value": "globular", "label": "球状蛋白", "recommend": "blob_circular"},
          {"value": "rod_filament", "label": "棒状/纤维状", "recommend": "blob_elliptical_stretch"},
          {"value": "disk_membrane", "label": "盘状/膜蛋白", "recommend": "blob_elliptical_squeeze"},
          {"value": "hollow", "label": "空心结构", "recommend": "blob_ring"}
        ]
      },
      {
        "id": "q_has_reference",
        "text": "你是否已有模板或初始模型？",
        "options": [
          {"value": "yes", "label": "有 → 推荐 Template Picker", "recommend": "template"},
          {"value": "no", "label": "没有 → 先 Blob 后 Template", "recommend": "blob_first"}
        ]
      },
      {
        "id": "q_contrast",
        "text": "你的数据对比度如何？",
        "options": [
          {"value": "good", "label": "对比度好 → Blob 够用", "recommend": "blob_only"},
          {"value": "poor", "label": "对比度差 → Blob + Topaz", "recommend": "blob_then_topaz"},
          {"value": "overlapping", "label": "大量重叠 → Topaz + Inspect", "recommend": "topaz_inspect"}
        ]
      }
    ],
    "recommendations": {
      "blob_circular": {
        "picker": "Blob Picker (circular)",
        "reason": "球状蛋白适合圆形 blob 模式",
        "path_preview": "Blob → Inspect → Extract → 2D → Select → Template → ...",
        "source": "CryoSPARC Guide: Blob Picker"
      },
      "template": {
        "picker": "Template Picker",
        "reason": "已有模板直接用 Template Picker，互相关更精准",
        "path_preview": "Template → Extract → 2D → Select → ...",
        "source": "CryoSPARC Guide: Template Picker"
      }
    }
  }
}
```

#### Step D.2：NavigatorAgent 渲染决策树

**改动文件**：`agents/navigator_agent.py`

在 `get_stage_guide()` 中：
```python
decision_tree = cp.get("decision_tree")
if decision_tree:
    lines.append("\n### 🔀 选择引导")
    lines.append(decision_tree["title"])
    lines.append("请回答以下问题，系统将推荐最适合的 Picker：")
    # 渲染为 Streamlit 交互式 radio 组件的 Markdown 提示
    # 实际交互由 main.py 的 render_guide_card() 处理
```

---

### Phase E：智能排障引擎（1 天）

> 目标：用 5 个结构化排障场景替换当前 1 条 fault 规则，支持交互式逐步诊断。

#### Step E.1：排障 KB 重构

**改动文件**：`knowledge_base/faults/fault_trouble.json`（替换当前单条）

5 个排障场景：

| 场景 ID | 步骤 | 症状 | 问题数 | 方案数 |
|---------|------|------|--------|--------|
| `2d_stripe_noise` | cp_06 | 2D 分类出现条纹类/纯噪声 | 3 | 4 |
| `fsc_oscillation` | cp_09 | FSC 曲线出现振荡 | 2 | 2 |
| `preferred_orientation` | cp_09 | 取向分布严重偏侧 | 1 | 3 |
| `too_many_junk` | cp_06 | 垃圾类过多 | 1 | 2 |
| `ctf_bad_fit` | cp_03 | CTF 拟合质量差 | 2 | 2 |

**数据结构**（以 `2d_stripe_noise` 为例）：

```json
{
  "fault_id": "2d_stripe_noise",
  "step": "cp_06",
  "title_cn": "2D 分类出现条纹类/纯噪声",
  "symptom_cn": "类别平均值呈条纹状或纯噪声，无清晰蛋白质特征",
  "severity": "problem",
  "questions": [
    {"id": "q_small_particle", "text_cn": "蛋白分子量是否 < 100 kDa？", "impact_cn": "小粒子低 SNR 是条纹类主因"},
    {"id": "q_force_max", "text_cn": "Force max over poses/shifts 是否开启？", "impact_cn": "开启会强制对齐导致条纹"},
    {"id": "q_iterations", "text_cn": "online-EM 迭代数是否 < 20？", "impact_cn": "迭代不足未充分收敛"}
  ],
  "solutions": [
    {
      "priority": 1,
      "action_cn": "关闭 Force max over poses/shifts",
      "reason_cn": "边缘化姿态改善低信噪比粒子对齐",
      "trade_off_cn": "计算时间增加 5-6 倍",
      "source": "CryoSPARC Guide: 2D Classification - Force max"
    }
  ]
}
```

#### Step E.2：增强 NavigatorAgent.diagnose()

**改动文件**：`agents/navigator_agent.py`

当前 `diagnose()` 只做简单关键词匹配 + 输出一段文本。增强后：

```python
def diagnose(self, state: PipelineState, user_text: str) -> str:
    # 1. 关键词匹配 → 找到最佳候选故障
    candidates = self._score_fault_candidates(user_text)
    if not candidates:
        return self._generic_diagnosis(state, user_text)
    
    best = candidates[0]
    
    # 2. 如果用户回答过诊断问题，跳过已答的问题
    asked = state.fault_diagnosis_state.get("asked_questions", [])
    pending = [q for q in best["questions"] if q["id"] not in asked]
    
    # 3. 还有未问的问题 → 继续提问
    if pending:
        return self._format_diagnosis_question(pending[0])
    
    # 4. 所有问题已回答 → 输出方案
    return self._format_solutions(best["solutions"])
```

#### Step E.3：PipelineState 增加排障状态

**改动文件**：`graph/state.py`

```python
# 新增字段
fault_diagnosis_state: Dict[str, Any] = field(default_factory=dict)
# 结构: {"active_fault_id": "2d_stripe_noise", "asked_questions": ["q_small_particle"], "answers": {"q_small_particle": "yes"}}
```

---

## 四、文件变更汇总

### 新建文件

| 文件 | Phase | 说明 |
|------|-------|------|
| `scripts/crawl_guide.py` | A | 官方 Guide 爬取脚本 |
| `knowledge_base/sources/official_guide_kb.json` | A | 爬取产物（静态数据） |
| `knowledge_base/plots/plot_interp_kb.json` | B | 9 种图表解读规则 |
| `agents/plot_agent.py` | B | 图表解读智能体 |
| `agents/recommend_agent.py` | C | 参数推荐引擎 |
| `knowledge_base/rules/recommendation_rules.json` | C | 6 参数推荐规则 |
| `docs/V3_ENHANCEMENT_PLAN.md` | — | 本文档 |

### 修改文件

| 文件 | Phase | 变更摘要 |
|------|-------|---------|
| `knowledge_base/flows/pipeline_checkpoints.json` | 0+A+D | 补全 cp_02–cp_12 + 增加 params_detail + cp_04 decision_tree |
| `graph/state.py` | 0+E | 增加 user_context, fault_diagnosis_state |
| `graph/app.py` | B | 增加 plot_interp 节点 + 路由 |
| `agents/navigator_agent.py` | A+B+C+D+E | 加载新 KB + 图表路由 + 推荐注入 + 决策树 + 增强 diagnose |
| `main.py` | A+B+C | Settings Tab 增加刷新按钮 + 实验条件面板；Chat Tab 增加快捷按钮 |

### 不变更文件

| 文件 | 原因 |
|------|------|
| `agents/llm_agent.py` | 当前已完整支持多 provider |
| `agents/memory_agent.py` | 当前已完整支持 SQLite |
| `agents/expert_agent.py` | 保留为备份，暂不接入 |
| `agents/sop_agent.py` | 保留为备份，暂不接入 |
| `knowledge_base/retriever.py` | 当前 RAG 已完整，新增 KB 文件会被自动索引 |
| `validator/validator.py` | 当前验证逻辑足够 |

---

## 五、时间估算

| Phase | 内容 | 时间 | 累计 |
|-------|------|------|------|
| Phase 0 | 基础数据补全（12 站 + 参数结构） | 1 天 | 1 天 |
| Phase A | 官方知识整合（爬取 + 引用） | 1 天 | 2 天 |
| Phase B | 图表解读引擎（KB + Agent + 路由） | 2 天 | 4 天 |
| Phase C | 上下文推荐（采集 UI + 规则 + 引擎） | 1.5 天 | 5.5 天 |
| Phase D | 决策引导（cp_04 决策树） | 0.5 天 | 6 天 |
| Phase E | 排障引擎（KB 重构 + 交互式诊断） | 1 天 | 7 天 |
| 集成测试 | 全链路验证 | 1 天 | **8 天** |

**可以并行**：Phase A 和 Phase B 可同时推进（A 是数据工程，B 是功能开发，互不阻塞）。

---

## 六、风险与注意事项

| 风险 | 缓解措施 |
|------|---------|
| 爬取被官方屏蔽 | 手动触发而非自动定时；控制请求间隔（≥3 秒）；遵守 robots.txt |
| 图表解读准确率 | 规则基于官方 Tutorial，每条带 source 可追溯；非 AI 自由发挥 |
| 推荐值不当 | 推荐值旁显示计算原因和公式，用户可覆盖；默认值作为 fallback |
| LLM 幻觉 | 推荐和排障走规则引擎（可审查）；Chat 自由问答有免责声明 |
| 知识库版本不一致 | `pipeline_checkpoints.json` 有两个副本（`flows/` 和根目录），需同步更新 |

---

## 七、验收标准

### Phase 0+1
- [ ] 12 个检查站全部有 key_steps / qc_check / common_pitfalls / coach_prompt
- [ ] 每个关键参数有结构化 params_detail
- [ ] 用户在任意检查站说"怎么做"能获得完整指导

### Phase A
- [ ] 13 个 Job 官方说明已爬取并存为 JSON
- [ ] NavigatorAgent 能在 stage_guide 中引用官方描述
- [ ] Settings Tab 有"刷新官方知识"按钮，点击后可更新

### Phase B
- [ ] 9 种图表有解读规则
- [ ] 用户说"帮我解读 FSC"能获得三级诊断（🟢/⚠️/❌）
- [ ] 每条诊断有官方来源链接

### Phase C
- [ ] Settings Tab 有实验条件配置面板
- [ ] 配置后参数卡片显示 💡 推荐值
- [ ] 推荐值附带计算原因

### Phase D
- [ ] cp_04 进入时展示决策引导问题
- [ ] 回答问题后得到 Picker 推荐 + 路径预览

### Phase E
- [ ] 5 个排障场景有结构化 KB
- [ ] 用户报错后，诊断引擎逐步提问
- [ ] 解决方案有优先级排序 + trade-off 提示
