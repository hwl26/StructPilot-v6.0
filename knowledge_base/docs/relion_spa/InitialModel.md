# RELION 初始模型生成(InitialModel/Ab-initio)

> 官方来源：https://relion.readthedocs.io/en/release-5.0/SPA_tutorial/InitialModel.html

**摘要**：relion-4.0 用梯度驱动算法从 2D 颗粒生成 de novo 3D 初始参考（不同于 CryoSPARC 的 SGD）。需合理视角分布与良好 2D 类平均，产出可用于 3D 分类或 3D auto-refine 的低分辨率模型。

**关键步骤**：
1. I/O tab：Select/job014/particles.star
2. Optimisation tab：Number of VDAM mini-batches: 100，Regularisation parameter T: 4，Number of classes: 1，Mask diameter (A): 200
3. Flatten and enforce non-negative solvent?: Yes，Symmetry: D2，Run in C1 and apply symmetry later?: Yes
4. Compute tab：Use GPU acceleration?: Yes；Running tab：Number of MPI procs: 1，threads: 12
5. Display 查看 InitialModel/job015/initial_model.mrc 评估伪影

**质控要点**：
- 在 2D slices 中查看 3D map 评估伪影（如溶剂区条纹）
- 可用 UCSF chimera 在 3D 查看

**注意事项**：
- 梯度驱动算法不能多 MPI 并行
- C1 运行再后续应用对称性收敛更好
- 均匀数据集单类(class=1)即可
