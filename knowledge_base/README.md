# StructPilot v2.0 Knowledge Base Schema

未来新增知识建议按以下结构组织：

## 推荐格式

### 1. 流程节点知识
用于描述每个检查站（checkpoint）的标准操作、参数和质控标准。
建议存放为 `pipeline_checkpoints.json`，每条记录包含：
- `checkpoint_id`
- `checkpoint_cn`
- `phase`
- `order`
- `stage_goal`
- `input_needed`
- `cryosparc`
- `relion`
- `qc_check`
- `common_pitfalls`
- `coach_prompt`
- `approval_gate`

### 2. 故障知识
用于故障诊断、回溯与建议。
建议存放为 `fault_trouble.json`，每条记录包含：
- `fault_keyword`
- `phenomenon`
- `possible_reason`（数组）
- `solve_suggest`
- `rollback_node`（数组）

### 3. 决策规则
用于参数阈值建议、选择策略、是否继续推进等。
建议存放为 `tier2_rules.json`，每条记录包含：
- `rule_name`
- `condition`
- `approval_level`
- `decision_tree`（数组）
- `reference`

### 4. 模板
用于教练话术、报告、提示语。
建议存放为 `coach_templates.json`。

## 以后更细致的知识，怎么输入

建议不要把知识写成一大段自然语言，而是尽量拆成“结构化片段”，这样更容易检索、复用、分发给不同 Agent。

### 推荐的数据颗粒度

#### A. 一个条目只解决一个问题
例如：
- “CTF fit 低于 4.5A 怎么办”
- “box size 如何估算”
- “2D class 模糊的原因有哪些”

不要把多个问题混在一个条目里。

#### B. 每条知识都要有可检索字段
建议至少包含：
- `id`
- `title`
- `keywords`
- `stage_id`
- `software`（cryosparc / relion / both）
- `symptom`
- `cause`
- `checkpoints`
- `solution`
- `rollback`
- `severity`
- `confidence`
- `reference`

#### C. 输出要分层
建议把知识分成 3 层：
1. **层 1：流程卡片** — 当前站要做什么
2. **层 2：规则卡片** — 参数阈值、判断标准
3. **层 3：故障卡片** — 具体问题、原因、回溯点

这样 Navigator 负责“走流程”，Expert 负责“解释知识”，SOP 负责“步骤化”，Memory 负责“记录上下文”。

## 推荐的单条知识 JSON 模板

```json
{
  "id": "ctf_fit_low",
  "title": "CTF fit 过低",
  "stage_id": "cp_03",
  "software": "both",
  "keywords": ["ctf", "fit", "低", "6A", "4.5A"],
  "symptom": "大部分 micrograph 的 CTF fit 分辨率差于 4.5A",
  "cause": ["defocus range 不合理", "图像质量差", "pixel size 配置错误"],
  "solution": ["检查输入参数", "剔除差图", "重新估计 CTF"],
  "rollback": ["cp_02", "cp_01"],
  "severity": "high",
  "confidence": 0.86,
  "reference": "StructPilot v2 migration note"
}
```

## 最佳实践

- 优先使用数组字段存放多条原因/建议
- 关键字字段尽量短而稳定
- 每条知识尽量绑定一个阶段 `stage_id`
- 允许一个知识条目同时属于多个软件，但要明确 `software`
- 后续如果知识很多，建议再拆成：
  - `flows/*.json`
  - `faults/*.json`
  - `rules/*.json`
  - `sops/*.json`

这样后面很容易升级为向量检索 + 规则检索的混合系统。
