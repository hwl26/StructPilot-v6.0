# RELION 溶剂掩膜创建(MaskCreate)与后处理锐化(PostProcess)

> 官方来源：https://relion.readthedocs.io/en/release-5.0/SPA_tutorial/Mask.html

**摘要**：3D auto-refine 后需锐化 map。gold-standard FSC 在精修中仅用未掩膜 map（除非用 solvent-flattened FSCs），导致分辨率被溶剂区噪声低估。先做掩膜定义蛋白/溶剂边界，再做 post-processing（B-factor 锐化 + 计算 masked FSC）。

**关键步骤**：
1. Mask Creation：I/O 选 Refine3D/job019/run_class001.mrc
2. Mask tab：Lowpass filter map (A): 15，Pixel size (A): -1（自动从header），Initial binarisation threshold: 0.01，Extend binary map: 3 px，Add soft-edge: 8 px
3. Post-processing：I/O 选一半未滤波 half-map + Solvent mask + Calibrated pixel size: 1.244
4. Sharpen tab：Estimate B-factor automatically?: Yes，Lowest resolution for auto-B fit (A): 10
5. MTF of detector: mtf_k2_200kV.star，Original detector pixel size: 0.885

**质控要点**：
- PostProcess 后查看 FSC 曲线与 Guinier 图
- phase-randomized FSC（红曲线）在估计分辨率处应≈0；否则掩膜过锐
- 掩膜应包裹整个结构但不含过多溶剂

**注意事项**：
- 掩膜过锐或细节过多→FSC 红曲线不归零，需更强低通/更软更宽掩膜后重做
- 像素尺寸若偏差几个百分点，在 PostProcess 提供正确 Calibrated pixel size 即可，无需重精修
- 掩膜 soft-edge 余弦过渡很重要，过锐对 FSC 校正敏感
