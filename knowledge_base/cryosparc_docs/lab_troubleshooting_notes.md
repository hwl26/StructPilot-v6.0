# 实验室故障排查记录

> **来源**: 实验室 cryoSPARC 运维经验、Excel + 白板中的备注
> **定位**: 真实生产环境中遇到的具体问题和解决方案

---

## 故障索引

| 编号 | 阶段 | 严重度 | 现象 | 一句话原因 |
|------|------|--------|------|-----------|
| T01 | 数据导入 | 🔴 阻塞 | Import Movies 找不到文件 | 文件权限不足或路径错误 |
| T02 | Topaz | 🟡 警告 | 训练 loss 很低但验证 loss 不降 | 过度拟合 |
| T03 | Template | 🟡 警告 | 取向分布不均 | 优势取向（preferred orientation） |
| T04 | 2D | 🟡 警告 | 大量 2D class 模糊 | 参数不合适或数据 SNR 太低 |
| T05 | RELION桥接 | 🔴 阻塞 | opticsGroup1 命名不一致报错 | 不同数据集混用 |
| T06 | RELION桥接 | 🔴 阻塞 | Cannot open image file | star 文件路径指向的文件不存在 |
| T07 | RELION桥接 | 🔴 阻塞 | Box size 不匹配 | csparc2star.py --box 与 Extract box size 不一致 |
| T08 | 3D精修 | 🟡 警告 | FSC 曲线震荡或突然下降 | 颗粒方向不准或分类没分干净 |
| T09 | 运维 | 🟡 警告 | cryoSPARC Job 报权限错误 | setfacl 赋权没有递归或用户名不对 |
| T10 | 数据导入 | 🟡 警告 | 导入的 micrograph 显示异常 | 输入了原始 .eer 而非 motion-corrected .mrc |

---

## T01：Import Movies 找不到文件

**现象**：Import Movies Job 运行后报错 "No micrographs found" 或 "Path does not exist"。

**原因分析**：
- `setfacl` 赋权未执行或未递归（缺少 `-R` 参数）
- 路径中的工作站站点号不一致
- 指向了错误的目录（如原始 `.eer` 而非 motion-corrected 后的 `.mrc`）

**排查步骤**：
```bash
# 1. 确认赋权已生效
getfacl 【数据目录】

# 2. 确认路径存在
ls 【数据目录】/MotionCorr/job002/Movies/*EER.mrc | head

# 3. 确认 cryoSPARC 用户有读权限
sudo -u cryosparcuser ls 【数据目录】
```

**解决**：
```bash
# 重新赋权（注意使用 -R 递归）
setfacl -m u:cryosparcuser:rwx -R 【数据目录根路径】

# 确认工作站站点（225/226/227）
# 注意：文件不是软连接，是实际路径
```

---

## T02：Topaz 训练过度拟合

**现象**：Topaz Train 输出显示 training loss 持续下降但 validation loss 不降反升。

**原因分析**：模型在"背答案"——记住了训练集中每张 micrograph 的噪声模式，而不是学会"通用的颗粒特征"。常见于训练集太小或过于同质。

**判断方法**：
- 观察 Topaz 输出目录中的 loss 曲线（`model_training.txt`）
- Training loss 很低 → Validation loss 很高 = 过拟合

**解决**：
1. **增加训练集多样性**：多选几张不同冰层厚度、不同区域的 micrographs
2. **减少训练轮次**：在 loss 开始 diverge 的点之前停止
3. **增加训练集数量**：从 ~500 张增加到 ~1000 张
4. **检查 GT 质量**：用于训练的颗粒坐标是否都是好颗粒（Select 2D 是否够严格）

**预防**：训练时同时观察 training 和 validation loss 曲线，发现 divergence 立即停止。

---

## T03：取向分布不均（Preferred Orientation）

**现象**：2D class average 的取向分布图（Euler 角分布）显示某些角度几乎没有颗粒，而某些角度颗粒堆积。

**原因**：蛋白在冰层中倾向于以某个特定方向吸附——这是冷冻电镜的固有问题，不是操作失误。

**解决**：
1. **Template Picker 补全**：识别劣势取向方向 → Create Templates 生成该方向的投影 → Template Picker 专门补全
2. **倾斜采集**：在数据采集阶段使用 tilt（30-40°），让蛋白在不同角度暴露于电子束
3. **不同冰层条件**：改变 blotting 参数或使用不同支持膜

**对 3D 重建的影响**：取向分布不均会导致密度图在缺失方向的 Fourier 壳上出现空缺，表现为 anisotropic（各向异性）分辨率。

---

## T04：大量 2D class 模糊

**现象**：2D Classification 结果中，>50% 的 class average 看不清二级结构特征。

**可能原因与排查顺序**：

1. **颗粒太少 / 颗粒质量差** → 检查 Select 2D 前的颗粒数量和第 2.1 步的 Blob/Topaz 输出
2. **2D class 数太多** → 颗粒数/class 太少（每类 < 50 个颗粒），减少 class 数
3. **Mask diameter 不对** → 太大（包含过多溶剂）或太小（切掉蛋白信号）
4. **数据 SNR 太低** → 需考虑 Topaz 挑颗粒（比 Blob 对低 SNR 更鲁棒）
5. **CTF 估算有问题** → 检查 Patch CTF 的 fit 质量，可能需要调整 CTF 估算参数

