# RELION 局部分辨率估计(LocalRes)与手性验证

> 官方来源：https://relion.readthedocs.io/en/release-5.0/SPA_tutorial/Validation.html

**摘要**：post-processing 的分辨率是全局估计，无法描述复合体内部常见分辨率的局域变化。relion 通过 Local resolution job-type 包装 Kucukelbir/Tagare 程序估计局部分辨率，也可选 relion 自身实现（移动软球掩膜）。

**关键步骤**：
1. Local resolution：I/O 选一半未滤波 half-map + User-provided solvent mask + Calibrated pixel size: 1.244
2. Relion tab：Use Relion?: Yes，User-provided B-factor: -30，MTF of detector: mtf_k2_200kv.star
3. 输出 relion_locres.mrc 可在 UCSF chimera 按局部分辨率着色
4. 检查手性：α-helix 转向错误提示手性反了；SGD 初始模型有 50% 概率反手
5. 命令行翻转手性：relion_image_handler --i postprocess.mrc --o ..._invert.mrc --invert_hand

**质控要点**：
- 局部分辨率图描述整体 map 质量变化
- 正确手性后叠加原子模型（如 PDB 5a1a β-galactosidase）验证
- 8 MPI 运行约 7 分钟

**注意事项**：
- 绝对手性无法从数据确定（除非倾斜样品台）
- 像素尺寸偏差几个百分点在 LocalRes 提供正确值即可，无需重精修
- 偏振随机化 FSC 红曲线应≈0
