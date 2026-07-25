def _render_relion_beginner_guide(state: Any) -> None:
    """渲染 RELION 入门模式操作指南（图文版）。"""
    st.markdown("## 🔬 RELION 快速上手指南")
    st.caption("针对入门用户的 RELION Import + Motion Correction 图文教程")

    # 工作流说明（去掉警告图标）
    st.info(
        "**🔬 RELION 工作流：**\n\n"
        "入门模式下，RELION 主要用于前期数据预处理：\n\n"
        "✅ **步骤1：数据导入** (Import) → 创建项目和 STAR 文件\n"
        "✅ **步骤2：运动校正** (Motion Correction) → 校正帧间漂移\n\n"
        "**完成后建议切换到 cryoSPARC** 继续 CTF 估计、颗粒挑选等步骤。\n\n"
        "需要完整 RELION 功能？请切换到「⚙️ 高级模式」。"
    )

    # 快速切换按钮
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 切换到 cryoSPARC", use_container_width=True, type="primary"):
            state.software = "cryosparc"
            st.rerun()
    with col2:
        if st.button("⚙️ 切换到高级模式", use_container_width=True):
            st.session_state.app_mode = "expert"
            st.rerun()

    st.markdown("---")

    # 步骤1：数据传输和准备
    with st.expander("📁 **前置步骤：数据传输与准备**", expanded=True):
        st.markdown("### 1.1 查看数据储存路径")
        st.code("""# 登录数据采集节点
ssh user@10.15.56.xxx

# 进入 Titan3 数据目录
cd /home/Titan3_falcon/

# 查找你的数据文件夹
ls
pwd

# 复制路径，例如：
# /home/Titan3_falcon/YourProject_20250704""", language="bash")

        st.markdown("### 1.2 传输数据到工作节点")
        st.code("""# 登录工作节点
ssh user@10.15.80.xxx

# 进入目标目录
cd /cluster-backup/pool-duke/EM_data

# 使用 rsync 传输数据
rsync -avrP -e "ssh -p 10086" \\
    user@10.15.56.xxx:/home/Titan3_falcon/YourProject_20250704 \\
    .

# 注意：末尾的 . 表示当前目录，不要省略！""", language="bash")

        st.markdown("### 1.3 创建 RELION 工作目录")
        st.code("""# 进入工作盘
cd /work/fs/pool/pool-duke/EM_Data

# 创建项目文件夹
mkdir YourProject_20250704
cd YourProject_20250704

# 创建 Movies 文件夹
mkdir Movies
cd Movies""", language="bash")

        st.markdown("### 1.4 创建软连接")
        st.info("💡 **为什么用软连接？** 避免重复复制大文件，节省空间")
        st.code("""# 创建 .eer 文件软连接
ln -s /cluster-backup/pool-duke/EM_data/YourProject_20250704/*.eer .

# 创建 .gain 文件软连接
ln -s /cluster-backup/pool-duke/EM_data/YourProject_20250704/*.gain .

# 检查软连接
ls -lh""", language="bash")

        st.warning("**⚠️ 特殊情况：EER 文件分散在多个 GridSquare 中**")
        st.code("""# 如果 .eer 文件在 GridSquare 子目录中，需要先移动
mv Images-Disc1/GridSquare*/Data/*.eer .

# 然后再创建软连接""", language="bash")

    # 步骤2：计算帧数和分组
    with st.expander("📊 **步骤 0：计算 EER Fractionation**", expanded=True):
        st.markdown("### 为什么要计算？")
        st.write("EER 文件包含多个 sections（帧），需要计算如何分组用于 Motion Correction。")

        st.markdown("### 使用 `header` 命令查看帧数")
        st.code("""# 打开任意 .eer 文件
header Movies/FoilHole_xxxxx.eer

# 查看输出中的 sections 数量""", language="bash")

        st.image("https://via.placeholder.com/800x200/1e293b/ffffff?text=header+输出示例：Number+of+sections:+1379")
        st.caption("📌 图示：header 命令输出，红框标注 sections 数量")

        st.markdown("### 计算 EER Fractionation")
        st.latex(r"\text{EER Fractionation} = \left\lfloor \frac{\text{total sections}}{\text{target frames}} \right\rfloor")
        st.markdown("**示例：**")
        st.markdown("- Total sections = 1379\n- Target frames = 40\n- EER Fractionation = 1379 ÷ 40 = **34**（取整数）")

        st.success("💡 **提示：** 小数部分舍去，只保留整数")

    # 步骤3：Import
    with st.expander("📂 **步骤1：数据导入 (Import)**", expanded=True):
        st.markdown("### 1.1 启动 RELION")
        st.code("""# 方法1：直接启动
relion &

# 方法2：加载特定版本
module load relion/5.0.4
relion &""", language="bash")

        st.markdown("### 1.2 Import 界面操作")
        st.image("https://via.placeholder.com/800x400/2563eb/ffffff?text=RELION+Import+界面示例")
        st.caption("📌 图示：RELION GUI - Import job type 界面")

        st.markdown("#### 关键参数填写")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("**参数**")
            st.markdown("- Raw input files")
            st.markdown("- Pixel size")
            st.markdown("- Voltage")
            st.markdown("- Cs")
        with col2:
            st.markdown("**填写示例**")
            st.markdown("- `Movies/*.eer`（手动输入，不用Browse）")
            st.markdown("- `0.96` Å")
            st.markdown("- `300` kV")
            st.markdown("- `2.7` mm")

        st.warning("**⚠️ 注意：** 不要点击 Browse，直接在输入框输入 `Movies/*.eer`")

        st.markdown("### 1.3 运行 Import")
        st.markdown("1. 填写完参数后，点击右下角 **`Run`** 按钮")
        st.markdown("2. 等待完成，查看输出窗口")

        st.image("https://via.placeholder.com/800x150/10b981/ffffff?text=导入成功：Written+Import/job001/movies.star+with+2988+items")
        st.caption("📌 图示：Import 成功输出")

        st.success("✅ **成功标志：** 生成 `Import/job001/movies.star` 文件")

        # 常见问题（紧凑版）
        st.markdown("### 常见问题")
        with st.container():
            st.markdown("""
<style>
.compact-error {
    background: #fee2e2;
    border-left: 4px solid #dc2626;
    padding: 8px 12px;
    margin: 4px 0;
    border-radius: 4px;
    font-size: 0.9em;
}
</style>

<div class="compact-error">
<b>❌ 路径错误：</b> 确保文件路径正确，支持绝对路径和相对路径
</div>

<div class="compact-error">
<b>❌ Pixel size 错误：</b> 影响后续所有步骤的尺度，务必核对
</div>

<div class="compact-error">
<b>❌ Gain reference 缺失：</b> 如果 movies 未应用 gain，需要在 Motion Correction 中指定
</div>
""", unsafe_allow_html=True)

    # 步骤4：Motion Correction
    with st.expander("🎬 **步骤2：运动校正 (Motion Correction)**", expanded=True):
        st.markdown("### 2.1 选择 Motion Correction")
        st.image("https://via.placeholder.com/800x400/8b5cf6/ffffff?text=Motion+Correction+界面示例")
        st.caption("📌 图示：Motion Correction 参数设置界面")

        st.markdown("### 2.2 核心参数设置")

        # I/O Tab
        st.markdown("#### **I/O Tab（输入输出）**")
        st.markdown("""
| 参数 | 填写值 | 说明 |
|------|--------|------|
| **Input movies STAR file** | `Import/job001/movies.star` | 选择上一步生成的 STAR 文件 |
| **Dose per frame (e/Å²)** | `1.25` | 总剂量 ÷ 帧数（如 50e/40帧=1.25） |
| **EER fractionation** | `37`（之前计算的值） | sections ÷ 目标帧数 |
        """)

        # Motion Tab
        st.markdown("#### **Motion Tab（运动校正）**")
        st.markdown("""
| 参数 | 推荐值 | 说明 |
|------|--------|------|
| **Bfactor** | `150` | 帧加权参数（如遇到 motion too large 错误，调高到 500-800） |
| **Patch size** | `5 x 5` | 局部运动校正网格 |
| **Binning factor** | `1` | 不降采样（或 `2` 降采样） |
        """)

        # Running Tab
        st.markdown("#### **Running Tab（运行配置）**")
        st.markdown("""
| 参数 | 填写值 | 说明 |
|------|--------|------|
| **Number of MPI** | `1` | MPI 进程数 |
| **Number of threads** | `12-24` | 根据服务器CPU核数 |
| **GPUs to use** | `0` 或 `0:1:2:3` | GPU 设备 ID |
        """)

        st.markdown("### 2.3 运行 Motion Correction")
        st.markdown("1. 确认所有参数填写正确")
        st.markdown("2. 点击右下角 **`Continue!`** 或 **`Run`** 按钮")
        st.markdown("3. 查看进度条和日志输出")

        st.image("https://via.placeholder.com/800x200/10b981/ffffff?text=运行中...请等待")
        st.caption("📌 图示：Motion Correction 运行中")

        st.success("✅ **完成标志：** 生成 `MotionCorr/job002/corrected_micrographs.star`")

        # 常见问题（紧凑版）
        st.markdown("### 常见问题")
        with st.container():
            st.markdown("""
<div class="compact-error">
<b>❌ 运动过大：</b> Bfactor 设置过小，尝试调高到 500-800
</div>

<div class="compact-error">
<b>❌ Gain 不匹配：</b> 检查 gain reference 的尺寸和方向
</div>

<div class="compact-error">
<b>❌ GPU 错误：</b> 检查 CUDA 版本和驱动，或改用 CPU 模式
</div>
""", unsafe_allow_html=True)

    # 步骤5：导出和切换
    with st.expander("🚀 **步骤3：完成后续流程**", expanded=False):
        st.markdown("### 恭喜！RELION 前期处理完成 🎉")
        st.write("你已经完成了数据导入和运动校正，现在可以：")

        st.markdown("#### **选项1：继续使用 RELION（高级模式）**")
        st.markdown("- CTF Estimation")
        st.markdown("- Particle Picking")
        st.markdown("- 2D/3D Classification")

        st.markdown("#### **选项2：切换到 cryoSPARC（推荐）**")
        st.markdown("- 导入 RELION 的 corrected micrographs")
        st.markdown("- 继续 CTF、Picking、分类、重构流程")

        st.info("💡 **提示：** cryoSPARC 的后期处理速度更快，推荐混合工作流")

        if st.button("✨ 切换到 cryoSPARC - CTF 估计", use_container_width=True, type="primary", key="continue_cryosparc"):
            state.software = "cryosparc"
            # 设置当前步骤为 CTF Estimation
            if hasattr(state, 'current_cp_id'):
                state.current_cp_id = "cp_03"  # CTF Estimation
            st.success("✅ 已切换到 cryoSPARC！准备进行 CTF 估计")
            st.rerun()

    # 参数速查表
    st.markdown("---")
    st.markdown("## 📋 参数速查表")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 像素大小")
        st.markdown("""
- **超高分辨率**：0.41 - 0.66 Å
- **高分辨率**：0.66 - 0.85 Å
- **中等分辨率**：0.85 - 1.06 Å
        """)

    with col2:
        st.markdown("### 加速电压")
        st.markdown("""
- **Titan Krios**：300 kV
- **Glacios**：200 kV
- **Cs**：2.7 mm（常见值）
        """)

    with col3:
        st.markdown("### 剂量参数")
        st.markdown("""
- **总剂量**：50 - 60 e⁻/Ų
- **帧数**：40 - 50 frames
- **每帧剂量**：总剂量 ÷ 帧数
        """)

    # 底部提示
    st.markdown("---")
    st.success("✅ **完成 RELION Motion Correction 后，点击上方按钮切换到 cryoSPARC 继续流程！**")
