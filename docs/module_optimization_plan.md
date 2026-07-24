# StructPilot 模块优化实施方案

根据用户需求和优化建议，本文档详细说明需要实现的功能改进。

---

## 🎯 模块一：课题组知识库共享平台优化

### 1. 对话检索来源标注系统

#### 当前状态
- ✅ 已有共享知识库（待审核/已验证状态）
- ✅ 已有对话检索功能
- ❌ 回答中没有明确区分「基础原理」和「实验室经验」
- ❌ 缺少来源标注（人员、时间、审核状态）

#### 优化目标
AI 回答应该分为三个层次：
1. **基础原理**（来自官方文档/通用知识）
2. **课题组经验**（来自知识库，标注来源）
3. **相关讨论**（来自历史对话记录）

#### 实施方案

**步骤1：增强检索结果结构**

修改 `knowledge/retriever.py`，检索结果增加来源元数据：

```python
# 检索结果格式
{
    "content": "Motion Correction 的 B-factor 建议 150-300",
    "source_type": "lab_experience",  # 或 "official_doc" / "chat_history"
    "metadata": {
        "author": "张三",
        "author_role": "博士生",
        "date": "2026-07-20",
        "status": "approved",  # 或 "pending"
        "category": "参数调优经验",
        "step": "cp_02",
    }
}
```

**步骤2：重构 LLM 回答格式**

修改 Prompt，要求 LLM 结构化输出：

```
你是 StructPilot，冷冻电镜数据处理助手。

回答格式要求：
1. 首先回答基础原理（基于官方文档）
2. 然后补充课题组经验（如果有）
3. 最后提及相关讨论（如果有）

示例：
【基础原理】
Motion Correction 的 B-factor 参数控制...（通用说明）

【🥇 课题组经验】
根据张三（博士生）2026-07-20 的记录（✅ 已验证）：
"TRPV1 蛋白用 B-factor=300 效果更好，漂移明显减少"

【💬 相关讨论】
李四在 2026-07-15 也遇到类似问题...
```

**步骤3：UI 展示优化**

在回答区域使用不同颜色/图标区分：

```python
# components/answer_display.py
def render_structured_answer(answer_data: dict):
    # 基础原理（蓝色背景）
    if answer_data.get("basic_principle"):
        with st.container(border=True):
            st.markdown("#### 📚 基础原理")
            st.markdown(answer_data["basic_principle"])
    
    # 课题组经验（金色背景）
    if answer_data.get("lab_experiences"):
        with st.container(border=True):
            st.markdown("#### 🥇 课题组实战经验")
            for exp in answer_data["lab_experiences"]:
                status_badge = "✅ 已验证" if exp["status"] == "approved" else "⚠️ 待审核"
                st.markdown(f"**{status_badge}** | {exp['author']}（{exp['author_role']}）· {exp['date']}")
                st.markdown(exp["content"])
                st.caption(f"分类：{exp['category']} | 步骤：{exp['step']}")
    
    # 相关讨论（灰色背景）
    if answer_data.get("related_discussions"):
        with st.expander("💬 历史讨论记录", expanded=False):
            for disc in answer_data["related_discussions"]:
                st.markdown(f"**{disc['user']}** · {disc['date']}")
                st.markdown(disc["content"])
```

---

### 2. 聊天记录标记为经验

#### 需求
用户与 AI 的对话中，如果某条回答特别有价值，可以一键标记为经验并提交审核。

#### 实施方案

**UI 设计**：

每条 AI 回答下方增加操作按钮：

```python
# main.py 聊天区域
for msg in st.session_state.chat_history:
    if msg["role"] == "assistant":
        st.markdown(msg["content"])
        
        # 操作按钮（仅成员及以上可见）
        if has_permission(current_user, "contribute"):
            col_mark, col_useful, col_report = st.columns([1, 1, 1])
            with col_mark:
                if st.button("🏷️ 标记为经验", key=f"mark_{msg['id']}"):
                    st.session_state.mark_exp_dialog = msg["id"]
                    st.rerun()
            with col_useful:
                if st.button("👍 有用", key=f"useful_{msg['id']}"):
                    # 记录反馈
                    pass
            with col_report:
                if st.button("⚠️ 报错", key=f"report_{msg['id']}"):
                    # 报告错误
                    pass

# 标记对话框
if st.session_state.get("mark_exp_dialog"):
    msg_id = st.session_state.mark_exp_dialog
    msg = find_message_by_id(msg_id)
    
    with st.form("mark_as_experience"):
        st.markdown("### 将对话标记为经验")
        st.info(f"**原始回答**：\n{msg['content'][:200]}...")
        
        title = st.text_input("经验标题", placeholder="简短描述")
        category = st.selectbox("分类", ["参数调优", "报错解决", "非常规流程"])
        step = st.selectbox("关联步骤", ["cp_01", "cp_02", ...])
        note = st.text_area("补充说明（可选）")
        
        if st.form_submit_button("提交审核"):
            save_experience_from_chat(msg, title, category, step, note, current_user)
            st.success("✅ 已提交，等待管理员审核")
            st.session_state.mark_exp_dialog = None
            st.rerun()
```

