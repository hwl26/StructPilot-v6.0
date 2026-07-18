# RELION CTF 与像差精修(CtfRefine)

> 官方来源：https://relion.readthedocs.io/en/release-5.0/SPA_tutorial/CtfRefine.html

**摘要**：用 CTF refinement job-type 估计数据集中的对称/非对称像差、各向异性放大、并重新估计每颗粒 defocus。可从 3D auto-refine 与对应 Post-processing 运行，以较小计算成本进一步提升分辨率。

**关键步骤**：
1. 高阶像差：I/O 选 Refine3D particles + Postprocess STAR；Fit tab：Estimate beamtilt?: Yes，Also estimate trefoil?: Yes，estimate 4th order aberrations?: Yes，Minimum resolution for fits (A): 30
2. 各向异性放大：Estimate anisotropic magnification?: Yes（禁用其他选项），Minimum resolution: 30
3. 每颗粒 defocus：Perform CTF parameter fitting?: Yes，Fit defocus?: Per-particle，Fit astigmatism?: Per-micrograph，Fit B-factor/phase-shift/beamtilt/4th: No，Minimum resolution: 30
4. 建议重跑 3D auto-refine + Post-processing 确认改进

**质控要点**：
- 查看 logfile.pdf 分析像差（beamtilt 非对称图蓝红不对称，trefoil 3-fold，tetrafoil 4-fold）
- 各向异性查看 optics 表 _rlnMagMat 接近单位矩阵
- 每颗粒 defocus 按微图着色查看倾斜冰层

**注意事项**：
- 先估计最大误差源（一般先 beamtilt）
- 各向异性放大与像差同时精修不稳定，须分开
- per-particle defocus 需参考分辨率远超 4 Å 才稳定
- 建议迭代：CTF 精修后可再 Bayesian polishing，反之亦可
