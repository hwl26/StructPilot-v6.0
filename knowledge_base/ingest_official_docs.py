"""B 阶段官方文档集成 — 摄取脚本（一次性，可重跑幂等）。

将预抓取的 cryoSPARC / RELION 官方文档以 KnowledgeDoc 形态写入
knowledge_base/knowledge_index.json，使 retriever（build_corpus →
load_knowledge_index）自动将其纳入 RAG 语料。无 API Key 时 retriever
走 _lexical_search（纯关键词），官方文档即可被检索并出现在"参考来源"。

设计要点：
- doc_id 含 "[官方文档]" 前缀 + 页面名 + 原文 URL，既作为 RAG 标识，
  也作为用户可见的引用标签（app.py 的 cite_text 直接使用 doc_id）。
- 额外字段 source_url 被 doc_to_text 忽略，仅用于占位区展示原文链接。
- tier="sop"（权重 0.95，低于内置 checkpoint 的 1.0，高于 note 0.7），
  保证官方文档补充而非淹没内置 SOP。
- checkpoint_id 映射到项目 12 步工作流（cp_01..cp_12）；跨步页面用 tags 补充。
"""

from __future__ import annotations

import json
import os
from datetime import datetime

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KB = os.path.join(_BASE, "knowledge_base")
_INDEX = os.path.join(_KB, "knowledge_index.json")
_REGISTRY = os.path.join(_KB, "sources", "source_registry.json")
_DOCS_DIR = os.path.join(_KB, "docs")

RELION_BASE = "https://relion.readthedocs.io/en/release-5.0/SPA_tutorial"

