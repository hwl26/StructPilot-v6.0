"""Stage workspace component for StructPilot.

Renders the current pipeline stage as a self-contained workspace with
internal tabs: SOP / Parameters / Screenshots / QC.

This component reads from the pipeline checkpoint JSON and adapts to
the active software (cryoSPARC or RELION).

It is designed to be embedded in the left column of the chat tab,
providing persistent stage context that does not scroll away with
chat messages.
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List, Optional
import html as _html_mod

import streamlit as st

from components.qa_card import render_qa_card


def render_stage_workspace(
    checkpoint: Dict[str, Any],
    software: str,
    state: Any,
    app: Any,
    on_switch: Optional[Any] = None,
    key_prefix: str = "ws",
) -> None:
    """Render the current-stage workspace.

    Parameters
    ----------
    checkpoint : dict
        The checkpoint JSON object from pipeline_checkpoints.json.
        Expected keys: checkpoint_id, checkpoint_cn, checkpoint_name,
        phase, order, stage_goal, input_needed, cryosparc, relion,
        qc_check, common_pitfalls, coach_prompt, image_refs.
    software : str
        Active software: 'cryosparc' or 'relion'.
    state : PipelineState
        Current pipeline state (for checkpoint records, notes, etc.).
    app : StructPilotApp
        Application instance (for SOP generation, guide cards, etc.).
    on_switch : callable, optional
        Callback when user clicks prev/next. Receives cp_id string.
    key_prefix : str
        Unique prefix for widget keys.
    """
    if not checkpoint:
        st.info("请从左侧选择一个流程阶段开始。")
        return

    cp_id = checkpoint.get("checkpoint_id", "")
    cp_cn = checkpoint.get("checkpoint_cn", "")
    cp_name = checkpoint.get("checkpoint_name", "")
    phase = checkpoint.get("phase", "")
    order = checkpoint.get("order", 0)
    stage_goal = checkpoint.get("stage_goal", "")
    input_needed = checkpoint.get("input_needed", "")
    approval_gate = checkpoint.get("approval_gate", False)
    coach_prompt = checkpoint.get("coach_prompt", "")

    # Software-specific data
    sw_data = checkpoint.get(software, {}) if isinstance(checkpoint.get(software), dict) else {}
    job_type = sw_data.get("job_type", "")
    key_steps = sw_data.get("key_steps", []) or []
    key_params = sw_data.get("key_params", []) or []
    sw_output = sw_data.get("output", "")
    qc_checks = checkpoint.get("qc_check", []) or []
    pitfalls = checkpoint.get("common_pitfalls", []) or []

    # --- Stage header bar ---
    _render_stage_header(
        order=order,
        cp_cn=cp_cn,
        phase=phase,
        software=software,
        job_type=job_type,
        approval_gate=approval_gate,
        state=state,
        cp_id=cp_id,
        on_switch=on_switch,
        app=app,
        key_prefix=key_prefix,
    )

    # --- Coach prompt (always visible) ---
    if coach_prompt:
        st.info(f"💡 {coach_prompt}")

    # --- Internal tabs ---
    tab_sop, tab_params, tab_screens, tab_qc = st.tabs([
        "📋 SOP",
        "⚙️ 参数",
        "🖼️ 截图",
        "✅ 质控",
    ])

    with tab_sop:
        _render_sop_tab(
            stage_goal=stage_goal,
            input_needed=input_needed,
            sw_output=sw_output,
            key_steps=key_steps,
            pitfalls=pitfalls,
            key_prefix=f"{key_prefix}_sop",
            checkpoint=checkpoint,
            software=software,
        )

    with tab_params:
        _render_params_tab(
            key_params=key_params,
            checkpoint=checkpoint,
            software=software,
            state=state,
            app=app,
            key_prefix=f"{key_prefix}_params",
        )

    with tab_screens:
        _render_screens_tab(
            checkpoint=checkpoint,
            app=app,
            state=state,
            key_prefix=f"{key_prefix}_scr",
        )

    with tab_qc:
        _render_qc_tab(
            qc_checks=qc_checks,
            pitfalls=pitfalls,
            state=state,
            cp_id=cp_id,
            checkpoint=checkpoint,
            key_prefix=f"{key_prefix}_qc",
        )

    # --- B域增强：官方补充说明占位（B阶段文档集成后填充） ---
    _render_official_docs_placeholder(checkpoint=checkpoint, key_prefix=key_prefix)


# ---------------------------------------------------------------------------
# Sub-renderers
# ---------------------------------------------------------------------------

def _render_stage_header(
    order: int,
    cp_cn: str,
    phase: str,
    software: str,
    job_type: str,
    approval_gate: bool,
    state: Any,
    cp_id: str,
    on_switch: Optional[Any],
    app: Any,
    key_prefix: str,
) -> None:
    """Render a compact, centered stage header with navigation.

    Layout:
        [上一步]   ⚪ 步骤 1 · 数据导入   [下一步]
                       作业类型：Import Movies

    Step name is centered and prominent; nav buttons are placed on both sides
    so they are easy to spot and click.
    """
    rec = getattr(state, "checkpoint_records", {}).get(cp_id)
    status = rec.status if rec else "pending"
    status_emoji = {
        "pending": "⚪",
        "in_progress": "🔵",
        "passed": "✅",
        "failed": "❌",
        "skipped": "⏭️",
    }.get(status, "⚪")

    gate_html = '<span class="sp-ws-gate">🔒 需确认</span>' if approval_gate else ""
    title_html = (
        f'<div class="sp-ws-title">'
        f'<span class="sp-ws-status">{status_emoji}</span>'
        f'<span class="sp-ws-step-name">步骤 {order} · {cp_cn}</span>'
        f'{gate_html}'
        f'</div>'
    )

    # Navigation bar: prev | centered title | next
    nav_col1, nav_col2, nav_col3 = st.columns([1, 2.2, 1])
    with nav_col1:
        if st.button("← 上一步", key=f"{key_prefix}_prev", use_container_width=True, type="secondary"):
            if on_switch:
                _navigate(on_switch, state, cp_id, direction=-1, app=app)
    with nav_col2:
        st.markdown(title_html, unsafe_allow_html=True)
    with nav_col3:
        if st.button("下一步 →", key=f"{key_prefix}_next", use_container_width=True, type="primary"):
            if on_switch:
                _navigate(on_switch, state, cp_id, direction=1, app=app)

    if job_type:
        st.caption(f"作业类型：{job_type}")


def _navigate(on_switch: Any, state: Any, current_cp_id: str, direction: int, app: Any = None) -> None:
    """Navigate to the previous or next checkpoint.

    Uses app.navigator.checkpoints from the StructPilotApp instance
    to find the ordered list of checkpoints. Triggers an immediate
    rerun so the UI updates right after the switch.
    """
    checkpoints = []
    if app and hasattr(app, "navigator"):
        checkpoints = sorted(app.navigator.checkpoints, key=lambda x: x.get("order", 999))

    if not checkpoints:
        return
    idx = next((i for i, c in enumerate(checkpoints) if c.get("checkpoint_id") == current_cp_id), -1)
    if idx < 0:
        return
    new_idx = idx + direction
    if 0 <= new_idx < len(checkpoints):
        new_cp_id = checkpoints[new_idx].get("checkpoint_id", "")
        if new_cp_id:
            on_switch(new_cp_id)
            st.rerun()


def _render_sop_tab(
    stage_goal: str,
    input_needed: str,
    sw_output: str,
    key_steps: List[str],
    pitfalls: List[str],
    key_prefix: str,
    checkpoint: Dict[str, Any] = None,
    software: str = "",
) -> None:
    """Render the SOP tab content.

    Enhanced with: workflow overview, step checkboxes, image-text layout.
    """
    if stage_goal:
        st.markdown(f"**🎯 目标**：{stage_goal}")

    col_in, col_out = st.columns(2)
    with col_in:
        if input_needed:
            st.markdown("**📥 输入**")
            st.markdown(input_needed)
    with col_out:
        if sw_output:
            st.markdown("**📤 输出**")
            st.markdown(sw_output)

    st.divider()

    cp_id = checkpoint.get("checkpoint_id", "") if checkpoint else ""

    # --- Workflow 概览：步骤进度条 ---
    if key_steps and len(key_steps) > 1:
        _render_workflow_overview(key_steps, key_prefix, cp_id)
        st.divider()

    # --- 操作步骤区：图文结合 + 可勾选 ---
    if key_steps:
        st.markdown("**📋 操作步骤**")

        lab_params = _load_lab_parameters(cp_id, software)
        step_images = []
        if checkpoint:
            for ref in checkpoint.get("image_refs", []) or []:
                if isinstance(ref, dict):
                    step_images.append(ref)
                elif isinstance(ref, str):
                    step_images.append({"path": ref})

        _render_step_cards(key_steps, step_images, key_prefix, cp_id)

        # 显示关键参数（实验室经验值）
        if lab_params:
            st.divider()
            with st.expander("🔧 关键参数（实验室经验值）", expanded=False):
                st.caption("以下参数来自实验室实际使用数值，供参考调整")
                for param in lab_params[:8]:
                    param_name = _html_mod.escape(param.get("parameter_name", ""))
                    lab_value = _html_mod.escape(param.get("lab_value", ""))
                    lab_note = _html_mod.escape(param.get("lab_note", ""))
                    tuning_guidance = _html_mod.escape(param.get("tuning_guidance", ""))
                    note_html = f'<div style="font-size:0.85rem;color:#475569;margin-bottom:4px;">{lab_note}</div>' if lab_note else ''
                    tuning_html = f'<div style="font-size:0.8rem;color:#475569;font-style:italic;">💡 {tuning_guidance}</div>' if tuning_guidance else ''
                    card_html = (
                        f'<div style="border-left:4px solid #C4612F;background:#FFF8F0;'
                        f'border-radius:8px;padding:12px 16px;margin:8px 0;">'
                        f'<div style="font-size:0.95rem;color:#1F2421;font-weight:600;margin-bottom:4px;">{param_name}</div>'
                        f'<div style="font-size:1.1rem;color:#C4612F;font-weight:700;margin-bottom:6px;">{lab_value}</div>'
                        f'{note_html}{tuning_html}</div>'
                    )
                    st.markdown(card_html, unsafe_allow_html=True)

    if pitfalls:
        with st.expander(f"⚠️ 常见陷阱（{len(pitfalls)} 条）", expanded=False):
            for pitfall in pitfalls:
                st.markdown(f"- {pitfall}")

    _sop_full = st.session_state.get("_workspace_sop_full", "")
    _sop_cp = st.session_state.get("_workspace_sop_cp_id", "")
    current_cp = key_prefix.replace("ws_", "").replace("_sop", "") if key_prefix else ""

    if _sop_full and (_sop_cp == current_cp or not current_cp):
        st.divider()
        with st.expander("📖 完整操作说明（来自助手分析）", expanded=False):
            _body = _sop_full
            if "\n---\n" in _body:
                _body = _body.split("\n---\n", 1)[-1]
            st.markdown(_body)


def _render_workflow_overview(
    key_steps: List[str],
    key_prefix: str,
    cp_id: str,
) -> None:
    """Render a horizontal workflow stepper at the top of SOP tab."""
    total = len(key_steps)
    state_key = f"_sop_steps_done_{key_prefix}_{cp_id}"
    done_set = set(st.session_state.get(state_key, set()))

    st.markdown("**🗺️ 流程概览**")
    st.caption(f"共 {total} 个步骤，已完成 {len(done_set & set(range(total)))} 步")

    step_labels = []
    for i, step in enumerate(key_steps):
        clean = step.strip()
        if len(clean) > 18:
            clean = clean[:16] + "..."
        status = "✅" if i in done_set else ("⏳" if i == 0 else "⬜")
        step_labels.append(f"{status} 步骤 {i+1}")

    # 用 columns 做步骤条
    n_cols = min(total, 6)
    cols = st.columns(n_cols)
    for i in range(min(total, n_cols)):
        with cols[i % n_cols]:
            is_done = i in done_set
            step_text = key_steps[i].strip()
            short_text = step_text[:20] + "..." if len(step_text) > 20 else step_text
            btn_label = f"{'✅' if is_done else '⬜'} 步骤 {i+1}"
            if st.button(btn_label, key=f"{key_prefix}_wf_{i}", help=short_text, use_container_width=True):
                if is_done:
                    done_set.discard(i)
                else:
                    done_set.add(i)
                st.session_state[state_key] = done_set
                st.rerun()

    if total > 6:
        with st.expander(f"查看全部 {total} 个步骤", expanded=False):
            for i in range(6, total):
                is_done = i in done_set
                step_text = key_steps[i].strip()
                col1, col2 = st.columns([1, 20])
                with col1:
                    if st.checkbox("done", value=is_done, key=f"{key_prefix}_wfchk_{i}", label_visibility="collapsed"):
                        done_set.add(i)
                    else:
                        done_set.discard(i)
                    st.session_state[state_key] = done_set
                with col2:
                    st.caption(f"步骤 {i+1}: {step_text}")


def _render_step_cards(
    key_steps: List[str],
    step_images: List[Dict[str, Any]],
    key_prefix: str,
    cp_id: str,
) -> None:
    """Render steps as interactive cards with checkboxes and optional images."""
    total = len(key_steps)
    state_key = f"_sop_steps_done_{key_prefix}_{cp_id}"
    done_set = set(st.session_state.get(state_key, set()))

    done_count = len(done_set & set(range(total)))
    progress = done_count / total if total > 0 else 0
    st.progress(progress, text=f"步骤进度：{done_count}/{total}")

    for i, step in enumerate(key_steps):
        is_done = i in done_set
        step_text = str(step).strip()
        step_clean = _html_mod.escape(step_text)

        card_bg = "#ecfdf5" if is_done else "#ffffff"
        border_color = "#10b981" if is_done else "#e2e8f0"
        border_left_color = "#10b981" if is_done else "#6366f1"
        num_color = "#10b981" if is_done else "#6366f1"

        is_key = any(kw in step_clean for kw in ["关键公式", "【关键】", "重要", "⚠️", "注意"])
        key_badge = ""
        if is_key:
            key_badge = '<span style="background:#fef3c7;color:#92400e;padding:1px 6px;border-radius:3px;font-size:0.7rem;font-weight:600;margin-left:6px;">关键</span>'

        btn_text = "✅" if is_done else "⬜"
        btn_label = "已完成" if is_done else "标记"
        
        card_html = (
            f'<div style="background:{card_bg};border:1px solid {border_color};'
            f'border-left:4px solid {border_left_color};border-radius:8px;'
            f'padding:8px 12px;margin:4px 0;display:flex;align-items:center;gap:8px;">'
            f'<div style="flex-shrink:0;">'
            f'<span style="display:inline-flex;align-items:center;justify-content:center;'
            f'width:22px;height:22px;border-radius:50%;background:{num_color};color:white;'
            f'font-weight:700;font-size:0.75rem;">'
            f'{"✓" if is_done else i+1}</span></div>'
            f'<div style="flex:1;min-width:0;">'
            f'<div style="font-weight:600;color:#1e293b;font-size:0.9rem;display:flex;align-items:center;flex-wrap:wrap;">'
            f'{step_clean}{key_badge}</div></div>'
            f'</div>'
        )

        has_image = step_images and i < len(step_images)
        img_path = ""
        img_caption = ""
        if has_image:
            img = step_images[i]
            img_path = img.get("path", "")
            img_caption = img.get("caption", img.get("image_name", f"图 {i+1}"))

        col_action = st.columns([12, 2]) if has_image else st.columns([14, 2])
        with col_action[0]:
            st.markdown(card_html, unsafe_allow_html=True)
        with col_action[1]:
            if st.button(f"{btn_text}", key=f"{key_prefix}_stepchk_{i}", use_container_width=True, help=btn_label):
                if is_done:
                    done_set.discard(i)
                else:
                    done_set.add(i)
                st.session_state[state_key] = done_set
                st.rerun()
            if has_image and img_path and os.path.exists(img_path):
                with st.popover("📷", use_container_width=True):
                    st.image(img_path, caption=img_caption, use_column_width=True)

    if total > 0:
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔄 重置", key=f"{key_prefix}_reset", use_container_width=True):
                st.session_state[state_key] = set()
                st.rerun()
        with col2:
            if st.button("✅ 全部", key=f"{key_prefix}_all", use_container_width=True):
                st.session_state[state_key] = set(range(total))
                st.rerun()
        with col3:
            if st.button("📤 导出", key=f"{key_prefix}_export", use_container_width=True):
                _export_steps(key_steps, done_set, cp_id)


def _render_key_param_row(param: Dict[str, Any], key_prefix: str = "") -> None:
    """Render a single key parameter as a prominent one-line card.

    Format: [name_cn / name]  →  **value unit**  (note below)
    """
    name = _html_mod.escape(param.get("name_cn") or param.get("name") or "")
    value = _html_mod.escape(str(param.get("value") or "—"))
    unit = _html_mod.escape(param.get("unit", ""))
    note = param.get("note", "")

    value_display = f"{value} {unit}".strip() if value and value != "—" else "—"

    card_html = (
        f'<div style="border-left:3px solid #0f766e;background:#f0fdfa;'
        f'border-radius:6px;padding:10px 14px;margin:5px 0;'
        f'display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;">'
        f'<code style="font-size:0.9rem;color:#0f766e;font-weight:650;min-width:120px;background:transparent;border:none;padding:0;">{name}</code>'
        f'<span style="font-size:1rem;color:#1e293b;font-weight:700;">{value_display}</span>'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)
    if note:
        st.caption(note)


def _render_params_tab(
    key_params: List[str],
    checkpoint: Dict[str, Any],
    software: str,
    state: Any,
    app: Any,
    key_prefix: str,
) -> None:
    """Render the parameters tab.

    Key parameters (first 4) shown prominently with name + value + unit.
    Non-key parameters collapsed into an expander by default.

    增强：结合官方文档、平台实际情况说明；添加实验室经验规定的workflow参数
    """
    cp_id = checkpoint.get("checkpoint_id", "")

    # 读取实验室参数建议
    lab_params = _load_lab_parameters(cp_id, software)

    if not key_params and not lab_params:
        st.caption("本阶段无关键参数。")
        return

    # 1. 参数推荐（结合官方文档+平台实际情况）
    st.markdown("**📌 参数推荐**")

    # 根据当前软件和检查点提供具体推荐
    if software.lower() == "cryosparc":
        st.info("""
        **cryoSPARC 参数设置建议**：

        - **参考官方文档**：cryoSPARC 每个 Job 都有详细的参数说明，点击参数旁边的 "?" 图标查看
        - **结合平台实际**：根据您的电镜平台配置（电压、探测器）和样品特性（大小、对称性）调整
        - **实验室经验**：参考下方"推荐修改参数"中的实验室优化值
        """)
    elif software.lower() == "relion":
        st.info("""
        **RELION 参数设置建议**：

        - **参考官方文档**：RELION 官方教程提供了每个步骤的推荐参数范围
        - **结合平台实际**：根据数据采集参数（pixel size、voltage、Cs）调整
        - **实验室经验**：参考下方"推荐修改参数"中的实验室优化值
        """)
    else:
        st.caption("选择软件后将显示具体的参数推荐。")

    # 2. 双软件灵活切换说明
    with st.expander("📚 双软件支持说明", expanded=False):
        st.markdown("**🔷 RELION** 和 **🔶 cryoSPARC** 均已支持！")
        st.caption("在左侧边栏选择当前使用的软件体系，SOP、参数、质控和官方文档会自动切换到对应软件的内容。")
        st.info("""
        **💡 切换方式**：
        - 在左侧边栏顶部的「软件体系」下拉框中选择 `cryoSPARC` 或 `RELION`
        - 切换后，当前步骤的 SOP、参数推荐、质控标准和官方文档会自动适配
        - 两种软件共享同一套流程框架（12 个检查点），但具体操作和参数各不相同
        """)

    # 3. 推荐修改参数（实验室经验+官方对比）
    if lab_params:
        st.divider()
        with st.expander("🔧 推荐修改参数（实验室经验+官方对比）", expanded=True):
            st.caption(f"已加载 {len(lab_params)} 个实验室常用参数，点击「沉淀为经验」可保存到知识库。")

            for param in lab_params[:10]:
                param_name = _html_mod.escape(param.get("parameter_name", ""))
                lab_value = _html_mod.escape(param.get("lab_value", ""))
                official_value = _html_mod.escape(param.get("official_tutorial_value", ""))
                lab_note = _html_mod.escape(param.get("lab_note", ""))
                tuning_guidance = _html_mod.escape(param.get("tuning_guidance", ""))
                diff_from_official = _html_mod.escape(param.get("diff_from_official", ""))

                official_display = official_value if official_value and official_value != 'N/A' else '—'
                note_html = f'<div style="font-size:0.88rem;color:#475569;margin-bottom:6px;line-height:1.5;">📝 {lab_note}</div>' if lab_note else ''
                diff_html = f'<div style="font-size:0.85rem;color:#A94E22;background:#F2E3D6;padding:6px 10px;border-radius:6px;margin-bottom:6px;">⚠️ 与官方差异：{diff_from_official}</div>' if diff_from_official and diff_from_official != '一致' else ''
                tuning_html = f'<div style="font-size:0.82rem;color:#0f766e;font-style:italic;margin-top:6px;">💡 调整建议：{tuning_guidance}</div>' if tuning_guidance else ''
                card_html = (
                    f'<div style="border:2px solid #C4612F;background:#FFF8F0;'
                    f'border-radius:10px;padding:14px 18px;margin:10px 0;">'
                    f'<div style="font-size:1rem;color:#1F2421;font-weight:700;margin-bottom:8px;">📋 {param_name}</div>'
                    f'<div style="display:flex;gap:20px;margin-bottom:8px;">'
                    f'<div style="flex:1;"><span style="font-size:0.85rem;color:#475569;">实验室值：</span>'
                    f'<span style="font-size:1.05rem;color:#C4612F;font-weight:700;">{lab_value}</span></div>'
                    f'<div style="flex:1;"><span style="font-size:0.85rem;color:#475569;">官方教程值：</span>'
                    f'<span style="font-size:0.95rem;color:#1F2421;font-weight:600;">{official_display}</span></div>'
                    f'</div>{note_html}{diff_html}{tuning_html}</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)

            # 一键沉淀按钮
            st.divider()
            col1, col2 = st.columns([2, 1])
            with col1:
                st.caption("💡 与助手对话后，参数建议和截图会自动沉淀到这里。")
            with col2:
                if st.button("💾 沉淀为经验", key=f"{key_prefix}_save_experience", use_container_width=True):
                    st.success("✅ 已标记为待沉淀，助手会在下次对话时确认并保存到知识库。")
    else:
        # 没有参数时的引导说明
        st.divider()
        with st.expander("💡 参数说明", expanded=False):
            st.markdown("""
            当前步骤暂无预加载的参数推荐。您可以：

            1. **查看下方关键参数**：从软件官方文档提取的核心参数说明
            2. **与助手对话**：询问参数设置建议，助手会根据您的项目情况给出推荐
            3. **上传截图**：上传您的参数设置截图，助手会自动识别并分析
            4. **沉淀经验**：确认好用的参数设置，点击沉淀保存到课题组经验库
            """)

    # 4. 原有的关键参数展示（保留）
    if key_params:
        st.divider()
        params_data = _collect_param_details(key_params, checkpoint, software, state, app)

        if params_data:
            from .parameter_panel import render_parameter_panel

            # Split into key (prominent) and secondary (collapsed) params
            key_items = [p for p in params_data if p.get("_is_key")]
            sec_items = [p for p in params_data if not p.get("_is_key")]

            if key_items:
                st.markdown("**⚙️ 关键参数（软件默认值）**")
                for param in key_items:
                    _render_key_param_row(param, key_prefix)

            if sec_items:
                with st.expander(f"📋 更多参数（{len(sec_items)} 项）", expanded=False):
                    render_parameter_panel(sec_items, key_prefix=f"{key_prefix}_sec")


def _collect_param_details(
    key_params: List[str],
    checkpoint: Dict[str, Any],
    software: str,
    state: Any,
    app: Any,
) -> List[Dict[str, Any]]:
    """Collect parameter details from multiple sources.

    Priority:
      1. User-captured values (state.params)
      2. Guide card parameters (guide_cards.json) — richest source with name_cn/default/unit/lab_experience
      3. Checkpoint fallback — basic name only
    """
    result = []
    cp_id = checkpoint.get("checkpoint_id", "")

    # --- Load guide cards for rich parameter data ---
    _gc_params = {}  # param_id -> dict of rich details
    try:
        import importlib
        main_mod = importlib.import_module("main")
        if hasattr(main_mod, "load_guide_cards"):
            _cards = main_mod.load_guide_cards()
            _card = _cards.get(cp_id, {}) if isinstance(_cards, dict) else {}
            for _substep in (_card.get("substeps") or []):
                for _p in (_substep.get("parameters") or []):
                    if isinstance(_p, dict):
                        _pid = _p.get("id", "") or _p.get("name", "")
                        if _pid:
                            _gc_params[_pid.lower()] = _p
    except Exception:
        pass

    # Check state.params for captured values
    state_params = getattr(state, "params", {}) or {}

    for idx, param_name in enumerate(key_params):
        entry: Dict[str, Any] = {"name": param_name}
        pn_lower = param_name.lower()

        # 1. Check captured user value
        for state_key, state_val in state_params.items():
            if pn_lower in state_key.lower() or state_key.lower() in pn_lower:
                entry["value"] = str(state_val)
                break

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
            # Use default as recommended value if no user-captured value exists
            if not entry.get("value") and gc.get("default"):
                entry["value"] = str(gc["default"])
            if gc.get("unit"):
                entry["unit"] = gc["unit"]
            # Combine meaning + lab_experience + common_mistake into note
            _notes = []
            if gc.get("meaning"):
                _notes.append(gc["meaning"])
            if gc.get("lab_experience"):
                _notes.append(f"💡 {gc['lab_experience']}")
            if gc.get("common_mistake"):
                _notes.append(f"⚠️ {gc['common_mistake']}")
            if _notes:
                entry["note"] = "\n".join(_notes)
        # 3. Basic fallback
        entry.setdefault("value", "")
        entry.setdefault("range", "")
        entry.setdefault("note", "")
        entry.setdefault("unit", "")

        # Mark first 4 params as "key" (prominent display), rest as secondary
        entry["_is_key"] = idx < 4
        result.append(entry)

    return result


def _render_screens_tab(
    checkpoint: Dict[str, Any],
    app: Any,
    state: Any,
    key_prefix: str,
) -> None:
    """Render the screenshots tab with image-text layout support."""
    from .image_gallery import render_image_gallery

    cp_id = checkpoint.get("checkpoint_id", "")
    cp_cn = checkpoint.get("checkpoint_cn", "")

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    images: List[Dict[str, Any]] = []

    for ref in checkpoint.get("image_refs", []) or []:
        if isinstance(ref, dict):
            images.append(ref)
        elif isinstance(ref, str):
            images.append({"path": ref})

    guide_cards_data = {}
    guide_path_fallback = os.path.join(base_dir, "knowledge_base", "guides", "guide_cards.json")
    if os.path.exists(guide_path_fallback):
        try:
            with open(guide_path_fallback, encoding="utf-8") as f:
                raw_data = json.load(f)
                cards = raw_data.get("cards", []) if isinstance(raw_data, dict) else raw_data
                if isinstance(cards, list):
                    guide_cards_data = {}
                    for card in cards:
                        if isinstance(card, dict):
                            cp_id_card = str(card.get("checkpoint_id") or card.get("id") or "").strip()
                            if cp_id_card:
                                guide_cards_data[cp_id_card] = card
        except Exception:
            pass

    card = None
    if isinstance(guide_cards_data, dict) and cp_id in guide_cards_data:
        card = guide_cards_data[cp_id]

    if card:
        for substep in card.get("substeps", []) or []:
            for img in substep.get("images") or []:
                if isinstance(img, dict):
                    img.setdefault("caption", substep.get("title", substep.get("label", "")))
                    img_path = img.get("path", "")
                    if img_path and not img_path.startswith(("http://", "https://", "data:")) and not os.path.isabs(img_path):
                        full_path = os.path.join(base_dir, img_path)
                        if os.path.exists(full_path):
                            img["path"] = full_path
                    images.append(img)

    for img_ref in getattr(state, "pending_images", []) or []:
        if isinstance(img_ref, dict):
            img_ref.setdefault("caption", img_ref.get("image_name", "uploaded"))
            images.append(img_ref)

    # --- 图文排版：即使无图也提供说明 ---
    if images:
        st.markdown("**📸 参考截图**")
        st.caption(f"本阶段共 {len(images)} 张参考截图，可对照实际结果进行质控检查。点击图片可查看大图。")
        render_image_gallery(images, key_prefix=key_prefix)

        # 截图解读说明
        st.divider()
        with st.expander("💡 如何正确使用这些参考截图？", expanded=False):
            st.markdown("""
            **对照检查要点：**

            1. **整体形状**：你的结果图是否与参考图有相似的形状和分布？
            2. **关键特征**：是否出现了参考图中标注的关键特征（如蛋白颗粒、密度分布等）？
            3. **质控指标**：数值型结果（如分辨率、FSC曲线）是否在合理范围内？
            4. **异常排查**：如果你的结果与参考图差异很大，可能是参数设置或数据质量有问题

            **操作建议：**
            - 上传你的结果图到对话区，让助手帮你对比分析
            - 在质控区（QC tab）对照检查清单逐项确认
            - 如有疑问，直接在对话框提问，助手会针对性解答
            """)
    else:
        st.markdown("**📸 截图说明**")
        st.caption("本阶段暂无预加载参考截图。别担心，下方有详细的图文说明帮你理解这个阶段！")

        # 图文说明卡片
        _screens_guide_card(checkpoint, cp_id, cp_cn)

        # 显示该阶段的关键观察点
        sw_data = checkpoint.get("cryosparc", {}) if isinstance(checkpoint.get("cryosparc"), dict) else {}
        if sw_data.get("key_steps"):
            st.divider()
            st.markdown("**🎯 本阶段关键观察点**")
            for i, step in enumerate(sw_data.get("key_steps", [])[:3], 1):
                st.markdown(f"{i}. {step}")


def _screens_guide_card(checkpoint: Dict[str, Any], cp_id: str, cp_cn: str) -> None:
    """Render a comprehensive text+icon guide when no screenshots are available."""
    import json as _json

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # 直接读取 stage_cards 文件，避免循环导入
    cs_doc = None
    rl_doc = None
    try:
        cs_path = os.path.join(base_dir, "knowledge_base", "flows", "cryosparc_stage_cards.json")
        if os.path.exists(cs_path):
            raw = _json.load(open(cs_path, encoding="utf-8"))
            if isinstance(raw, list):
                cs_doc = next((d for d in raw if d.get("id") == cp_id), None)
    except Exception:
        pass
    try:
        rl_path = os.path.join(base_dir, "knowledge_base", "relion_stage_cards.json")
        if os.path.exists(rl_path):
            raw = _json.load(open(rl_path, encoding="utf-8"))
            if isinstance(raw, list):
                rl_doc = next((d for d in raw if d.get("id") == cp_id), None)
    except Exception:
        pass

    # 1. 本阶段结果图类型说明
    with st.expander("🖼️ 本阶段典型结果图类型", expanded=True):
        st.markdown(f"""
        **{cp_cn}** 阶段通常会产生以下类型的结果图：

        | 图类型 | 说明 | 在哪看 |
        |--------|------|--------|
        | **参数设置界面** | 关键参数的配置截图 | 软件 Job Builder |
        | **结果概览** | 处理后的主结果展示 | 软件 Output 区 |
        | **质控图表** | FSC 曲线、分辨率分布等 | QC / Analysis 面板 |
        | **中间结果** | 关键中间步骤的可视化 | 各 Job 的详细输出 |
        """)
        st.caption("💡 上传任何一种截图，助手都能帮你解读和分析。")

    # 2. 软件操作入口指引
    with st.expander("🔧 对应软件操作入口", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🔶 cryoSPARC**")
            if cs_doc and cs_doc.get("cryosparc_jobs"):
                for job in cs_doc["cryosparc_jobs"]:
                    st.markdown(f"- `{job}`")
            else:
                st.caption("请在左侧选择 cryoSPARC 软件体系查看")
        with col2:
            st.markdown("**🔷 RELION**")
            if rl_doc and rl_doc.get("relion_jobs"):
                for job in rl_doc["relion_jobs"]:
                    st.markdown(f"- `{job}`")
            else:
                st.caption("请在左侧选择 RELION 软件体系查看")

    # 3. 上传引导
    with st.expander("📤 上传你的结果图获取解读", expanded=False):
        st.markdown("""
        **上传方式：**
        1. 在右侧对话区点击 📎 按钮
        2. 选择一张或多张结果截图
        3. 发送给助手，等待 AI 分析

        **分析内容包括：**
        - ✅ 图像质量评估
        - 🔍 关键特征识别
        - ⚠️ 潜在问题提示
        - 💡 优化建议和下一步操作

        **支持的图片格式：** PNG, JPG, JPEG, TIFF (截图推荐 PNG)
        """)

    # 4. 快速问题入口
    st.divider()
    st.caption("💡 有具体问题？直接在对话框问，比如：")
    quick_qs = []
    if cs_doc and cs_doc.get("starter_questions"):
        quick_qs = cs_doc["starter_questions"][:3]
    elif rl_doc and rl_doc.get("starter_questions"):
        quick_qs = rl_doc["starter_questions"][:3]
    else:
        quick_qs = [
            f"{cp_cn}后应该看什么结果？",
            f"{cp_cn}常见问题有哪些？",
            f"{cp_cn}参数怎么调？",
        ]
    for q in quick_qs:
        st.code(q, language=None)



def _render_qc_tab(
    qc_checks: List[str],
    pitfalls: List[str],
    state: Any,
    cp_id: str,
    checkpoint: Dict[str, Any],
    key_prefix: str,
) -> None:
    """Render the QC tab.

    Enhanced: pitfalls moved from SOP tab, checklist interactive, lab experience removed.
    """
    if not qc_checks:
        st.caption("本阶段无质控标准。")
    else:
        st.markdown("**✅ 质控检查清单**")

        # 交互性质控清单
        qc_state_key = f"_qc_checks_done_{key_prefix}_{cp_id}"
        qc_done = st.session_state.get(qc_state_key, set())

        last_qc = getattr(state, "last_qc_result", {}) or {}
        qc_passed = last_qc.get("passed")

        for idx, check in enumerate(qc_checks):
            is_checked = idx in qc_done
            col1, col2 = st.columns([1, 20])
            with col1:
                if st.checkbox("done", value=is_checked, key=f"{key_prefix}_qc_{idx}", label_visibility="collapsed"):
                    qc_done.add(idx)
                else:
                    qc_done.discard(idx)
                st.session_state[qc_state_key] = qc_done
            with col2:
                st.markdown(f"{'✅' if is_checked else '☐'} {check}")

        if qc_passed is True:
            render_qa_card({"status": "pass", "message": "当前质控通过"})
        elif qc_passed is False:
            concerns = last_qc.get("concerns", []) or []
            if concerns:
                shown = concerns[:3]
                extra = concerns[3:]
                render_qa_card(
                    {
                        "status": "fail",
                        "message": "质控未通过：" + "；".join(shown),
                        "suggestions": extra,
                    }
                )
            else:
                render_qa_card(
                    {"status": "fail", "message": "质控未通过，请检查参数。"}
                )

        rec = getattr(state, "checkpoint_records", {}).get(cp_id)
        if rec and rec.qc_summary:
            st.caption(f"已记录质控摘要：{rec.qc_summary}")

    st.divider()

    # --- 常见陷阱（从 SOP tab 移到 QC tab，更符合质控定位） ---
    if pitfalls:
        with st.expander(f"⚠️ 常见陷阱 / 避坑指南（{len(pitfalls)} 条）", expanded=True):
            for idx, pitfall in enumerate(pitfalls):
                pitfall_escaped = _html_mod.escape(str(pitfall))
                pitfall_html = (
                    f'<div style="background:#fef2f2;border-left:4px solid #ef4444;'
                    f'border-radius:6px;padding:10px 14px;margin:6px 0;">'
                    f'<div style="color:#991b1b;font-size:0.9rem;">'
                    f'<span style="font-weight:600;">坑点 {idx+1}：</span>{pitfall_escaped}'
                    f'</div></div>'
                )
                st.markdown(pitfall_html, unsafe_allow_html=True)

    st.divider()

    # --- 官方补充说明（RELION + cryoSPARC） ---
    with st.expander("📚 官方补充说明", expanded=False):
        _render_official_docs_in_qc(checkpoint, key_prefix)


def _render_official_docs_in_qc(checkpoint: Dict[str, Any], key_prefix: str) -> None:
    """在质控tab内渲染官方补充说明（RELION + cryoSPARC）"""
    cp_id = checkpoint.get("checkpoint_id", "")

    # 读取 relion_stage_cards.json
    docs_relion = _load_relion_stage_docs()
    docs_cryosparc = _load_cryosparc_stage_docs()

    # 匹配当前 checkpoint
    relion_doc = next((d for d in docs_relion if d.get("id") == cp_id), None)
    cryosparc_doc = next((d for d in docs_cryosparc if d.get("id") == cp_id), None)

    has_content = False

    # 渲染 RELION 官方说明
    if relion_doc and relion_doc.get("source_refs"):
        st.markdown("**🔷 RELION 官方文档（AutoPick与Extract）**")
        for ref in relion_doc.get("source_refs", [])[:3]:
            title = ref.get("title", "")
            url = ref.get("url", "")
            if title and url:
                st.markdown(f"- [{title}]({url})")
        has_content = True
        st.divider()

    # 渲染 cryoSPARC 官方说明
    if cryosparc_doc and cryosparc_doc.get("source_refs"):
        st.markdown("**🔶 cryoSPARC 官方文档**")
        for ref in cryosparc_doc.get("source_refs", [])[:3]:
            title = ref.get("title", "")
            url = ref.get("url", "")
            if title and url:
                st.markdown(f"- [{title}]({url})")
        has_content = True
    else:
        st.markdown("**🔶 cryoSPARC 官方文档**")
        st.caption("从知识库中提取的 cryoSPARC 官方摘要，与助手对话后会自动补充。")
        has_content = True

    if not has_content:
        st.caption("暂无官方文档补充说明。")


# ---------------------------------------------------------------------------
# B-domain enhancement: Lab experience + Official docs sections
# ---------------------------------------------------------------------------

def _load_official_docs() -> List[Dict[str, Any]]:
    """读取 knowledge_index.json 中 B 阶段预抓取的官方文档（带会话缓存）。"""
    cache = st.session_state.get("_official_docs_cache")
    if cache is not None:
        return cache
    docs: List[Dict[str, Any]] = []
    try:
        kb_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "knowledge_base", "knowledge_index.json",
        )
        if os.path.exists(kb_path):
            raw = json.load(open(kb_path, encoding="utf-8"))
            if isinstance(raw, list):
                for d in raw:
                    if isinstance(d, dict) and str(d.get("source", "")).startswith("official_doc"):
                        docs.append(d)
    except Exception:
        docs = []
    st.session_state._official_docs_cache = docs
    return docs


def _load_relion_stage_docs() -> List[Dict[str, Any]]:
    """读取 relion_stage_cards.json"""
    cache = st.session_state.get("_relion_stage_docs_cache")
    if cache is not None:
        return cache
    docs: List[Dict[str, Any]] = []
    try:
        kb_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "knowledge_base", "relion_stage_cards.json",
        )
        if os.path.exists(kb_path):
            raw = json.load(open(kb_path, encoding="utf-8"))
            if isinstance(raw, list):
                docs = raw
    except Exception:
        docs = []
    st.session_state._relion_stage_docs_cache = docs
    return docs


def _load_cryosparc_stage_docs() -> List[Dict[str, Any]]:
    """读取 cryosparc_stage_cards.json"""
    cache = st.session_state.get("_cryosparc_stage_docs_cache")
    if cache is not None:
        return cache
    docs: List[Dict[str, Any]] = []
    try:
        kb_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "knowledge_base", "flows", "cryosparc_stage_cards.json",
        )
        if os.path.exists(kb_path):
            raw = json.load(open(kb_path, encoding="utf-8"))
            if isinstance(raw, list):
                docs = raw
    except Exception:
        docs = []
    st.session_state._cryosparc_stage_docs_cache = docs
    return docs


def _load_lab_parameters(cp_id: str, software: str) -> List[Dict[str, str]]:
    """从 lab_parameters_master.csv 读取当前 checkpoint 的实验室参数建议。

    stage_id 与 cp_id 的映射关系（Excel 阶段编号 vs 流程检查点编号）：
    - 1.x 数据导入/CTF → cp_01（Import）、cp_03（CTF）
    - 2.x 挑颗粒 → cp_04（Blob/Topaz/Template Picker）
    - 3.x 第一轮提取+2D → cp_05（Extract）、cp_06（2D Classification）
    - 4.x 第二轮提取+2D → cp_05（Extract）、cp_06（2D Classification）
    - 5.1 去重 → cp_07（Select 2D）
    - 5.2 初始模型 → cp_08（Ab-initio）
    - 5.3 异质性精修 → cp_09（Heterogeneous Refinement）
    - 5.4 同质性精修 → cp_10（Homogeneous Refinement）
    - 5.5 非均匀精修 → cp_11（Non-uniform Refinement）
    - 0.x / B.x → 无对应 cp（前置操作 / 跨软件桥接）
    """
    cache_key = f"_lab_params_{cp_id}_{software}"
    cache = st.session_state.get(cache_key)
    if cache is not None:
        return cache

    params: List[Dict[str, str]] = []
    try:
        # 定位 CSV 文件路径：knowledge_base/cryosparc_docs/lab_parameters_master.csv
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        csv_path = os.path.join(base_dir, "knowledge_base", "cryosparc_docs", "lab_parameters_master.csv")

        if not os.path.exists(csv_path):
            return params

        # cp_id → 匹配的 stage_id 前缀列表
        _cp_to_stage_prefixes = {
            "cp_01": ["1.1"],           # Import Movies
            "cp_02": [],                 # 运动校正 Excel 中未单列
            "cp_03": ["1.2", "1.3"],     # Patch CTF / Curate Exposures
            "cp_04": ["2.1", "2.2", "2.3", "2.4", "2.5"],  # Blob/Topaz/Template 挑颗粒
            "cp_05": ["3.1", "4.1"],     # 第一/二轮 Extract
            "cp_06": ["3.2", "4.2"],     # 第一/二轮 2D Classification
            "cp_07": ["5.1"],            # 去重 / Select 2D 相关
            "cp_08": ["5.2"],            # Ab-initio 初始模型
            "cp_09": ["5.3"],            # 异质性精修
            "cp_10": ["5.4"],            # 同质性精修
            "cp_11": ["5.5"],            # 非均匀精修
            "cp_12": [],                 # 模型验证
        }
        target_prefixes = _cp_to_stage_prefixes.get(cp_id, [])

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                stage_id = row.get("stage_id", "")

                # 按 stage_id 前缀匹配
                matched = False
                for prefix in target_prefixes:
                    if stage_id and stage_id.startswith(prefix):
                        matched = True
                        break
                if not matched:
                    continue

                params.append({
                    "parameter_name": row.get("parameter_name", ""),
                    "lab_value": row.get("lab_value", ""),
                    "lab_note": row.get("lab_note", ""),
                    "tuning_guidance": row.get("tuning_guidance", ""),
                    "official_tutorial_value": row.get("official_tutorial_value", ""),
                    "diff_from_official": row.get("diff_from_official", ""),
                    "stage_name": row.get("stage_name", ""),
                    "stage_id": stage_id,
                })
    except Exception as e:
        params = []

    st.session_state[cache_key] = params
    return params


def _render_official_docs_placeholder(checkpoint: Dict[str, Any], key_prefix: str = "ws") -> None:
    """B 阶段官方文档集成：展示当前步骤对应的预抓取官方文档（含原文链接）。

    文档来源为 RELION 5.0 SPA Tutorial 与 cryoSPARC User Management 的精编摘要，
    已在 knowledge_index.json 中（source 以 official_doc 开头）。匹配规则：
    文档的 checkpoint_id == 当前步，或当前步 cp_id 出现在文档 tags 中。
    点击标题下的「查看官方原文」跳转官方页面（合法引用，非全文复制）。
    """
    cp_id = checkpoint.get("checkpoint_id", "")
    cp_cn = checkpoint.get("checkpoint_cn", "") or cp_id
    sw = (checkpoint.get("relion") and "relion") or (checkpoint.get("cryosparc") and "cryosparc") or ""

    docs = _load_official_docs()
    matched: List[Dict[str, Any]] = []
    for d in docs:
        doc_cp = d.get("checkpoint_id", "")
        doc_tags = d.get("tags", []) or []
        if doc_cp == cp_id or cp_id in doc_tags:
            # 若当前软件已知，优先同软件文档；跨软件步骤两者都展示
            if sw and d.get("software") and d.get("software") != sw:
                continue
            matched.append(d)
    # 无同软件匹配时，放宽到展示该步骤所有官方文档（跨软件通用步骤）
    if not matched and cp_id:
        for d in docs:
            if d.get("checkpoint_id") == cp_id or cp_id in (d.get("tags", []) or []):
                matched.append(d)

    with st.expander("📚 官方补充说明", expanded=False):
        if not matched:
            st.caption(f"「{cp_cn}」暂无对应官方文档。")
            return
        for idx, doc in enumerate(matched):
            title = doc.get("title_cn", "") or doc.get("doc_id", "")
            url = doc.get("source_url", "")
            summary = doc.get("summary", "") or ""
            st.markdown(f"**📖 {title}**")
            if url:
                st.markdown(f"[查看官方原文 ↗]({url})")
            if summary:
                snippet = summary if len(summary) <= 110 else summary[:110] + "…"
                st.caption(snippet)
            if idx < len(matched) - 1:
                st.divider()


def _export_steps(key_steps: List[str], done_set: set, cp_id: str) -> None:
    """Export step checklist as markdown text for download."""
    total = len(key_steps)
    done_count = len(done_set & set(range(total)))
    lines = [
        f"# {cp_id or 'SOP'} 操作步骤清单",
        f"",
        f"**进度**: {done_count}/{total} 步骤已完成",
        f"",
        "---",
        "",
    ]
    for i, step in enumerate(key_steps):
        status = "✅" if i in done_set else "⬜"
        lines.append(f"{status} 步骤 {i+1}: {step.strip()}")
    lines.append("")
    lines.append("---")
    lines.append(f"*由 StructPilot 自动导出*")

    md_content = "\n".join(lines)
    st.download_button(
        label="📥 下载 Markdown 清单",
        data=md_content,
        file_name=f"{cp_id or 'sop'}_checklist.md",
        mime="text/markdown",
        key=f"{cp_id}_download_steps",
    )