**快速试错**：
```
减少 class 数（100→50）→ 看是否改善
降低 mask diameter → 看是否改善
如果都无效 → 检查原始 micrograph 质量和 CTF fit
```

---

## T05：RELION opticsGroup1 命名不一致

**现象**：第二套数据集导入 RELION 后报错 "opticsGroup1 not found" 或 "Multiple optics groups with different parameters"。

**原因**：csparc2star.py 转换时，不同批次的颗粒可能被标记为不同的 opticsGroup。RELION 要求同一 Job 中所有颗粒属于同一组或明确分组。

**解决**：
```bash
# 1. 打开 star 文件，搜索 opticsGroup
grep -n "opticsGroup" 【star文件】

# 2. 在 vi 中统一命名
:%s #_rlnOpticsGroupName .*#_rlnOpticsGroupName opticsGroup1#g

# 3. 注意：只对同一采集参数的数据这样做。
#    不同 pixel size / dose / voltage 的数据必须分开进入不同 RELION Job。
```

**预防**：不同采集参数（不同 pixel size、不同电压、不同剂量）的数据分别转换、分别建 RELION 项目。

---

## T06：RELION "Cannot open image file"

**现象**：RELION 运行时报 "Cannot open image file: ..." 并列出 micrograph 路径。

**原因**：star 文件中的 micrograph 路径在 RELION 端的文件系统中不存在。通常是因为步骤 3 的路径替换不正确或漏了替换。

**排查**：
```bash
# 检查 star 文件中的路径
grep "_rlnMicrographName" 【star文件】 | head -5 | while read line; do
    path=$(echo "$line" | awk '{print $NF}')
    if [ ! -f "$path" ]; then
        echo "NOT FOUND: $path"
    fi
done
```

**解决**：
```bash
# 重新执行步骤 3，确认路径前缀替换正确
vi 【star文件】
:%s #【cryoSPARC路径前缀】#【RELION路径前缀】#g
# 检查替换效果
:%s/#//gn    # 查看剩余多少个 # 分隔符（应该为 0）
:wq
```

---

## T07：csparc2star.py box size 不匹配

**现象**：RELION Extract 时报 "Box size exceeds micrograph dimensions" 或颗粒位置偏移、不在中心。

**原因**：`csparc2star.py --box` 参数与你 cryoSPARC Extract 时设置的实际 box size 不同。

**解决**：
1. 回到 cryoSPARC，找到对应的 Extract Job
2. 查看 Job 参数中的 `Extraction box size (pix)` 值
3. 用该值重新运行 csparc2star.py

**预防**：将 `--box` 参数与 cryoSPARC Extract 的 box size 绑定为一个常数，写在脚本注释中避免遗忘。

---

## T08：FSC 曲线异常

**现象**：Homogeneous Refinement 的 FSC 曲线出现以下异常模式之一：
- 在低分辨率处（如 20-30Å）出现震荡
- FSC 曲线突然下降后平台（而非平滑衰减）
- FSC=0.143 处的分辨率远差于预期

**诊断与解决**：

| 异常模式 | 最可能原因 | 解决 |
|---------|-----------|------|
| 低分辨率震荡 | 颗粒取向严重不均 | Template Picker 补全或重新采集 |
| 突然下降+平台 | Heterogeneous 分类未分干净 | 增加 Hetero class 数或调低 class similarity |
| 整体分辨率差 | 颗粒数不够或噪声太大 | 扩大颗粒量、优化 2D 筛选条件 |

---

## T09：cryoSPARC Job 权限错误

**现象**：cryoSPARC Job 在运行时报 "Permission denied" 或无法读取文件。

**原因**：数据导入前未赋予 cryoSPARC 用户读权限；或文件的实际拥有者发生了变化。

**解决**：
```bash
# 重新赋权（-R 递归对所有子目录和文件）
setfacl -m u:cryosparcuser:rwx -R 【数据目录】

# 确认生效
getfacl 【数据目录】 | grep cryosparcuser
```

**预防**：每次新数据到达时，先用脚本统一赋权。

---

## T10：导入的 micrograph 显示异常

**现象**：Import Movies 后，在 cryoSPARC 中预览 micrograph 发现图像异常（全黑/全白/严重噪点）。

**原因**：Import Movies 的输入应该是 **motion correction 之后**的 `.mrc` 文件，而不是原始的 `.eer` 或 `.tiff`。MotionCor2/RELION MotionCorr 将原始影片帧对齐并输出为单个 `.mrc`。

**排查**：
```bash
# 确认 MotionCorr 输出确实存在
ls MotionCorr/job002/Movies/*.mrc | head
# 如果不存在，检查 MotionCorr job 是否成功完成
```

**解决**：确保导入路径指向 `MotionCorr/job002/Movies/*EER.mrc` 而非原始数据目录。

---

## 预防性检查清单

在每次启动新数据处理前，逐项过一遍：

- [ ] 数据已到达服务器且赋权完成（`setfacl -R`）
- [ ] MotionCorr 已完成且输出 `.mrc` 文件正常
- [ ] Import Movies 的路径指向 MotionCorr 输出目录
- [ ] Pixel size / Voltage / Dose / Cs 参数确认正确
- [ ] 跑 Patch CTF 后检查几张 micrograph 的 CTF fit 质量
- [ ] Curate Exposures 删除明显坏照片
- [ ] Topaz 训练时同时观察 training 和 validation loss
- [ ] 2D 分类后检查 class average 质量和取向分布
- [ ] 3D 精修后检查 FSC 曲线是否正常