---

## 🎯 模块二：cryoSPARC 工作流参数交互系统优化

### 3. 高阶模式：官方文档链接集成

#### 当前状态
- ✅ 高级模式有参数说明
- ❌ 缺少官方文档链接

#### 优化目标
每个参数旁边显示「📖 查看官方说明」链接，点击跳转到 CryoSPARC 官方文档对应章节。

#### 实施方案

**步骤1：构建参数→文档映射表**

创建 `knowledge_base/cryosparc_doc_links.json`：

```json
{
  "import_movies": {
    "psize_A": {
      "doc_url": "https://guide.cryosparc.com/processing-data/import-and-preprocessing/import-movies#pixel-size",
      "summary": "像素大小（Å/pixel），决定真实空间分辨率"
    },
    "accel_kv": {
      "doc_url": "https://guide.cryosparc.com/processing-data/import-and-preprocessing/import-movies#acceleration-voltage",
      "summary": "加速电压（kV），影响 CTF 拟合"
    }
  },
  "patch_motion_correction_multi": {
    "bfactor": {
      "doc_url": "https://guide.cryosparc.com/processing-data/import-and-preprocessing/motion-correction#b-factor",
      "summary": "B-factor 控制运动校正的平滑程度，典型值 150-500"
    }
  },
  ...
}
```

**步骤2：UI 展示**

在参数输入框旁边增加文档链接：

```python
# 高级模式参数渲染
for param in tab["parameters"]:
    col_param, col_doc = st.columns([3, 1])
    
    with col_param:
        # 原有参数输入框
        st.text_input(param["name"], value=param["value"])
    
    with col_doc:
        # 官方文档链接
        doc_link = get_doc_link(job_type, param["name"])
        if doc_link:
            st.markdown(f"[📖 官方说明]({doc_link['url']})")
            st.caption(doc_link["summary"])
```

---

### 4. QC 回溯分析增强

#### 当前状态
- ✅ 有质检卡片（QA Card）
- ❌ 无法粘贴 CryoSPARC 运行结果
- ❌ 无法给出下一步建议

#### 优化目标
用户可以粘贴 CryoSPARC Job 的输出日志/统计数据，StructPilot 自动分析并给出：
1. QC 判断（通过/警告/失败）
2. 问题诊断（如果失败）
3. 下一步建议（调整参数 / 重新运行 / 跳过该步骤）
4. 引用课题组相关经验

#### 实施方案

**步骤1：创建 QC 回溯面板**

在高级模式增加「📊 QC 回溯分析」tab：

```python
# main.py - 高级模式
with tab_qc_analysis:
    st.markdown("### 📊 质检回溯分析")
    st.caption("粘贴 CryoSPARC Job 的输出结果，获取 QC 判断和下一步建议")
    
    # 选择步骤
    step = st.selectbox("选择步骤", ["Motion Correction", "CTF Estimation", "2D Classification", ...])
    
    # 输入区域
    result_input_method = st.radio("输入方式", ["粘贴文本", "上传截图", "上传 JSON"])
    
    if result_input_method == "粘贴文本":
        user_paste = st.text_area(
            "粘贴 CryoSPARC 输出",
            height=200,
            placeholder=(
                "示例：\n"
                "Total micrographs: 5000\n"
                "Micrographs accepted: 4523\n"
                "Micrographs rejected: 477\n"
                "Mean motion (Å): 15.2\n"
                "Mean CTF fit: 4.5 Å\n"
                "..."
            )
        )
    elif result_input_method == "上传截图":
        uploaded_img = st.file_uploader("上传截图", type=["png", "jpg"])
    else:
        uploaded_json = st.file_uploader("上传 JSON", type=["json"])
    
    if st.button("🔍 开始分析", type="primary"):
        with st.spinner("正在分析..."):
            # 调用 LLM 分析
            qc_result = analyze_cryosparc_output(step, user_paste)
            
            # 显示结果
            render_qc_analysis_result(qc_result)
```