# 每个条目即一个 KnowledgeDoc（dict）。doc_to_text 使用
# title_cn / summary / action_steps / qc_checks / common_errors。
OFFICIAL_DOCS = [
    {
        "doc_id": f"[官方文档] RELION-SPA·Introduction ({RELION_BASE}/Introduction.html)",
        "software": "relion",
        "checkpoint_id": "cp_01",
        "title_cn": "RELION 5.0 SPA 教程概览与数据导入",
        "title_en": "RELION SPA Tutorial — Introduction",
        "summary": (
            "RELION 5.0 单颗粒分析全流程教程，覆盖 beam-induced motion correction、"
            "CTF estimation、自动颗粒挑选、颗粒提取、2D 类平均、VDAM 初始模型、3D 分类、"
            "高分辨率 3D 精修（含 Blush 正则化）、CTF 精修与高阶像差校正、Bayesian polishing、"
            "map 锐化与局部分辨率估计、ModelAngelo 自动建模、DynaMight 柔性分析。"
            "使用 beta-galactosidase 测试数据（JEOL CRYO ARM 200），约一天可走完。"
        ),
        "action_steps": [
            "启动 RELION GUI 并进入 project directory",
            "下载并解压教程测试数据 relion30_tutorial_data.tar 与 relion50_tutorial_precalculated_results.tar.gz",
            "完整数据集可在 EMPIAR-10204 获取",
            "遇到问题先读 RELION Wiki FAQ 与 CCPEM 邮件列表，再考虑提问",
        ],
        "qc_checks": [
            "确认数据已正确解压且 project directory 可写",
            "确认显微镜参数与数据匹配（本教程为 200kV JEOL CRYO ARM）",
        ],
        "common_errors": [
            "不要直接邮件联系作者，先查 FAQ / CCPEM 列表",
            "确保使用正确的 pixel size 与加速电压参数",
        ],
        "tags": ["official_doc", "relion", "cp_01", "introduction", "setup"],
        "tier": "sop",
        "status": "formal_ready",
        "source": "official_doc_relion",
        "source_url": f"{RELION_BASE}/Introduction.html",
        "imported_at": "",
    },
    {
        "doc_id": f"[官方文档] RELION-SPA·Preprocessing ({RELION_BASE}/Preprocessing.html)",
        "software": "relion",
        "checkpoint_id": "cp_02",
        "title_cn": "RELION 预处理：运动校正(MotionCorr)与CTF估计(CtfFind)",
        "title_en": "RELION SPA Tutorial — Preprocessing",
        "summary": (
            "从 Import 原始电影到 beam-induced motion correction（MotionCorr job）与 "
            "CTF estimation（CtfFind job）。导入 Movies/*.tiff 后，用 RELION 自身 motioncor2 "
            "实现做运动校正并输出功率谱，再调用 ctffind 4.1 估计 CTF 参数。"
        ),
        "action_steps": [
            "Import：Movies tab 设 Raw input files: Movies/*.tiff，Are these multi-frame movies?: Yes，Pixel size: 0.885",
            "MotionCorr：Input movies STAR: Import/job001/movies.star，First/Last frame: 1/-1，Dose per frame: 1.277，Save sum of power spectra: Yes",
            "MotionCorr Motion tab：Bfactor: 150，Number of patches X,Y: 5 5，Gain-reference: Movies/gain.mrc，Use RELION's own implementation?: Yes",
            "CtfFind：Input micrographs STAR: Motioncorr/job002/corrected_micrographs.star，Amount of astigmatism: 100",
            "CtfFind CTFFIND-4.1 tab：Use power spectra from MotionCorr?: Yes，FFT box size: 512，Min/Max defocus: 5000/50000",
            "Display 查看 Thon 环质控；不满意可删 .log 后 Continue! 重跑",
        ],
        "qc_checks": [
            "Display 选 out: micrographs_ctf.star 查看 Thon 环确认 CTF 拟合质量",
            "CTF 拟合差可删 .log 重跑或 Subset selection 舍弃",
        ],
        "common_errors": [
            "Symbolic links 必须用 absolute path，relative path 致后续错误",
            "Write output in float16?: Yes 省磁盘但 Gctf 不兼容且 UCSF MotionCor2 不支持；CTF 需用 CTFFIND-4.1",
            "RELION 5.0 已移除 GCTF 支持，仅 ctffind 4.1 开源且可读 MotionCorr 功率谱",
        ],
        "tags": ["official_doc", "relion", "cp_02", "cp_03", "preprocessing", "motioncorrection", "ctf"],
        "tier": "sop",
        "status": "formal_ready",
        "source": "official_doc_relion",
        "source_url": f"{RELION_BASE}/Preprocessing.html",
        "imported_at": "",
    },
    {
        "doc_id": f"[官方文档] RELION-SPA·Autopicking ({RELION_BASE}/Autopicking.html)",
        "software": "relion",
        "checkpoint_id": "cp_04",
        "title_cn": "RELION 颗粒挑选(AutoPick)与提取(Extract)",
        "title_en": "RELION SPA Tutorial — Autopicking",
        "summary": (
            "从微图中进行颗粒挑选与提取：先选微图子集，用 LoG 滤波自动挑初选颗粒，提取后做 2D 分类并用"
            "自动化神经网络选优类，再用其重训 Topaz 并全图挑选，最后按 FOM 阈值提取颗粒，形成后续处理用的初始数据集。"
        ),
        "action_steps": [
            "Subset selection：选 micrographs_split1.star（10 张微图）供训练",
            "AutoPick(LoG)：Min/Max diameter 150/180 A 挑初选坐标",
            "Extract：Particle box size 256 pix，Rescale 至 64 pix",
            "Class2D：2D classification 得类平均，Subset selection 自动选类(auto-select)",
            "AutoPick(Topaz)：先训练 model_epoch10.sav，再全图 picking，particle diameter 180 A",
            "Extract：按 AutoPick/job011/autopick.star 提取，Use autopick FOM threshold，Minimum -3",
        ],
        "qc_checks": [
            "提取前确认 autopick.star 覆盖所需微图",
            "坐标缺失微图会 GUI 红警",
        ],
        "common_errors": [
            "Topaz training 须单 MPI process，不并行；picking 可多 MPI",
            "float16 输出省空间，但非 RELION/CCPEM 程序可能不兼容",
        ],
        "tags": ["official_doc", "relion", "cp_04", "cp_05", "autopick", "extract", "topaz", "log"],
        "tier": "sop",
        "status": "formal_ready",
        "source": "official_doc_relion",
        "source_url": f"{RELION_BASE}/Autopicking.html",
        "imported_at": "",
    },
    {
        "doc_id": f"[官方文档] RELION-SPA·Class2D ({RELION_BASE}/Class2D.html)",
        "software": "relion",
        "checkpoint_id": "cp_06",
        "title_cn": "RELION 2D 分类(Class2D)与优类筛选",
        "title_en": "RELION SPA Tutorial — Class2D",
        "summary": (
            "参考自由 2D 类平均，用于剔除坏颗粒。坏颗粒平均差会落入小类，剔除即数据清洗。"
            "使用 VDAM 算法（relion-4.0 引入）比 EM 更快且类平均更好。"
        ),
        "action_steps": [
            "I/O tab：Input images STAR: Extract/job012/particles.star",
            "Optimisation tab：Number of classes: 100，Regularisation parameter T: 2",
            "Use EM algorithm?: No，Use VDAM algorithm?: Yes，Number of VDAM mini-batches: 100",
            "Mask diameter (A): 200，Mask individual particles with zeros?: Yes",
            "Center class averages?: Yes",
            "Compute tab：Use GPU acceleration?: Yes；Running tab：Number of MPI procs: 1，threads: 12",
            "Subset selection (Select/job014)：Automatically select 2D classes?: Yes，Minimum threshold: 0.1",
        ],
        "qc_checks": [
            "类平均应像低通滤波原子模型投影，溶剂区应平坦",
            "溶剂区径向条纹是过拟合典型信号，可限制 E-step 分辨率(10-15A)",
        ],
        "common_errors": [
            "类平均过噪→降低 T；分辨率不足→提高 T",
            "VDAM 算法不能 MPI 并行，须单 MPI",
            "2D 分类与 Subset selection 可重复多次，但勿丢弃少数视角",
        ],
        "tags": ["official_doc", "relion", "cp_06", "class2d", "classification", "vdam"],
        "tier": "sop",
        "status": "formal_ready",
        "source": "official_doc_relion",
        "source_url": f"{RELION_BASE}/Class2D.html",
        "imported_at": "",
    },
    {
        "doc_id": f"[官方文档] RELION-SPA·InitialModel ({RELION_BASE}/InitialModel.html)",
        "software": "relion",
        "checkpoint_id": "cp_07",
        "title_cn": "RELION 初始模型生成(InitialModel/Ab-initio)",
        "title_en": "RELION SPA Tutorial — InitialModel",
        "summary": (
            "relion-4.0 用梯度驱动算法从 2D 颗粒生成 de novo 3D 初始参考（不同于 CryoSPARC 的 SGD）。"
            "需合理视角分布与良好 2D 类平均，产出可用于 3D 分类或 3D auto-refine 的低分辨率模型。"
        ),
        "action_steps": [
            "I/O tab：Select/job014/particles.star",
            "Optimisation tab：Number of VDAM mini-batches: 100，Regularisation parameter T: 4，Number of classes: 1，Mask diameter (A): 200",
            "Flatten and enforce non-negative solvent?: Yes，Symmetry: D2，Run in C1 and apply symmetry later?: Yes",
            "Compute tab：Use GPU acceleration?: Yes；Running tab：Number of MPI procs: 1，threads: 12",
            "Display 查看 InitialModel/job015/initial_model.mrc 评估伪影",
        ],
        "qc_checks": [
            "在 2D slices 中查看 3D map 评估伪影（如溶剂区条纹）",
            "可用 UCSF chimera 在 3D 查看",
        ],
        "common_errors": [
            "梯度驱动算法不能多 MPI 并行",
            "C1 运行再后续应用对称性收敛更好",
            "均匀数据集单类(class=1)即可",
        ],
        "tags": ["official_doc", "relion", "cp_07", "initialmodel", "abinitio", "vdam"],
        "tier": "sop",
        "status": "formal_ready",
        "source": "official_doc_relion",
        "source_url": f"{RELION_BASE}/InitialModel.html",
        "imported_at": "",
    },
    {
        "doc_id": f"[官方文档] RELION-SPA·Class3D ({RELION_BASE}/Class3D.html)",
        "software": "relion",
        "checkpoint_id": "cp_08",
        "title_cn": "RELION 3D 分类(Class3D)",
        "title_en": "RELION SPA Tutorial — Class3D",
        "summary": (
            "无监督 3D 分类，relion 的 3D multi-reference refinement 提供强大异质性分析。"
            "从 3D classification job-type 运行，可对数据集分亚组描述变异性。"
        ),
        "action_steps": [
            "I/O tab：Input images STAR: Select/job014/particles.star，Reference map: InitialModel/job015/initial_model.mrc",
            "Reference tab：Ref. map is on absolute greyscale?: Yes，Initial low-pass filter (A): 50，Symmetry: C1",
            "CTF tab：Do CTF correction?: Yes，Ignore CTFs until first peak?: No",
            "Optimisation tab：Number of classes: 4，Regularisation parameter T: 4，Number of iterations: 25，Mask diameter (A): 200，Mask individual particles with zeros?: Yes，Limit resolution E-step to (A): -1，Use Blush regularisation?: Yes",
            "Sampling tab 通常不改；Compute tab：Use GPU acceleration?: Yes；Running tab：Number of MPI procs: 5，threads: 6",
            "Subset selection：Automatically select 2D classes?: No，手动选优类丢弃亚优类",
        ],
        "qc_checks": [
            "在 2D slices 查看类重建评估未解异质性（模糊/条纹区）",
            "用 relion_star_printtable 查看 rlnResolution/rlnSsnrMap",
            "grep _rlnChangesOptimalClasses 检查收敛",
        ],
        "common_errors": [
            "类平均过噪→降低 T；分辨率不足→提高 T",
            "初始分类常用 C1 无对称以分离坏颗粒并验证对称性",
            "Blush regularisation 需 relion-5 conda + CUDA GPU，否则设 No",
            "3D 分类计算更耗内存，常用更多 threads",
        ],
        "tags": ["official_doc", "relion", "cp_08", "class3d", "classification", "blush"],
        "tier": "sop",
        "status": "formal_ready",
        "source": "official_doc_relion",
        "source_url": f"{RELION_BASE}/Class3D.html",
        "imported_at": "",
    },
    {
        "doc_id": f"[官方文档] RELION-SPA·Refine3D ({RELION_BASE}/Refine3D.html)",
        "software": "relion",
        "checkpoint_id": "cp_09",
        "title_cn": "RELION 高分辨率 3D 精修(Refine3D)",
        "title_en": "RELION SPA Tutorial — Refine3D",
        "summary": (
            "同质性子集选定后，用 3D auto-refine 全自动高分辨率精修。采用 gold-standard FSC"
            "（独立半集）估计分辨率避免自增强过拟合，并自动判断收敛，几乎无需调参。"
        ),
        "action_steps": [
            "先重新提取粒子（更少下采样）：Particle extraction，OR re-extract refined particles?: Yes，Particle box size: 360，Rescale: Yes，Re-scaled size: 256（→1.244 Å，限分辨率~2.5Å）",
            "I/O tab：Input images STAR: Extract/job018/particles.star，Reference map: 缩放至256盒的 class map",
            "Reference tab：Ref. map is on absolute greyscale?: No，Initial low-pass filter (A): 50，Symmetry: D2",
            "Optimisation/CTF tab 同 Class3D；Auto-sampling tab：Use finer angular sampling faster?: Yes",
            "Compute tab：Use parallel disc I/O?: Yes，Skip padding?: Yes（省内存但小心混叠），Pre-read all particles into RAM?: Yes，Use GPU acceleration?: Yes；Running tab：Number of MPI procs: 5（奇数，最小3），threads: 6",
        ],
        "qc_checks": [
            "收敛时最后迭代分辨率显著提升（两半集合并）",
            "grep Auto Refine3D/job019/run.out 查看采样与分辨率估计",
            "odd MPI 数最高效（1 master + 2 half-set worker sets）",
        ],
        "common_errors": [
            "Skip padding?: Yes 省内存但 box 紧时边缘可能混叠",
            "高对称精修才用 3.7° 采样+0.9° 局部搜索，其余默认 7.5°/1.8°",
            "大 box 末迭代内存显著增加",
        ],
        "tags": ["official_doc", "relion", "cp_09", "refine3d", "autorefine", "goldstandard"],
        "tier": "sop",
        "status": "formal_ready",
        "source": "official_doc_relion",
        "source_url": f"{RELION_BASE}/Refine3D.html",
        "imported_at": "",
    },
    {
        "doc_id": f"[官方文档] RELION-SPA·Mask ({RELION_BASE}/Mask.html)",
        "software": "relion",
        "checkpoint_id": "cp_11",
        "title_cn": "RELION 溶剂掩膜创建(MaskCreate)与后处理锐化(PostProcess)",
        "title_en": "RELION SPA Tutorial — Mask",
        "summary": (
            "3D auto-refine 后需锐化 map。gold-standard FSC 在精修中仅用未掩膜 map（除非用 solvent-flattened FSCs），"
            "导致分辨率被溶剂区噪声低估。先做掩膜定义蛋白/溶剂边界，再做 post-processing（B-factor 锐化 + 计算 masked FSC）。"
        ),
        "action_steps": [
            "Mask Creation：I/O 选 Refine3D/job019/run_class001.mrc",
            "Mask tab：Lowpass filter map (A): 15，Pixel size (A): -1（自动从header），Initial binarisation threshold: 0.01，Extend binary map: 3 px，Add soft-edge: 8 px",
            "Post-processing：I/O 选一半未滤波 half-map + Solvent mask + Calibrated pixel size: 1.244",
            "Sharpen tab：Estimate B-factor automatically?: Yes，Lowest resolution for auto-B fit (A): 10",
            "MTF of detector: mtf_k2_200kV.star，Original detector pixel size: 0.885",
        ],
        "qc_checks": [
            "PostProcess 后查看 FSC 曲线与 Guinier 图",
            "phase-randomized FSC（红曲线）在估计分辨率处应≈0；否则掩膜过锐",
            "掩膜应包裹整个结构但不含过多溶剂",
        ],
        "common_errors": [
            "掩膜过锐或细节过多→FSC 红曲线不归零，需更强低通/更软更宽掩膜后重做",
            "像素尺寸若偏差几个百分点，在 PostProcess 提供正确 Calibrated pixel size 即可，无需重精修",
            "掩膜 soft-edge 余弦过渡很重要，过锐对 FSC 校正敏感",
        ],
        "tags": ["official_doc", "relion", "cp_11", "mask", "postprocess", "sharpen", "bfactor"],
        "tier": "sop",
        "status": "formal_ready",
        "source": "official_doc_relion",
        "source_url": f"{RELION_BASE}/Mask.html",
        "imported_at": "",
    },
    {
        "doc_id": f"[官方文档] RELION-SPA·CtfRefine ({RELION_BASE}/CtfRefine.html)",
        "software": "relion",
        "checkpoint_id": "cp_10",
        "title_cn": "RELION CTF 与像差精修(CtfRefine)",
        "title_en": "RELION SPA Tutorial — CtfRefine",
        "summary": (
            "用 CTF refinement job-type 估计数据集中的对称/非对称像差、各向异性放大、并重新估计每颗粒 defocus。"
            "可从 3D auto-refine 与对应 Post-processing 运行，以较小计算成本进一步提升分辨率。"
        ),
        "action_steps": [
            "高阶像差：I/O 选 Refine3D particles + Postprocess STAR；Fit tab：Estimate beamtilt?: Yes，Also estimate trefoil?: Yes，estimate 4th order aberrations?: Yes，Minimum resolution for fits (A): 30",
            "各向异性放大：Estimate anisotropic magnification?: Yes（禁用其他选项），Minimum resolution: 30",
            "每颗粒 defocus：Perform CTF parameter fitting?: Yes，Fit defocus?: Per-particle，Fit astigmatism?: Per-micrograph，Fit B-factor/phase-shift/beamtilt/4th: No，Minimum resolution: 30",
            "建议重跑 3D auto-refine + Post-processing 确认改进",
        ],
        "qc_checks": [
            "查看 logfile.pdf 分析像差（beamtilt 非对称图蓝红不对称，trefoil 3-fold，tetrafoil 4-fold）",
            "各向异性查看 optics 表 _rlnMagMat 接近单位矩阵",
            "每颗粒 defocus 按微图着色查看倾斜冰层",
        ],
        "common_errors": [
            "先估计最大误差源（一般先 beamtilt）",
            "各向异性放大与像差同时精修不稳定，须分开",
            "per-particle defocus 需参考分辨率远超 4 Å 才稳定",
            "建议迭代：CTF 精修后可再 Bayesian polishing，反之亦可",
        ],
        "tags": ["official_doc", "relion", "cp_10", "cp_09", "ctfrefine", "aberration", "beamtilt", "defocus"],
        "tier": "sop",
        "status": "formal_ready",
        "source": "official_doc_relion",
        "source_url": f"{RELION_BASE}/CtfRefine.html",
        "imported_at": "",
    },
    {
        "doc_id": f"[官方文档] RELION-SPA·Polish ({RELION_BASE}/Polish.html)",
        "software": "relion",
        "checkpoint_id": "cp_09",
        "title_cn": "RELION Bayesian polishing（贝叶斯抛光）",
        "title_en": "RELION SPA Tutorial — Polish",
        "summary": (
            "relion 实现基于参考的每颗粒 beam-induced motion 校正的贝叶斯方法，优化正则化似然，"
            "对每颗粒轨迹关联平滑时空运动的先验。先训练模式估计最优先验参数，再抛光模式拟合所有颗粒运动并产生加权平均。"
        ),
        "action_steps": [
            "训练模式：I/O 选 MotionCorr corrected micrographs + Refine3D/CtfRefine particles + Postprocess STAR；First/Last frame: 1/-1",
            "Train tab：Train optimal parameters?: Yes，Fraction of Fourier pixels for testing: 0.5，Use this many particles: 3000；Perform particle polishing?: No（单 MPI）",
            "抛光模式：Perform particle polishing?: Yes，Optimised parameter file 或 OR use your own parameters?: Yes",
            "自带参数（示例）：Sigma for velocity: 0.45，Sigma for divergence: 1290，Sigma for acceleration: 2.66，Min/Max resolution for B-factor fit: 20/-1",
            "抛光后重跑 3D auto-refine（shiny.star）+ Post-processing",
        ],
        "qc_checks": [
            "polish 输出 shiny.star 与 PDF logfile（scale/B-factor 图、颗粒轨迹）",
            "重跑精修+后处理确认分辨率提升（示例达 2.9 Å）",
            "提供 half-map 作参考可防过拟合，Initial low-pass: 8，Use solvent-flattened FSCs?: Yes",
        ],
        "common_errors": [
            "Bayesian polishing 不推荐丢弃首/末帧（B-factor 自动优化 SNR）",
            "训练未 MPI 并行，须单 MPI；默认参数 σvel=0.2;σdiv=5000;σacc=2 常可直接用",
            "训练结果有时不稳定（多次运行 sigma 差异大），但抛光实际分辨率常不敏感",
            "CTF 精修与 polishing 顺序可互换，先处理最大问题",
        ],
        "tags": ["official_doc", "relion", "cp_09", "cp_11", "polish", "bayesian", "motion"],
        "tier": "sop",
        "status": "formal_ready",
        "source": "official_doc_relion",
        "source_url": f"{RELION_BASE}/Polish.html",
        "imported_at": "",
    },
    {
        "doc_id": f"[官方文档] RELION-SPA·Validation ({RELION_BASE}/Validation.html)",
        "software": "relion",
        "checkpoint_id": "cp_12",
        "title_cn": "RELION 局部分辨率估计(LocalRes)与手性验证",
        "title_en": "RELION SPA Tutorial — Validation",
        "summary": (
            "post-processing 的分辨率是全局估计，无法描述复合体内部常见分辨率的局域变化。"
            "relion 通过 Local resolution job-type 包装 Kucukelbir/Tagare 程序估计局部分辨率，"
            "也可选 relion 自身实现（移动软球掩膜）。"
        ),
        "action_steps": [
            "Local resolution：I/O 选一半未滤波 half-map + User-provided solvent mask + Calibrated pixel size: 1.244",
            "Relion tab：Use Relion?: Yes，User-provided B-factor: -30，MTF of detector: mtf_k2_200kv.star",
            "输出 relion_locres.mrc 可在 UCSF chimera 按局部分辨率着色",
            "检查手性：α-helix 转向错误提示手性反了；SGD 初始模型有 50% 概率反手",
            "命令行翻转手性：relion_image_handler --i postprocess.mrc --o ..._invert.mrc --invert_hand",
        ],
        "qc_checks": [
            "局部分辨率图描述整体 map 质量变化",
            "正确手性后叠加原子模型（如 PDB 5a1a β-galactosidase）验证",
            "8 MPI 运行约 7 分钟",
        ],
        "common_errors": [
            "绝对手性无法从数据确定（除非倾斜样品台）",
            "像素尺寸偏差几个百分点在 LocalRes 提供正确值即可，无需重精修",
            "偏振随机化 FSC 红曲线应≈0",
        ],
        "tags": ["official_doc", "relion", "cp_12", "validation", "localres", "resolution", "handedness"],
        "tier": "sop",
        "status": "formal_ready",
        "source": "official_doc_relion",
        "source_url": f"{RELION_BASE}/Validation.html",
        "imported_at": "",
    },
    {
        "doc_id": f"[官方文档] RELION-SPA·WrappingUp ({RELION_BASE}/WrappingUp.html)",
        "software": "relion",
        "checkpoint_id": "cp_12",
        "title_cn": "RELION 收尾：目录清理、引用与延伸阅读",
        "title_en": "RELION SPA Tutorial — WrappingUp",
        "summary": (
            "教程结束。relion 提供清理 job 目录选项节省磁盘（gentle/harsh 两种模式）。"
            "鼓励引用论文与查阅 FAQ/CCPEM。本教程未覆盖 multi-body refinement。"
        ),
        "action_steps": [
            "Gentle cleaning：仅删中间迭代文件；Harsh cleaning：也删启动新 job 所需文件（如 MotionCorr 平均微图、提取颗粒栈）",
            "可从 Job actions 清理单个 job，或从 GUI 顶部 Jobs 菜单 Gently clean all jobs",
            "长期存储前 gently clean project directory",
            "有问题先查 relion Wiki FAQ 与 CCPEM 邮件列表",
            "引用 Scheres 2012/2016 等相关论文",
        ],
        "qc_checks": [
            "清理前确认不再需要中间文件",
            "导出前确保最终 postprocess.mrc 与 half-maps 保留",
        ],
        "common_errors": [
            "harsh cleaning 会删除重跑所需输入，谨慎使用",
            "multi-body refinement 不在本教程范围，见 RELION Wiki",
        ],
        "tags": ["official_doc", "relion", "cp_12", "wrappingup", "export", "cleanup"],
        "tier": "sop",
        "status": "formal_ready",
        "source": "official_doc_relion",
        "source_url": f"{RELION_BASE}/WrappingUp.html",
        "imported_at": "",
    },
    {
        "doc_id": "[官方文档] cryoSPARC·User Management (https://guide.cryosparc.com/setup-configuration-and-management/software-system-guides/tutorial-user-management)",
        "software": "cryosparc",
        "checkpoint_id": "",
        "title_cn": "cryoSPARC 用户管理(User Management)官方教程",
        "title_en": "CryoSPARC Guide — User Management",
        "summary": (
            "通过 cryoSPARC 用户界面创建用户、管理角色与密码重置。适用于 CryoSPARC ≤v3.3；"
            "v4.0+ 见 Admin Panel。v2.12+ 提供 UI 用户管理工具，管理员可创建用户、提升/降级角色、"
            "用户通过 UI 重置密码。"
        ),
        "action_steps": [
            "创建用户：点击用户名→Admin 进入用户管理页（须 admin）；填写 Add a New User 表单（email+username+姓名）；新用户出现在表中，Tokens 列点击 4 位注册 token 复制发送",
            "新用户用登录页 New Account 链接，输入 email+token+新密码完成注册并自动登录",
            "改角色：Admin 页 Role 列点击用户角色确认，非 admin→提升为 admin，admin→转为普通用户",
            "重置密码：登录页 Reset Password→选 I need a reset token 输入 email；admin 在用户管理页获取 4 位 reset token 发给用户；用户用 I have a reset token 填 email+token+新密码登录",
        ],
        "qc_checks": [
            "安装时第一个通过 CLI 创建的用户为 admin",
            "Structura Biotechnology 无法重置密码，仅本地 admin 可重置",
            "reset token 须安全传达给用户",
        ],
        "common_errors": [
            "v4.0+ 用户管理移至 Admin Panel，旧教程仅适用于 ≤v3.3",
            "非 admin 用户无法访问用户管理页",
            "密码重置须通过 admin 获取的 reset token，非命令行",
        ],
        "tags": ["official_doc", "cryosparc", "user_management", "admin", "license", "password"],
        "tier": "sop",
        "status": "formal_ready",
        "source": "official_doc_cryosparc",
        "source_url": "https://guide.cryosparc.com/setup-configuration-and-management/software-system-guides/tutorial-user-management",
        "imported_at": "",
    },
]


