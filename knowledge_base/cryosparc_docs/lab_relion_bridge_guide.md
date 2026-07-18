# cryoSPARC → RELION 桥接指南

> **来源**: 实验室真实运维经验
> **定位**: cryoSPARC 与 RELION 之间的颗粒坐标转换与互操作
> **⚠️**: csparc2star.py 的 --box 参数需根据你最初在 cryoSPARC Extract 时设置的 box size 来确定，示例值仅作参考

---

## 一、什么时候需要桥接？

以下场景需要使用 cryoSPARC → RELION 桥接：

- cryoSPARC 挑颗粒 + 2D 分类效果好，但想用 RELION 的 3D 分类 / Bayesian Polishing 等独有功能
- 课题组内的标准管线在 RELION 端，希望保持一致性
- RELION 的某些精修算法（如 SIDESPLITTER、3D Flex）在特定场景下有优势
- 需要与已有 RELION 项目的颗粒合并处理

---

## 二、工具链环境准备

### 2.1 安装 pyem

```bash
conda create -n pyem python=3.9
conda activate pyem
pip install pyem
```

`csparc2star.py` 来自 pyem 工具包，是 MIT 开发的 cryoSPARC ↔ RELION 互操作工具集。

### 2.2 确认可执行

```bash
which csparc2star.py
# 输出: /home/software/miniconda3/envs/pyem/bin/csparc2star.py (或类似路径)
```

---

## 三、完整转换流程（四步）

### 步骤 1：找到 RELION 端的 motion-corrected movies 路径

```bash
cd 【motion correction 输出目录】
# 例: cd /fs/pool/pool-train/EM_data/【项目名】/MotionCorr/job002/Movies
ls *EER.mrc | head
```

**关键**：确保路径指向的是 **motion correction 之后**的 `.mrc` 文件，不是原始 `.eer` 或 `.tiff`。

> 注意：每一台服务器/每次采集的路径结构可能不同。不要硬编码路径，每次确认一下。

### 步骤 2：cryoSPARC 颗粒坐标 → RELION star 格式转换

```bash
csparc2star.py \
  --box 【你的box_size】 \
  --swapxy \
  --inverty \
  【cryoSPARC颗粒坐标.cs】 \
  【cryoSPARC颗粒结构信息_passthrough.cs】 \
  【输出star文件名.star】 \
  --strip-uid
```

**参数详解**：

| 参数 | 含义 | 是否必须 | 示例/说明 |
|------|------|---------|-----------|
| `--box` | RELION 颗粒框大小（像素） | ✅ 必须 | **需与你最初在 cryoSPARC Extract 时设置的 box size 保持一致**。你在 Extract 中设了多少就是多少。240 仅为示例值 |
| `--swapxy` | 交换 X/Y 坐标 | ✅ 必须 | cryoSPARC 和 RELION 的坐标系定义不同 |
| `--inverty` | 翻转 Y 坐标 | ✅ 必须 | 两个软件的 Y 轴方向相反 |
| 输入1 | 颗粒坐标信息 | ✅ 必须 | 如 `J25_particles_kept.cs` |
| 输入2 | 颗粒结构信息（passthrough） | ✅ 必须 | 如 `J25_passthrough_particles_kept.cs` |
| 输出 | star 文件名 | ✅ 必须 | 如 `J25_particle.star` |
| `--strip-uid` | 去掉 UID 字段 | 推荐 | 让输出更干净，减少 RELION 解析干扰 |

**两个输入文件的来源**：

在 cryoSPARC 中，Select 2D（或其他输出颗粒的操作）完成后，Job 的输出目录会同时生成两个 `.cs` 文件：
- `【J编号】_particles_kept.cs` → 颗粒坐标
- `【J编号】_passthrough_particles_kept.cs` → 透传的元数据（micrograph 路径、CTF 参数等）

两个都要传给 csparc2star.py。

### 步骤 3：修改 star 文件路径

cryoSPARC 和 RELION 存储文件路径的格式不同，需要手动替换：

```bash
vi 【生成的star文件】
# 在 vi 中执行全局替换
:%s #【cryoSPARC路径前缀】#【RELION路径前缀】#g
gg      # 快速回到文件开头检查
:wq     # 保存退出
```

**路径转换示例**：

```
cryoSPARC 路径格式:   J3/Import/.../Movies/xxx_EER.mrc
RELION 需要的格式:    MotionCorr/job002/Movies/xxx_EER.mrc

# 在 vi 中:
:%s #J3/Import/ #MotionCorr/job002/Movies/ #g
```

