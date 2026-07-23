"""StructPilot v6.0 — 需求问答（Onboarding）组件 - 重设计版。

分步展示 + 卡片化布局 + 进度可视化，提升首次使用体验。
"""

from __future__ import annotations

from typing import Any, Dict

import streamlit as st


def _init_onboarding_state() -> None:
    """初始化问答状态。"""
    if "onboarding_completed" not in st.session_state:
        st.session_state.onboarding_completed = False
    if "onboarding_step" not in st.session_state:
        st.session_state.onboarding_step = 0  # 当前步骤（0=欢迎页，1-5=问题页，6=确认页）
    if "user_profile" not in st.session_state:
        st.session_state.user_profile = {}
    if "recommended_workflow" not in st.session_state:
        st.session_state.recommended_workflow = []


def _generate_workflow_recommendation(profile: Dict[str, Any]) -> Dict[str, Any]:
    """根据用户画像生成工作流推荐。"""
    goal = profile.get("goal", "")
    sample_type = profile.get("sample_type", "")
    microscope = profile.get("microscope", "")
    resolution_target = profile.get("resolution_target", "")

    # 基础步骤
    base_steps = ["cp_01", "cp_02", "cp_03"]

    # 根据目标扩展步骤
    if goal == "质检":
        steps = base_steps
        skip_steps = ["cp_04", "cp_05", "cp_06", "cp_07", "cp_08", "cp_09", "cp_10", "cp_11"]
        reason = "目标是初步质检，只需完成到 CTF Estimation，确认数据质量即可。"
    elif goal == "2D分类":
        steps = base_steps + ["cp_04", "cp_05", "cp_06"]
        skip_steps = ["cp_07", "cp_08", "cp_09", "cp_10", "cp_11"]
        reason = "目标是 2D 分类筛选，完成颗粒提取和分类后即可停止。"
    elif goal == "3D重构":
        steps = [f"cp_{i:02d}" for i in range(1, 12)]
        skip_steps = []
        reason = "目标是完整 3D 重构，需走完全部流程。"
    else:
        steps = base_steps + ["cp_04", "cp_05", "cp_06"]
        skip_steps = ["cp_07", "cp_08", "cp_09", "cp_10", "cp_11"]
        reason = "默认推荐到 2D 分类，可根据结果决定是否继续。"

    # 参数预填充
    params = {}

    # 根据电镜类型设置
    if "Krios" in microscope and "300" in microscope:
        params["voltage"] = 300
        params["pixel_size"] = 0.86
    elif "Arctica" in microscope or "200" in microscope:
        params["voltage"] = 200
        params["pixel_size"] = 1.0
    else:
        params["voltage"] = 300
        params["pixel_size"] = 0.86

    # 根据样品类型设置粒子直径和 mask 直径
    # ⚠️ 注意：以下为起始参考值，需根据 2D 分类结果迭代调整
    # 蛋白质形状差异（球形 vs 拉长）导致分子量无法直接对应固定直径
    # mask_diameter = particle_diameter + 2×solvent_shell(~10Å) + 摆动余量(~10Å)
    if "小型" in sample_type:
        params["particle_diameter"] = 80  # 起始参考：<150 kDa 小型复合物
        params["mask_diameter"] = 100
    elif "中等" in sample_type:
        params["particle_diameter"] = 150  # 起始参考：150-500 kDa 中等复合物
        params["mask_diameter"] = 180
    elif "大型" in sample_type:
        params["particle_diameter"] = 250  # 起始参考：>500 kDa 大型复合物
        params["mask_diameter"] = 300
    elif "病毒" in sample_type or "高对称" in sample_type:
        params["particle_diameter"] = 300  # 病毒尺寸范围大（20-200 nm），需单独评估
        params["mask_diameter"] = 360
        params["symmetry"] = "C1"  # 提示用户后续根据实际对称性调整（I, I2, I3...）
    else:
        # 通用/不确定：使用中等尺度默认值
        params["particle_diameter"] = 150
        params["mask_diameter"] = 180

    # 根据分辨率目标设置
    if "粗筛" in resolution_target:
        params["max_resolution_ctf"] = 6
        params["num_classes_2d"] = 30
    elif "中等" in resolution_target:
        params["max_resolution_ctf"] = 5
        params["num_classes_2d"] = 50
    elif "高分辨" in resolution_target:
        params["max_resolution_ctf"] = 4
        params["num_classes_2d"] = 100
    else:
        params["max_resolution_ctf"] = 5
        params["num_classes_2d"] = 50

    return {
        "steps": steps,
        "skip_steps": skip_steps,
        "params": params,
        "reason": reason,
    }


