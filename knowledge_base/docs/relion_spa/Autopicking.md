# RELION 颗粒挑选(AutoPick)与提取(Extract)

> 官方来源：https://relion.readthedocs.io/en/release-5.0/SPA_tutorial/Autopicking.html

**摘要**：从微图中进行颗粒挑选与提取：先选微图子集，用 LoG 滤波自动挑初选颗粒，提取后做 2D 分类并用自动化神经网络选优类，再用其重训 Topaz 并全图挑选，最后按 FOM 阈值提取颗粒，形成后续处理用的初始数据集。

**关键步骤**：
1. Subset selection：选 micrographs_split1.star（10 张微图）供训练
2. AutoPick(LoG)：Min/Max diameter 150/180 A 挑初选坐标
3. Extract：Particle box size 256 pix，Rescale 至 64 pix
4. Class2D：2D classification 得类平均，Subset selection 自动选类(auto-select)
5. AutoPick(Topaz)：先训练 model_epoch10.sav，再全图 picking，particle diameter 180 A
6. Extract：按 AutoPick/job011/autopick.star 提取，Use autopick FOM threshold，Minimum -3

**质控要点**：
- 提取前确认 autopick.star 覆盖所需微图
- 坐标缺失微图会 GUI 红警

**注意事项**：
- Topaz training 须单 MPI process，不并行；picking 可多 MPI
- float16 输出省空间，但非 RELION/CCPEM 程序可能不兼容