> vi 命令说明：`:%s` = 全文替换；`#` 是分隔符（因为路径里有 `/`，用 `#` 比分隔更清晰）；`g` = 每行所有匹配都替换。

### 步骤 4：RELION 端 CTF 重算

关键一步：之前的 CTF 是在 cryoSPARC 里算的（Patch CTF），到 RELION 后需要重算。

原因：CTF 估计和后续处理（2D 分类、3D 精修）使用的软件相关。cryoSPARC 的 CTF 参数嵌入在 `.cs` 文件中，RELION 不直接兼容——但可以通过 csparc2star.py 把 CTF 参数写进 star 文件。然而最稳妥的做法是：

1. 在 RELION 中用 `Ctffind4` 或 `Gctf` 对**同一批 micrographs** 重新跑 CTF 估计
2. 用 RELION 的 `--ctf` 参数指定重算后的 CTF 值

---

## 四、故障排查

### 故障 1：opticsGroup 命名不一致

**现象**：第二套数据集导入 RELION 后，`opticsGroup1` 命名变化导致报错。

**原因**：RELION 用 `opticsGroup` 来区分不同采集参数的颗粒组。同一个 star 文件中如果有多个 `opticsGroup` 但命名不统一（如 `opticsGroup1` vs `opticsGroup2` 或空值），RELION 会报错。

**解决**：
```bash
# 在 vi 中检查 opticsGroup 字段
vi 【star文件】
/opticsGroup   # 搜索出现位置

# 如果发现不一致，统一命名
:%s #_rlnOpticsGroupName opticsGroup1#_rlnOpticsGroupName opticsGroup1#g
```

**预防**：每次用 csparc2star.py 转换时，确认所有输入颗粒来自同一批次、同一采集参数的数据。不同批次的数据分别转换、分别建 RELION 项目。

### 故障 2：star 文件路径指向的文件不存在

**现象**：RELION 运行 2D/3D 时报 "Cannot open image file"。

**解决**：
```bash
# 检查 star 文件中的路径是否真实存在
grep "_rlnMicrographName" 【star文件】 | head -5
# 逐条验证
ls -la 【路径】
# 如果不通 → 回到步骤 3，修正路径
```

### 故障 3：box size 不匹配

**现象**：RELION Extract 时报 "Box size exceeds micrograph dimensions" 或颗粒位置偏移。

**原因**：csparc2star.py 的 `--box` 参数和你 cryoSPARC Extract 时设置的实际 box size 不一致。

**解决**：回到 cryoSPARC，查看 Extract Job 的参数中 `Extraction box size` 的实际值，然后用相同的值重新跑 csparc2star.py。

---

## 五、完整示例脚本

将上述步骤汇总为一个可执行的 shell 脚本（需根据实际情况修改路径和参数）：

```bash
#!/bin/bash
# cryoSPARC → RELION 桥接脚本（模板）
# 使用前请修改以下变量

# === 配置区域 ===
PYEM_ENV="pyem"
CRYOSPARC_DIR="/fs/pool/pool-train/EM_data/【项目名】/cryoSPARC projects/CS-【项目】-【日期】"
RELION_MC_DIR="/fs/pool/pool-train/EM_data/【项目名】/MotionCorr/job002/Movies"
BOX_SIZE=240          # ⚠️ 改成你的实际 box size
JOB_NUM="J25"         # cryoSPARC Job 编号

# === 执行转换 ===
conda activate ${PYEM_ENV}

csparc2star.py \
  --box ${BOX_SIZE} \
  --swapxy \
  --inverty \
  "${CRYOSPARC_DIR}/${JOB_NUM}/${JOB_NUM}_particles_kept.cs" \
  "${CRYOSPARC_DIR}/${JOB_NUM}/${JOB_NUM}_passthrough_particles_kept.cs" \
  "${JOB_NUM}_particle.star" \
  --strip-uid

# === 修改路径（需手动确认） ===
echo ">>> 请手动执行以下命令修改 star 文件路径:"
echo "vi ${JOB_NUM}_particle.star"
echo ":%s #J3/Import/ #MotionCorr/job002/Movies/ #g"
echo ":wq"

echo ">>> 转换完成！"
```

---

## 六、相关资源

- pyem 官方仓库: https://github.com/asarnow/pyem
- RELION 官方文档: https://relion.readthedocs.io/
- cryoSPARC 官方文档: https://guide.cryosparc.com/