**步骤2：QC 分析逻辑**

```python
# utils/qc_analyzer.py
def analyze_cryosparc_output(step: str, output_text: str) -> dict:
    """
    分析 CryoSPARC 输出并给出 QC 判断。
    
    Returns
    -------
    {
        "status": "pass" / "warning" / "fail",
        "score": 85,
        "issues": ["Mean motion 偏大", "部分 micrograph 被拒绝"],
        "diagnosis": "运动校正结果基本可接受，但漂移偏大...",
        "next_steps": [
            {
                "action": "调整参数重新运行",
                "params": {"bfactor": 300},
                "reason": "增大 B-factor 可减少漂移"
            },
            {
                "action": "继续下一步",
                "confidence": 0.7,
                "risk": "可能影响后续 CTF 拟合精度"
            }
        ],
        "lab_experiences": [
            {
                "author": "张三",
                "date": "2026-07-15",
                "status": "approved",
                "content": "遇到类似情况，增大 B-factor 到 300 解决"
            }
        ]
    }
    """
    # 1. 解析输出文本，提取关键指标
    metrics = parse_cryosparc_metrics(step, output_text)
    
    # 2. 根据阈值判断 QC 状态
    qc_status, issues = evaluate_qc_thresholds(step, metrics)
    
    # 3. 检索课题组相关经验
    lab_exps = search_lab_experiences(step, issues)
    
    # 4. 调用 LLM 生成诊断和建议
    prompt = f"""
    你是 StructPilot QC 分析专家。
    
    步骤：{step}
    输出结果：
    {output_text}
    
    检测到的问题：
    {issues}
    
    课题组经验：
    {lab_exps}
    
    请给出：
    1. 问题诊断
    2. 下一步建议（调整参数 / 重新运行 / 继续 / 跳过）
    3. 引用课题组经验（如果相关）
    """
    
    llm_response = app.llm.generate(prompt)
    
    return {
        "status": qc_status,
        "issues": issues,
        "diagnosis": llm_response.get("diagnosis"),
        "next_steps": llm_response.get("next_steps"),
        "lab_experiences": lab_exps,
    }
```

**步骤3：QC 结果展示**

```python
def render_qc_analysis_result(result: dict):
    # 状态徽章
    if result["status"] == "pass":
        st.success("✅ QC 通过")
    elif result["status"] == "warning":
        st.warning("⚠️ QC 警告：存在潜在问题")
    else:
        st.error("❌ QC 失败：需要重新运行")
    
    # 问题列表
    if result["issues"]:
        with st.expander("⚠️ 检测到的问题", expanded=True):
            for issue in result["issues"]:
                st.markdown(f"- {issue}")
    
    # 诊断
    with st.container(border=True):
        st.markdown("#### 🔍 问题诊断")
        st.markdown(result["diagnosis"])
    
    # 下一步建议
    st.markdown("#### 💡 下一步建议")
    for idx, step in enumerate(result["next_steps"]):
        with st.container(border=True):
            st.markdown(f"**方案{idx+1}：{step['action']}**")
            st.markdown(step.get("reason", ""))
            if step.get("params"):
                st.json(step["params"])
            if step.get("confidence"):
                st.progress(step["confidence"], f"置信度：{step['confidence']*100:.0f}%")
    
    # 课题组经验
    if result["lab_experiences"]:
        with st.container(border=True):
            st.markdown("#### 🥇 课题组类似经验")
            for exp in result["lab_experiences"]:
                status_badge = "✅" if exp["status"] == "approved" else "⚠️"
                st.markdown(f"{status_badge} **{exp['author']}** · {exp['date']}")
                st.markdown(exp["content"])
```

---

## 🎯 模块三：用户体验优化

### 5. 入门模式自动参数计算

#### 当前状态
- ✅ 已有问答收集关键参数
- ⚠️ 部分参数（box size, mask）需要手动填写

#### 优化目标
根据「蛋白直径」自动计算：
- Box size（建议值 = 直径 × 1.5，向上取到 2 的幂次）
- Mask radius（建议值 = 直径 × 0.5）
- Extract box size（根据像素大小和直径）

#### 实施方案

