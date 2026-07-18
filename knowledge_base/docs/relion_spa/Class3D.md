# RELION 3D 分类(Class3D)

> 官方来源：https://relion.readthedocs.io/en/release-5.0/SPA_tutorial/Class3D.html

**摘要**：无监督 3D 分类，relion 的 3D multi-reference refinement 提供强大异质性分析。从 3D classification job-type 运行，可对数据集分亚组描述变异性。

**关键步骤**：
1. I/O tab：Input images STAR: Select/job014/particles.star，Reference map: InitialModel/job015/initial_model.mrc
2. Reference tab：Ref. map is on absolute greyscale?: Yes，Initial low-pass filter (A): 50，Symmetry: C1
3. CTF tab：Do CTF correction?: Yes，Ignore CTFs until first peak?: No
4. Optimisation tab：Number of classes: 4，Regularisation parameter T: 4，Number of iterations: 25，Mask diameter (A): 200，Mask individual particles with zeros?: Yes，Limit resolution E-step to (A): -1，Use Blush regularisation?: Yes
5. Sampling tab 通常不改；Compute tab：Use GPU acceleration?: Yes；Running tab：Number of MPI procs: 5，threads: 6
6. Subset selection：Automatically select 2D classes?: No，手动选优类丢弃亚优类

**质控要点**：
- 在 2D slices 查看类重建评估未解异质性（模糊/条纹区）
- 用 relion_star_printtable 查看 rlnResolution/rlnSsnrMap
- grep _rlnChangesOptimalClasses 检查收敛

**注意事项**：
- 类平均过噪→降低 T；分辨率不足→提高 T
- 初始分类常用 C1 无对称以分离坏颗粒并验证对称性
- Blush regularisation 需 relion-5 conda + CUDA GPU，否则设 No
- 3D 分类计算更耗内存，常用更多 threads
