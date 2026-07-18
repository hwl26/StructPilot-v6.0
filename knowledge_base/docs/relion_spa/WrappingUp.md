# RELION 收尾：目录清理、引用与延伸阅读

> 官方来源：https://relion.readthedocs.io/en/release-5.0/SPA_tutorial/WrappingUp.html

**摘要**：教程结束。relion 提供清理 job 目录选项节省磁盘（gentle/harsh 两种模式）。鼓励引用论文与查阅 FAQ/CCPEM。本教程未覆盖 multi-body refinement。

**关键步骤**：
1. Gentle cleaning：仅删中间迭代文件；Harsh cleaning：也删启动新 job 所需文件（如 MotionCorr 平均微图、提取颗粒栈）
2. 可从 Job actions 清理单个 job，或从 GUI 顶部 Jobs 菜单 Gently clean all jobs
3. 长期存储前 gently clean project directory
4. 有问题先查 relion Wiki FAQ 与 CCPEM 邮件列表
5. 引用 Scheres 2012/2016 等相关论文

**质控要点**：
- 清理前确认不再需要中间文件
- 导出前确保最终 postprocess.mrc 与 half-maps 保留

**注意事项**：
- harsh cleaning 会删除重跑所需输入，谨慎使用
- multi-body refinement 不在本教程范围，见 RELION Wiki