```python
# components/onboarding_v3.py
def calculate_recommended_params(particle_diameter: float, pixel_size: float) -> dict:
    """
    根据颗粒直径和像素大小自动计算推荐参数。
    
    Parameters
    ----------
    particle_diameter : float
        颗粒直径（Å）
    pixel_size : float
        像素大小（Å/pixel）
    
    Returns
    -------
    dict
        {
            "box_size": 256,
            "box_size_reason": "直径 150Å × 1.5 = 225Å，225/0.96 ≈ 234 像素，向上取 2^8 = 256",
            "mask_radius": 75,
            "mask_radius_reason": "直径的一半",
            "particle_diameter_px": 156,
        }
    """
    import math
    
    # 计算盒子大小
    min_box_A = particle_diameter * 1.5  # 至少 1.5 倍直径
    min_box_px = min_box_A / pixel_size
    # 向上取到最近的 2 的幂次
    box_size = 2 ** math.ceil(math.log2(min_box_px))
    
    # 计算 mask radius
    mask_radius = particle_diameter / 2
    
    # 颗粒直径（像素）
    particle_diameter_px = particle_diameter / pixel_size
    
    return {
        "box_size": int(box_size),
        "box_size_reason": f"直径 {particle_diameter}Å × 1.5 = {min_box_A:.0f}Å，{min_box_A:.0f}/{pixel_size} ≈ {min_box_px:.0f} 像素，向上取 2^{int(math.log2(box_size))} = {box_size}",
        "mask_radius": int(mask_radius),
        "mask_radius_reason": f"直径的一半：{particle_diameter}/2 = {mask_radius:.0f}Å",
        "particle_diameter_px": int(particle_diameter_px),
    }

# 在问答完成后展示
st.markdown("### ✨ 根据你的输入，我们自动计算了以下参数：")
auto_params = calculate_recommended_params(particle_diameter, pixel_size)
st.json(auto_params)
st.caption("这些参数已自动填充到 workflow，你可以在高级模式中手动调整")
```

---

### 6. 经验去重检测

#### 需求
提交经验时，自动检测是否已有类似条目，避免重复。

#### 实施方案

```python
# utils/experience_dedup.py
def detect_duplicate_experience(title: str, symptoms: str, solution: str) -> list[dict]:
    """
    检测是否有重复经验。
    
    Returns
    -------
    list[dict]
        相似的已有经验列表，按相似度排序
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    
    # 加载已有经验
    existing_exps = load_all_experiences()
    
    # 构建查询文本
    query = f"{title} {symptoms} {solution}"
    
    # TF-IDF 向量化
    corpus = [f"{exp['title']} {exp.get('symptoms_text', '')} {exp['solution']}" 
              for exp in existing_exps]
    corpus.append(query)
    
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(corpus)
    
    # 计算相似度
    similarities = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1])[0]
    
    # 筛选相似度 > 0.6 的条目
    duplicates = []
    for idx, sim in enumerate(similarities):
        if sim > 0.6:
            duplicates.append({
                **existing_exps[idx],
                "similarity": sim,
            })
    
    return sorted(duplicates, key=lambda x: x["similarity"], reverse=True)

# UI 展示
if st.button("提交经验"):
    duplicates = detect_duplicate_experience(title, symptoms, solution)
    
    if duplicates:
        st.warning(f"⚠️ 检测到 {len(duplicates)} 条相似经验，请确认是否重复：")
        for dup in duplicates[:3]:
            with st.expander(f"相似度 {dup['similarity']*100:.0f}% - {dup['title']}"):
                st.markdown(f"**作者**：{dup['author']}")
                st.markdown(f"**解决方案**：{dup['solution']}")
        
        confirm = st.checkbox("确认不重复，仍然提交")
        if not confirm:
            st.stop()
    
    # 提交
    save_experience(...)
```

---

## 📅 实施优先级

| 优先级 | 功能 | 预计工作量 | 用户价值 |
|--------|------|-----------|---------|
| **P0** | 对话检索来源标注 | 2天 | 高（核心差异化） |
| **P0** | QC 回溯分析 | 3天 | 高（实际需求强） |
| **P1** | 聊天记录标记为经验 | 1天 | 中（提升贡献便利性） |
| **P1** | 官方文档链接集成 | 0.5天 | 中（提升学习效率） |
| **P2** | 自动参数计算 | 0.5天 | 中（降低使用门槛） |
| **P2** | 经验去重检测 | 1天 | 低（优化体验） |

---

## 🚀 下一步行动

要我立即开始实施哪个功能？建议顺序：
1. **对话检索来源标注**（最核心的差异化功能）
2. **QC 回溯分析**（用户最需要的实际功能）
3. 其他功能按需实施

需要我现在开始吗？
