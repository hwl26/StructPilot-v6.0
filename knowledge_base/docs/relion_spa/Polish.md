# RELION Bayesian polishing（贝叶斯抛光）

> 官方来源：https://relion.readthedocs.io/en/release-5.0/SPA_tutorial/Polish.html

**摘要**：relion 实现基于参考的每颗粒 beam-induced motion 校正的贝叶斯方法，优化正则化似然，对每颗粒轨迹关联平滑时空运动的先验。先训练模式估计最优先验参数，再抛光模式拟合所有颗粒运动并产生加权平均。

**关键步骤**：
1. 训练模式：I/O 选 MotionCorr corrected micrographs + Refine3D/CtfRefine particles + Postprocess STAR；First/Last frame: 1/-1
2. Train tab：Train optimal parameters?: Yes，Fraction of Fourier pixels for testing: 0.5，Use this many particles: 3000；Perform particle polishing?: No（单 MPI）
3. 抛光模式：Perform particle polishing?: Yes，Optimised parameter file 或 OR use your own parameters?: Yes
4. 自带参数（示例）：Sigma for velocity: 0.45，Sigma for divergence: 1290，Sigma for acceleration: 2.66，Min/Max resolution for B-factor fit: 20/-1
5. 抛光后重跑 3D auto-refine（shiny.star）+ Post-processing

**质控要点**：
- polish 输出 shiny.star 与 PDF logfile（scale/B-factor 图、颗粒轨迹）
- 重跑精修+后处理确认分辨率提升（示例达 2.9 Å）
- 提供 half-map 作参考可防过拟合，Initial low-pass: 8，Use solvent-flattened FSCs?: Yes

**注意事项**：
- Bayesian polishing 不推荐丢弃首/末帧（B-factor 自动优化 SNR）
- 训练未 MPI 并行，须单 MPI；默认参数 σvel=0.2;σdiv=5000;σacc=2 常可直接用
- 训练结果有时不稳定（多次运行 sigma 差异大），但抛光实际分辨率常不敏感
- CTF 精修与 polishing 顺序可互换，先处理最大问题