def render_onboarding_dialog() -> bool:
    """渲染需求问答对话框（分步版）。

    Returns
    -------
    bool
        用户是否完成问答（点击"确认并开始"）
    """
    _init_onboarding_state()

    if st.session_state.onboarding_completed:
        return True

    step = st.session_state.onboarding_step

    # ========== 欢迎页（step=0）==========
    if step == 0:
        st.markdown("# 🎯 欢迎使用 StructPilot")
        st.markdown(
            "**cryo-EM 数据处理智能陪跑系统**  \n"
            "让我们先了解你的需求，为你定制专属流程路线。"
        )
        st.markdown("---")

        # 价值说明卡片（科学雅观风格：灰蓝色系，低饱和度）
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                '<div style="padding:1.2rem;background:#f8fafc;border-radius:10px;border-left:4px solid #64748b;box-shadow:0 1px 3px rgba(0,0,0,0.05);">'
                '<div style="font-size:2rem;margin-bottom:0.5rem;">⚡</div>'
                '<strong style="color:#1e293b;font-size:1.05rem;">节省时间</strong><br>'
                '<span style="color:#64748b;font-size:0.9rem;">自动跳过不需要的步骤，<br>专注核心目标</span>'
                '</div>',
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                '<div style="padding:1.2rem;background:#f8fafc;border-radius:10px;border-left:4px solid #3b82f6;box-shadow:0 1px 3px rgba(0,0,0,0.05);">'
                '<div style="font-size:2rem;margin-bottom:0.5rem;">🎯</div>'
                '<strong style="color:#1e293b;font-size:1.05rem;">参数预填充</strong><br>'
                '<span style="color:#64748b;font-size:0.9rem;">基于设备和样品，<br>自动推荐最优参数</span>'
                '</div>',
                unsafe_allow_html=True
            )
        with col3:
            st.markdown(
                '<div style="padding:1.2rem;background:#f8fafc;border-radius:10px;border-left:4px solid #8b5cf6;box-shadow:0 1px 3px rgba(0,0,0,0.05);">'
                '<div style="font-size:2rem;margin-bottom:0.5rem;">🥇</div>'
                '<strong style="color:#1e293b;font-size:1.05rem;">课题组经验</strong><br>'
                '<span style="color:#64748b;font-size:0.9rem;">优先展示师兄师姐<br>的成功经验</span>'
                '</div>',
                unsafe_allow_html=True
            )


        st.markdown("<br>", unsafe_allow_html=True)
        st.info("💡 **只需1分钟，回答5个问题**，即可开始定制化陪跑")

        if st.button("🚀 开始配置", use_container_width=True, type="primary"):
            st.session_state.onboarding_step = 1
            st.rerun()

        return False

    # ========== 问题页（step=1~5）==========
    elif 1 <= step <= 5:
        # 进度条
        progress = (step) / 5
        st.progress(progress, text=f"**配置进度：第 {step}/5 步**")
        st.markdown("---")

        # 问题内容
        if step == 1:
            st.markdown("### 1️⃣ 你的研究目标是什么？")
            st.caption("💬 选择最接近你当前阶段的目标，系统会自动裁剪流程")

            goal_options = {
                "质检": {
                    "label": "初步质检",
                    "desc": "确认数据质量，到 CTF Estimation 即可",
                    "icon": "🔍",
                    "steps": "3步",
                },
                "2D分类": {
                    "label": "2D 分类筛选颗粒",
                    "desc": "需要好的颗粒类别，不做 3D",
                    "icon": "📊",
                    "steps": "6步",
                },
                "3D重构": {
                    "label": "3D 重构",
                    "desc": "完整流程，最终得到三维结构",
                    "icon": "🧊",
                    "steps": "12步",
                },
            }

            selected_goal = None
            for key, opt in goal_options.items():
                is_selected = st.session_state.user_profile.get("goal") == key
                if st.button(
                    f"{opt['icon']} **{opt['label']}** （{opt['steps']}）\n\n{opt['desc']}",
                    key=f"goal_{key}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
                ):
                    selected_goal = key

            if selected_goal:
                st.session_state.user_profile["goal"] = selected_goal
                st.session_state.onboarding_step = 2
                st.rerun()

        elif step == 2:
            st.markdown("### 2️⃣ 你的样品类型？")
            st.caption("💬 样品类型决定了颗粒大小和参数范围")
            st.info(
                "⚠️ **说明**：下方参数为起始参考值，需根据实际 2D 分类结果迭代调整。\n\n"
                "蛋白质形状差异大（球形 vs 拉长），分子量无法直接对应固定直径。"
            )

            sample_options = {
                "小型蛋白/复合物": {
                    "label": "小型蛋白/复合物",
                    "desc": "<150 kDa（起始 ~100Å）",
                    "icon": "🔬",
                },
                "中等蛋白复合物": {
                    "label": "中等蛋白复合物",
                    "desc": "150-500 kDa（起始 ~150Å）",
                    "icon": "🧬",
                },
                "大型复合物": {
                    "label": "大型复合物",
                    "desc": ">500 kDa（起始 ~250Å）",
                    "icon": "⚛️",
                },
                "病毒/高对称颗粒": {
                    "label": "病毒/高对称颗粒",
                    "desc": "需根据已知尺寸设定（20-200 nm）",
                    "icon": "🦠",
                },
                "通用": {
                    "label": "不确定",
                    "desc": "自动判断",
                    "icon": "❓",
                },
            }

            selected_sample = None
            # 前4个选项两列布局，最后1个单独一行居中
            col1, col2 = st.columns(2)
            for i, (key, opt) in enumerate(list(sample_options.items())[:4]):
                is_selected = st.session_state.user_profile.get("sample_type") == key
                with (col1 if i % 2 == 0 else col2):
                    if st.button(
                        f"{opt['icon']} **{opt['label']}**\n\n{opt['desc']}",
                        key=f"sample_{key}",
                        use_container_width=True,
                        type="primary" if is_selected else "secondary",
                    ):
                        selected_sample = key

            # 最后一个"不确定"选项居中显示
            last_key = list(sample_options.keys())[-1]
            last_opt = sample_options[last_key]
            is_selected = st.session_state.user_profile.get("sample_type") == last_key
            col_l, col_center, col_r = st.columns([1, 2, 1])
            with col_center:
                if st.button(
                    f"{last_opt['icon']} **{last_opt['label']}**\n\n{last_opt['desc']}",
                    key=f"sample_{last_key}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
                ):
                    selected_sample = last_key

            if selected_sample:
                st.session_state.user_profile["sample_type"] = selected_sample
                st.session_state.onboarding_step = 3
                st.rerun()

        elif step == 3:
            st.markdown("### 3️⃣ 使用的电镜设备？")
            st.caption("💬 设备决定了电压和像素尺寸")

            microscope_options = {
                "Krios 300kV": {
                    "label": "Titan Krios 300kV",
                    "desc": "像素尺寸通常 0.8-1.0 Å/pix",
                    "icon": "🔬",
                },
                "Arctica 200kV": {
                    "label": "Talos Arctica 200kV",
                    "desc": "像素尺寸通常 1.0-1.2 Å/pix",
                    "icon": "🔭",
                },
                "其他": {
                    "label": "其他设备",
                    "desc": "后续手动填写参数",
                    "icon": "⚙️",
                },
            }

            selected_microscope = None
            for key, opt in microscope_options.items():
                is_selected = st.session_state.user_profile.get("microscope") == key
                if st.button(
                    f"{opt['icon']} **{opt['label']}**\n\n{opt['desc']}",
                    key=f"microscope_{key}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
                ):
                    selected_microscope = key

            if selected_microscope:
                st.session_state.user_profile["microscope"] = selected_microscope
                st.session_state.onboarding_step = 4
                st.rerun()

        elif step == 4:
            st.markdown("### 4️⃣ 目标分辨率？")
            st.caption("💬 分辨率目标影响 2D 分类数量和 CTF 参数")

            resolution_options = {
                "粗筛": {
                    "label": "粗筛（>10Å）",
                    "desc": "快速验证样品质量",
                    "icon": "⚡",
                },
                "中等": {
                    "label": "中等（5-10Å）",
                    "desc": "大多数生物学问题足够",
                    "icon": "🎯",
                },
                "高分辨": {
                    "label": "高分辨（<5Å）",
                    "desc": "需要看侧链细节",
                    "icon": "🔍",
                },
            }

            selected_resolution = None
            for key, opt in resolution_options.items():
                is_selected = st.session_state.user_profile.get("resolution_target") == key
                if st.button(
                    f"{opt['icon']} **{opt['label']}**\n\n{opt['desc']}",
                    key=f"resolution_{key}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
                ):
                    selected_resolution = key

            if selected_resolution:
                st.session_state.user_profile["resolution_target"] = selected_resolution
                st.session_state.onboarding_step = 5
                st.rerun()

        elif step == 5:
            st.markdown("### 5️⃣ 有经验师兄师姐带你吗？")
            st.caption("💬 有人带的话，会优先展示课题组经验库")

            mentor_options = {
                "有": {
                    "label": "有师兄师姐带",
                    "desc": "优先展示课题组经验库",
                    "icon": "🥇",
                },
                "独立探索": {
                    "label": "独立探索",
                    "desc": "依赖官方文档和教学模式",
                    "icon": "📚",
                },
            }

            selected_mentor = None
            col1, col2 = st.columns(2)
            for i, (key, opt) in enumerate(mentor_options.items()):
                is_selected = st.session_state.user_profile.get("has_mentor") == key
                with (col1 if i % 2 == 0 else col2):
                    if st.button(
                        f"{opt['icon']} **{opt['label']}**\n\n{opt['desc']}",
                        key=f"mentor_{key}",
                        use_container_width=True,
                        type="primary" if is_selected else "secondary",
                    ):
                        selected_mentor = key

            if selected_mentor:
                st.session_state.user_profile["has_mentor"] = selected_mentor
                st.session_state.onboarding_step = 6
                st.rerun()

        # 返回按钮（step >= 2 时显示）
        if step >= 2:
            st.markdown("---")
            if st.button("← 上一步", key="onboarding_back"):
                st.session_state.onboarding_step -= 1
                st.rerun()

        return False

    # ========== 确认页（step=6）==========
    elif step == 6:
        st.markdown("# ✨ 你的专属流程方案")
        st.markdown("---")

        # 生成推荐
        workflow = _generate_workflow_recommendation(st.session_state.user_profile)
        st.session_state.recommended_workflow = workflow

        # 方案概览
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("需要步骤", f"{len(workflow['steps'])} 步")
        with col2:
            st.metric("跳过步骤", f"{len(workflow['skip_steps'])} 步")
        with col3:
            goal = st.session_state.user_profile.get("goal", "")
            st.metric("目标", goal)

        st.markdown("### 📋 流程预览")

        # 步骤列表（用表格展示更清晰）
        step_names = {
            "cp_01": "Import Movies",
            "cp_02": "Motion Correction",
            "cp_03": "CTF Estimation",
            "cp_04": "Blob Picker",
            "cp_05": "Extract Particles",
            "cp_06": "2D Classification",
            "cp_07": "Select 2D",
            "cp_08": "Initial Model",
            "cp_09": "3D Classification",
            "cp_10": "3D Refinement",
            "cp_11": "Post-processing",
        }

        for step_id in ["cp_01", "cp_02", "cp_03", "cp_04", "cp_05", "cp_06", "cp_07", "cp_08", "cp_09", "cp_10", "cp_11"]:
            if step_id in workflow["steps"]:
                st.markdown(f"✅ **{step_names.get(step_id, step_id)}**")
            else:
                st.markdown(f"⊗ ~~{step_names.get(step_id, step_id)}~~（跳过）")

        st.markdown("### ⚙️ 推荐参数（可编辑）")
        st.caption("💡 系统已为你填入推荐值，请根据电镜管理员提供的数据修正关键参数")

        params = workflow["params"]

        # 初始化参数编辑状态
        if "_edited_params" not in st.session_state:
            st.session_state._edited_params = params.copy()

        # 关键参数（必须准确）
        st.markdown("#### 🔴 关键参数（请与电镜管理员确认）")

        col1, col2 = st.columns(2)
        with col1:
            voltage = st.number_input(
                "加速电压 (kV) *",
                value=st.session_state._edited_params.get("voltage", 300),
                min_value=100,
                max_value=500,
                step=100,
                help="必须准确！通常为 200kV 或 300kV",
                key="param_voltage"
            )
            st.session_state._edited_params["voltage"] = voltage

        with col2:
            pixel_size = st.number_input(
                "像素尺寸 (Å/pix) *",
                value=st.session_state._edited_params.get("pixel_size", 0.86),
                min_value=0.1,
                max_value=5.0,
                step=0.01,
                format="%.3f",
                help="⚠️ 此参数错误会导致全流程失败！请使用电镜管理员提供的准确值",
                key="param_pixel_size"
            )
            st.session_state._edited_params["pixel_size"] = pixel_size

        st.caption(f"💡 推荐值：加速电压 {params.get('voltage')} kV，像素尺寸 {params.get('pixel_size')} Å/pix")

        # 推荐参数（可后续调整）
        with st.expander("🟡 推荐参数（可后续调整，点击展开编辑）", expanded=False):
            st.warning(
                "⚠️ **起始参考值**：颗粒/掩膜直径基于样品分子量估算，"
                "需根据 2D 分类结果迭代调整（蛋白质形状差异大）。"
            )
            col3, col4 = st.columns(2)

            with col3:
                particle_diameter = st.number_input(
                    "颗粒直径 (Å) — 起始参考",
                    value=st.session_state._edited_params.get("particle_diameter", 150),
                    min_value=50,
                    max_value=500,
                    step=10,
                    help="起始估算值，需根据实际 2D 分类调整",
                    key="param_particle_diameter"
                )
                st.session_state._edited_params["particle_diameter"] = particle_diameter

                max_resolution_ctf = st.number_input(
                    "CTF 最大分辨率 (Å)",
                    value=st.session_state._edited_params.get("max_resolution_ctf", 5),
                    min_value=3,
                    max_value=10,
                    step=1,
                    help="CTF Estimation 时搜索的最高分辨率",
                    key="param_max_resolution_ctf"
                )
                st.session_state._edited_params["max_resolution_ctf"] = max_resolution_ctf

            with col4:
                mask_diameter = st.number_input(
                    "掩膜直径 (Å) — 起始参考",
                    value=st.session_state._edited_params.get("mask_diameter", 180),
                    min_value=50,
                    max_value=600,
                    step=10,
                    help="起始估算：粒子直径 + 溶剂层(~10Å) + 摆动余量(~10Å)",
                    key="param_mask_diameter"
                )
                st.session_state._edited_params["mask_diameter"] = mask_diameter

                num_classes_2d = st.number_input(
                    "2D 分类数",
                    value=st.session_state._edited_params.get("num_classes_2d", 50),
                    min_value=10,
                    max_value=200,
                    step=10,
                    help="颗粒数少时减少，颗粒数多时增加",
                    key="param_num_classes_2d"
                )
                st.session_state._edited_params["num_classes_2d"] = num_classes_2d

        # 保存编辑后的参数到 workflow
        workflow["params"] = st.session_state._edited_params.copy()
        st.session_state.recommended_workflow = workflow

        st.markdown("### 💡 推荐理由")
        st.info(workflow["reason"])

        st.markdown("---")

        # 操作按钮
        col_reset, col_restart, col_confirm = st.columns([1, 1, 2])
        with col_reset:
            if st.button("🔄 恢复推荐值", use_container_width=True, help="恢复系统推荐的默认值"):
                # 重新生成推荐，覆盖编辑
                profile = st.session_state.user_profile
                fresh_workflow = _generate_workflow_recommendation(profile)
                st.session_state._edited_params = fresh_workflow["params"].copy()
                st.session_state.recommended_workflow = fresh_workflow
                st.rerun()

        with col_restart:
            if st.button("← 重新配置", use_container_width=True):
                st.session_state.onboarding_step = 0
                st.session_state.user_profile = {}
                st.session_state.pop("_edited_params", None)
                st.rerun()

        with col_confirm:
            if st.button("✅ 确认并开始", use_container_width=True, type="primary"):
                st.session_state.onboarding_completed = True
                st.session_state.pop("_edited_params", None)  # 清理临时状态
                st.rerun()

        return False

    return False
