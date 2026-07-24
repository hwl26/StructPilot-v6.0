"""StructPilot v6.0 — 高级模式渲染层。

复用原有双栏布局，追加：参数导出、预设管理、贡献经验入口。
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Callable

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
_PRESETS_DIR = BASE_DIR / "runtime" / "presets"
_LAB_EXP_PATH = BASE_DIR / "knowledge_base" / "lab_experience_kb.json"
_IMG_DIR = BASE_DIR / "runtime" / "experience_images"


def _export_params_csv(current_cp: dict) -> str:
    """把当前步骤参数导出为 CSV 字符串。"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["参数名", "推荐值", "默认值", "说明"])
    for tab in current_cp.get("tabs", []):
        for p in tab.get("parameters", []):
            writer.writerow([
                p.get("name", ""),
                p.get("recommended_value", ""),
                p.get("default_value", ""),
                p.get("description", ""),
            ])
    return buf.getvalue()


def _export_params_json(current_cp: dict) -> str:
    out = {}
    for tab in current_cp.get("tabs", []):
        for p in tab.get("parameters", []):
            key = p.get("name", "")
            if key:
                out[key] = p.get("recommended_value", p.get("default_value", ""))
    return json.dumps(out, ensure_ascii=False, indent=2)


def _save_preset(preset_name: str, note: str, software: str, cp_id: str, params_json: str) -> bool:
    try:
        _PRESETS_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in preset_name)
        path = _PRESETS_DIR / f"{safe_name}.json"
        preset = {
            "preset_name": preset_name,
            "note": note,
            "software": software,
            "step": cp_id,
            "params": json.loads(params_json),
        }
        path.write_text(json.dumps(preset, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def _save_experience_images(uploaded_files: list, cp_id: str) -> list[str]:
    """保存上传的截图，返回文件名列表"""
    import datetime

    _IMG_DIR.mkdir(parents=True, exist_ok=True)

    saved_filenames = []
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    for idx, img_file in enumerate(uploaded_files[:3]):  # 最多3张
        # 生成唯一文件名
        ext = Path(img_file.name).suffix.lower()
        if ext not in [".png", ".jpg", ".jpeg"]:
            continue

        filename = f"{cp_id}_{timestamp}_{idx}{ext}"

        # 检查文件大小（最大5MB）
        file_size = len(img_file.getbuffer())
        if file_size > 5 * 1024 * 1024:
            continue

        # 保存到磁盘
        target_path = _IMG_DIR / filename
        target_path.write_bytes(img_file.getbuffer())

        saved_filenames.append(filename)

    return saved_filenames


def _list_presets() -> list[dict]:
    try:
        _PRESETS_DIR.mkdir(parents=True, exist_ok=True)
        result = []
        for f in _PRESETS_DIR.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                d["_filename"] = f.name
                result.append(d)
            except Exception:
                pass
        return result
    except Exception:
        return []


def _render_export_panel(current_cp: dict) -> None:
    """参数导出面板。"""
    cp_id = current_cp.get("checkpoint_id", "")
    cp_cn = current_cp.get("checkpoint_cn", cp_id)

    st.markdown("#### 📥 导出当前步骤参数")
    st.caption("仅导出本步骤的参数设置（用于记录/对比），不是完整 Workflow")
    col_csv, col_json = st.columns(2)
    with col_csv:
        csv_data = _export_params_csv(current_cp)
        st.download_button(
            "📄 CSV 表格",
            csv_data,
            file_name=f"{cp_id}_params.csv",
            mime="text/csv",
            use_container_width=True,
            help="参数表格，可用 Excel 打开",
        )
    with col_json:
        json_data = _export_params_json(current_cp)
        st.download_button(
            "📋 JSON 数据",
            json_data,
            file_name=f"{cp_id}_params.json",
            mime="application/json",
            use_container_width=True,
            help="参数 JSON，便于程序读取",
        )


def _render_preset_manager(current_cp: dict, software: str) -> None:
    """预设保存/加载面板。"""
    cp_id = current_cp.get("checkpoint_id", "")
    json_data = _export_params_json(current_cp)

    st.markdown("#### 💾 预设管理")
    col_save, col_load = st.columns(2)

    with col_save:
        st.markdown("**保存为预设**")
        preset_name = st.text_input("预设名称", key="expert_preset_name",
                                    placeholder="例：TRPV1膜蛋白标准流程")
        note = st.text_input("备注（可选）", key="expert_preset_note",
                              placeholder="适用条件、注意事项")
        if st.button("💾 保存", key="expert_save_preset", use_container_width=True):
            if preset_name.strip():
                ok = _save_preset(preset_name, note, software, cp_id, json_data)
                if ok:
                    st.success(f"已保存预设：{preset_name}")
                else:
                    st.error("保存失败，请检查运行目录写入权限")
            else:
                st.warning("请先输入预设名称")

    with col_load:
        st.markdown("**加载已有预设**")
        presets = _list_presets()
        if presets:
            names = [p.get("preset_name", p.get("_filename", "")) for p in presets]
            sel = st.selectbox("选择预设", names, key="expert_load_sel")
            sel_preset = next((p for p in presets if p.get("preset_name") == sel), None)
            if sel_preset:
                st.json(sel_preset.get("params", {}))
            if st.button("📤 加载到当前步骤", key="expert_load_preset", use_container_width=True):
                st.info("请手动将上方参数值填入软件（一键导入功能规划中）")
        else:
            st.caption("暂无已保存的预设")


def _render_kb_contribute_panel(current_cp: dict) -> None:
    """贡献课题组经验入口（含截图上传）。"""
    cp_id = current_cp.get("checkpoint_id", "")
    cp_cn = current_cp.get("checkpoint_cn", cp_id)

    st.markdown("#### 💡 贡献课题组经验")
    with st.form(key=f"kb_contribute_{cp_id}"):
        title = st.text_input("标题（简短描述问题）", placeholder="例：Motion Correction 报错 local motion too large")
        category = st.selectbox("分类", ["报错解决方案", "参数调优经验", "非常规流程", "软件技巧"])
        symptoms_text = st.text_area("症状描述（遇到了什么问题）", height=70)
        solution = st.text_area("解决方案（怎么解决的）", height=80)

        # 📸 截图上传
        st.markdown("**📸 截图 + 🎬 操作视频（可选）**")
        col_img, col_vid = st.columns(2)
        with col_img:
            uploaded_files = st.file_uploader(
                "报错截图或结果图",
                type=["png", "jpg", "jpeg"],
                accept_multiple_files=True,
                help="最多 3 张，每张 <5MB",
                key=f"kb_images_{cp_id}"
            )
        with col_vid:
            video_file = st.file_uploader(
                "操作演示视频",
                type=["mp4", "mov", "avi", "webm"],
                help="最多 50MB，演示完整操作步骤",
                key=f"kb_video_{cp_id}"
            )
            video_url = st.text_input(
                "或填写外链（B站/YouTube）",
                placeholder="https://www.bilibili.com/video/...",
                key=f"kb_video_url_{cp_id}"
            )

        # 预览
        if uploaded_files:
            cols = st.columns(min(len(uploaded_files), 3))
            for idx, img_file in enumerate(uploaded_files[:3]):
                with cols[idx]:
                    st.image(img_file, caption=img_file.name, use_container_width=True)
        if video_file:
            st.video(video_file)
        elif video_url.strip():
            st.caption(f"🔗 视频外链：{video_url.strip()}")

        tags_str = st.text_input("标签（逗号分隔）", placeholder="运动校正, 漂移, B-factor")
        submitted = st.form_submit_button("提交经验")

    if submitted:
        if title.strip() and solution.strip():
            try:
                # ✨ 输入验证和清理
                from utils.security import sanitize_user_input, validate_json_size

                # 长度限制检查
                if len(title) > 200:
                    st.error("标题过长（最多 200 字符）")
                    return
                if len(solution) > 5000:
                    st.error("解决方案过长（最多 5000 字符）")
                    return

                # 保存截图
                image_filenames = []
                if uploaded_files:
                    image_filenames = _save_experience_images(uploaded_files, cp_id)

                # 🎬 保存视频文件
                saved_video_path = ""
                if video_file:
                    try:
                        import datetime as _dt, os as _os
                        vid_dir = BASE_DIR / "runtime" / "experience_media"
                        vid_dir.mkdir(parents=True, exist_ok=True)
                        ext = Path(video_file.name).suffix.lower()
                        vid_name = f"{cp_id}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                        (vid_dir / vid_name).write_bytes(video_file.getbuffer())
                        saved_video_path = vid_name
                    except Exception:
                        pass  # 视频保存失败不阻断提交

                try:
                    data = json.loads(_LAB_EXP_PATH.read_text(encoding="utf-8"))
                except Exception:
                    data = {"entries": [], "meta": {}}

                # ✨ 术语规范化和自动标签提取
                from utils.terminology import normalize_text, auto_extract_tags

                normalized_title = normalize_text(title)
                normalized_symptoms = normalize_text(symptoms_text)
                normalized_solution = normalize_text(solution)

                # 用户手动输入的标签
                manual_tags = [t.strip() for t in tags_str.split(",") if t.strip()]

                # 自动提取的标签
                auto_tags = auto_extract_tags(normalized_title, normalized_symptoms, normalized_solution)

                # 合并标签（手动优先，去重）
                all_tags = list(dict.fromkeys(manual_tags + auto_tags))[:10]  # 最多10个

                # ✨ 去重检测
                from utils.deduplication import find_similar_experiences
                similar = find_similar_experiences(
                    normalized_title,
                    data.get("entries", []),
                    threshold=0.80
                )
                if similar:
                    st.warning(
                        f"⚠️ 发现相似的经验（相似度 {similar[0]['similarity']:.0%}）：\n\n"
                        f"**{similar[0]['entry'].get('title', '')}**\n\n"
                        f"确定要继续提交吗？可能造成重复。"
                    )
                    if not st.button("✓ 确认提交（不是重复）", key=f"confirm_submit_{cp_id}"):
                        st.stop()

                import datetime
                new_entry = {
                    "id": f"lab_{len(data['entries'])+1:03d}",
                    "category": category,
                    "title": normalized_title,
                    "source": "lab_experience",
                    "author": "用户贡献",
                    "date": datetime.date.today().isoformat(),
                    "status": "pending",  # ✨ 审核状态：待审核
                    "software": "通用",
                    "step": cp_id,
                    "symptoms": [s.strip() for s in normalized_symptoms.split("；") if s.strip()],
                    "symptoms_text": normalized_symptoms,
                    "solution": normalized_solution,
                    "tags": all_tags,
                    "images": image_filenames,
                    "video_path": saved_video_path,
                    "video_url": video_url.strip() if video_url.strip() else "",
                }
                data["entries"].append(new_entry)
                _LAB_EXP_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

                img_info = f"（含 {len(image_filenames)} 张截图）" if image_filenames else ""
                tag_info = f"，自动生成 {len(auto_tags)} 个标签" if auto_tags else ""
                st.success(f"✅ 经验已提交{img_info}{tag_info}，待管理员审核后生效（目前标注「待验证」，已可检索）")

                # ✨ 新增：GitHub Issues 分享入口
                st.markdown("---")
                st.markdown("**📤 想让更多人受益？提交到课题组经验库：**")

                # 构建预填的 GitHub Issue URL
                import urllib.parse
                issue_title = f"[经验贡献] {normalized_title}"
                issue_body = f"""**分类**：{category}
**步骤**：{cp_cn} ({cp_id})

**症状**：
{normalized_symptoms}

**解决方案**：
{normalized_solution}

**标签**：{', '.join(all_tags)}

---
_本条经验由 StructPilot v6.0 用户贡献_
"""
                issue_url = f"https://github.com/hwl26/StructPilot-v6.0/issues/new?title={urllib.parse.quote(issue_title)}&body={urllib.parse.quote(issue_body)}&labels=经验贡献,{urllib.parse.quote(cp_id)}"

                st.link_button(
                    "📤 提交到 GitHub Issues（公开分享）",
                    url=issue_url,
                    help="管理员审核通过后会合并到正式知识库，全体用户可见",
                    use_container_width=True,
                )
            except Exception as exc:
                st.error(f"提交失败：{exc}")
        else:
            st.warning("请至少填写标题和解决方案")


def render_expert_view(
    current_cp: dict,
    software: str,
) -> None:
    """高级模式：在折叠面板中渲染导出/预设/贡献经验功能。"""
    cp_id = current_cp.get("checkpoint_id", "")
    cp_cn = current_cp.get("checkpoint_cn", current_cp.get("checkpoint_name", ""))

    st.markdown(f"#### 当前步骤：{cp_cn}")

    # ── 工具栏 ───────────────────────────────────────────────
    t_export, t_presets, t_contribute = st.tabs(
        ["📥 导出参数", "💾 预设管理", "💡 贡献经验"]
    )

    with t_export:
        _render_export_panel(current_cp)

    with t_presets:
        _render_preset_manager(current_cp, software)

    with t_contribute:
        _render_kb_contribute_panel(current_cp)

