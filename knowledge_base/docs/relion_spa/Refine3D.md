# RELION 高分辨率 3D 精修(Refine3D)

> 官方来源：https://relion.readthedocs.io/en/release-5.0/SPA_tutorial/Refine3D.html

**摘要**：同质性子集选定后，用 3D auto-refine 全自动高分辨率精修。采用 gold-standard FSC（独立半集）估计分辨率避免自增强过拟合，并自动判断收敛，几乎无需调参。

**关键步骤**：
1. 先重新提取粒子（更少下采样）：Particle extraction，OR re-extract refined particles?: Yes，Particle box size: 360，Rescale: Yes，Re-scaled size: 256（→1.244 Å，限分辨率~2.5Å）
2. I/O tab：Input images STAR: Extract/job018/particles.star，Reference map: 缩放至256盒的 class map
3. Reference tab：Ref. map is on absolute greyscale?: No，Initial low-pass filter (A): 50，Symmetry: D2
4. Optimisation/CTF tab 同 Class3D；Auto-sampling tab：Use finer angular sampling faster?: Yes
5. Compute tab：Use parallel disc I/O?: Yes，Skip padding?: Yes（省内存但小心混叠），Pre-read all particles into RAM?: Yes，Use GPU acceleration?: Yes；Running tab：Number of MPI procs: 5（奇数，最小3），threads: 6

**质控要点**：
- 收敛时最后迭代分辨率显著提升（两半集合并）
- grep Auto Refine3D/job019/run.out 查看采样与分辨率估计
- odd MPI 数最高效（1 master + 2 half-set worker sets）

**注意事项**：
- Skip padding?: Yes 省内存但 box 紧时边缘可能混叠
- 高对称精修才用 3.7° 采样+0.9° 局部搜索，其余默认 7.5°/1.8°
- 大 box 末迭代内存显著增加
