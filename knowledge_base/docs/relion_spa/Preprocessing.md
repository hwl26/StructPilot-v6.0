# RELION 预处理：运动校正(MotionCorr)与CTF估计(CtfFind)

> 官方来源：https://relion.readthedocs.io/en/release-5.0/SPA_tutorial/Preprocessing.html

**摘要**：从 Import 原始电影到 beam-induced motion correction（MotionCorr job）与 CTF estimation（CtfFind job）。导入 Movies/*.tiff 后，用 RELION 自身 motioncor2 实现做运动校正并输出功率谱，再调用 ctffind 4.1 估计 CTF 参数。

**关键步骤**：
1. Import：Movies tab 设 Raw input files: Movies/*.tiff，Are these multi-frame movies?: Yes，Pixel size: 0.885
2. MotionCorr：Input movies STAR: Import/job001/movies.star，First/Last frame: 1/-1，Dose per frame: 1.277，Save sum of power spectra: Yes
3. MotionCorr Motion tab：Bfactor: 150，Number of patches X,Y: 5 5，Gain-reference: Movies/gain.mrc，Use RELION's own implementation?: Yes
4. CtfFind：Input micrographs STAR: Motioncorr/job002/corrected_micrographs.star，Amount of astigmatism: 100
5. CtfFind CTFFIND-4.1 tab：Use power spectra from MotionCorr?: Yes，FFT box size: 512，Min/Max defocus: 5000/50000
6. Display 查看 Thon 环质控；不满意可删 .log 后 Continue! 重跑

**质控要点**：
- Display 选 out: micrographs_ctf.star 查看 Thon 环确认 CTF 拟合质量
- CTF 拟合差可删 .log 重跑或 Subset selection 舍弃

**注意事项**：
- Symbolic links 必须用 absolute path，relative path 致后续错误
- Write output in float16?: Yes 省磁盘但 Gctf 不兼容且 UCSF MotionCor2 不支持；CTF 需用 CTFFIND-4.1
- RELION 5.0 已移除 GCTF 支持，仅 ctffind 4.1 开源且可读 MotionCorr 功率谱