def _stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _invalidate_retriever_caches() -> list:
    """删除 retriever 的语料/向量缓存，迫使下次检索重建（含新增官方文档）。

    retriever.build_corpus 会优先读 config/corpus_cache.json；若不失效，
    本次新增的官方文档不会被纳入 RAG 语料。embeddings_cache.json 一并清理，
    避免有 Key 模式下旧向量掩盖新文档。
    """
    config_dir = os.path.join(_BASE, "config")
    cleared = []
    for name in ("corpus_cache.json", "embeddings_cache.json"):
        path = os.path.join(config_dir, name)
        if os.path.exists(path):
            try:
                os.remove(path)
                cleared.append(name)
            except Exception:
                pass
    return cleared


def ingest() -> dict:
    """Append OFFICIAL_DOCS into knowledge_index.json (idempotent)."""
    os.makedirs(_DOCS_DIR, exist_ok=True)

    # --- knowledge_index.json ---
    existing: list = []
    if os.path.exists(_INDEX):
        try:
            existing = json.load(open(_INDEX, encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []
    existing_ids = {d.get("doc_id") for d in existing if isinstance(d, dict)}
    added = 0
    for doc in OFFICIAL_DOCS:
        if doc["doc_id"] in existing_ids:
            continue
        doc = dict(doc)
        doc["imported_at"] = _stamp()
        existing.append(doc)
        existing_ids.add(doc["doc_id"])
        added += 1
    with open(_INDEX, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    # --- source_registry.json ---
    registry = {"schema_version": "1.0", "sources": []}
    if os.path.exists(_REGISTRY):
        try:
            registry = json.load(open(_REGISTRY, encoding="utf-8"))
            if not isinstance(registry, dict):
                registry = {"schema_version": "1.0", "sources": []}
        except Exception:
            registry = {"schema_version": "1.0", "sources": []}
    sources = registry.setdefault("sources", [])
    source_ids = {s.get("source_id") for s in sources if isinstance(s, dict)}
    relion_src = {
        "source_id": "relion_spa_tutorial",
        "name": "RELION 5.0 Single Particle Analysis Tutorial",
        "url": f"{RELION_BASE}/index.html",
        "vendor": "relion",
        "doc_count": sum(1 for d in OFFICIAL_DOCS if d["software"] == "relion"),
        "license_note": "官方 Guide 精选摘要，用户点击原文链接跳转查看完整内容（合法引用，非全文复制）",
        "ingested_at": _stamp(),
    }
    cryo_src = {
        "source_id": "cryosparc_user_management",
        "name": "CryoSPARC Guide — User Management",
        "url": "https://guide.cryosparc.com/setup-configuration-and-management/software-system-guides/tutorial-user-management",
        "vendor": "cryosparc",
        "doc_count": sum(1 for d in OFFICIAL_DOCS if d["software"] == "cryosparc"),
        "license_note": "官方 Guide 精选摘要，合法引用",
        "ingested_at": _stamp(),
    }
    for src in (relion_src, cryo_src):
        if src["source_id"] not in source_ids:
            sources.append(src)
    with open(_REGISTRY, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)

    # --- raw markdown audit files ---
    relion_dir = os.path.join(_DOCS_DIR, "relion_spa")
    cryo_dir = os.path.join(_DOCS_DIR, "cryosparc")
    os.makedirs(relion_dir, exist_ok=True)
    os.makedirs(cryo_dir, exist_ok=True)
    for doc in OFFICIAL_DOCS:
        target = relion_dir if doc["software"] == "relion" else cryo_dir
        safe = doc["doc_id"].split("·")[-1].split("(")[0].strip().replace("/", "_")
        md_path = os.path.join(target, f"{safe}.md")
        md = (
            f"# {doc['title_cn']}\n\n"
            f"> 官方来源：{doc['source_url']}\n\n"
            f"**摘要**：{doc['summary']}\n\n"
            f"**关键步骤**：\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(doc["action_steps"], 1)) + "\n\n"
            f"**质控要点**：\n" + "\n".join(f"- {s}" for s in doc["qc_checks"]) + "\n\n"
            f"**注意事项**：\n" + "\n".join(f"- {s}" for s in doc["common_errors"]) + "\n"
        )
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)

    # --- 失效 retriever 缓存，确保新增官方文档进入下次检索语料 ---
    cleared = _invalidate_retriever_caches()

    return {
        "added_to_index": added,
        "total_in_index": len(existing),
        "official_doc_count": len(OFFICIAL_DOCS),
        "registry_sources": [s.get("source_id") for s in sources],
        "caches_cleared": cleared,
        "docs_dir": _DOCS_DIR,
    }


if __name__ == "__main__":
    result = ingest()
    print(json.dumps(result, ensure_ascii=False, indent=2))
