# RELION 2D 分类(Class2D)与优类筛选

> 官方来源：https://relion.readthedocs.io/en/release-5.0/SPA_tutorial/Class2D.html

**摘要**：参考自由 2D 类平均，用于剔除坏颗粒。坏颗粒平均差会落入小类，剔除即数据清洗。使用 VDAM 算法（relion-4.0 引入）比 EM 更快且类平均更好。

**关键步骤**：
1. I/O tab：Input images STAR: Extract/job012/particles.star
2. Optimisation tab：Number of classes: 100，Regularisation parameter T: 2
3. Use EM algorithm?: No，Use VDAM algorithm?: Yes，Number of VDAM mini-batches: 100
4. Mask diameter (A): 200，Mask individual particles with zeros?: Yes
5. Center class averages?: Yes
6. Compute tab：Use GPU acceleration?: Yes；Running tab：Number of MPI procs: 1，threads: 12
7. Subset selection (Select/job014)：Automatically select 2D classes?: Yes，Minimum threshold: 0.1

**质控要点**：
- 类平均应像低通滤波原子模型投影，溶剂区应平坦
- 溶剂区径向条纹是过拟合典型信号，可限制 E-step 分辨率(10-15A)

**注意事项**：
- 类平均过噪→降低 T；分辨率不足→提高 T
- VDAM 算法不能 MPI 并行，须单 MPI
- 2D 分类与 Subset selection 可重复多次，但勿丢弃少数视角
