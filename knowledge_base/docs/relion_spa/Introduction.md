# RELION 5.0 SPA 教程概览与数据导入

> 官方来源：https://relion.readthedocs.io/en/release-5.0/SPA_tutorial/Introduction.html

**摘要**：RELION 5.0 单颗粒分析全流程教程，覆盖 beam-induced motion correction、CTF estimation、自动颗粒挑选、颗粒提取、2D 类平均、VDAM 初始模型、3D 分类、高分辨率 3D 精修（含 Blush 正则化）、CTF 精修与高阶像差校正、Bayesian polishing、map 锐化与局部分辨率估计、ModelAngelo 自动建模、DynaMight 柔性分析。使用 beta-galactosidase 测试数据（JEOL CRYO ARM 200），约一天可走完。

**关键步骤**：
1. 启动 RELION GUI 并进入 project directory
2. 下载并解压教程测试数据 relion30_tutorial_data.tar 与 relion50_tutorial_precalculated_results.tar.gz
3. 完整数据集可在 EMPIAR-10204 获取
4. 遇到问题先读 RELION Wiki FAQ 与 CCPEM 邮件列表，再考虑提问

**质控要点**：
- 确认数据已正确解压且 project directory 可写
- 确认显微镜参数与数据匹配（本教程为 200kV JEOL CRYO ARM）

**注意事项**：
- 不要直接邮件联系作者，先查 FAQ / CCPEM 列表
- 确保使用正确的 pixel size 与加速电压参数
