# RELION 数据处理流程指导（入门模式）

## 适用场景

完成需求问卷后，系统推荐使用 RELION 进行数据处理时，本指南将逐步引导你完成从数据传输到运动校正的完整流程。

---

## 📋 前置准备

在开始之前，请准备以下信息：

| 参数 | 说明 | 示例 | 你的值 |
|------|------|------|--------|
| **数据存储路径** | 原始数据在哪里？ | `/home/Titan3_falcon/YourProject_20250704` | `__________` |
| **目标处理路径** | 在哪里处理数据？ | `/fs/pool/pool-duke/EM_data/YourProject` | `__________` |
| **数据格式** | EER还是TIFF？ | `.eer` 或 `.tif` | `__________` |
| **Gain 文件** | Gain reference 路径 | `/path/to/gain.mrc` | `__________` |

---

## 第一步：数据传输

### 1.1 查看原始数据路径

```bash
# 登录到数据采集服务器（询问实验室管理员获取IP和用户名）
ssh <username>@<采集服务器IP>

# 进入数据存储目录
cd /home/<数据目录>

# 查看你的数据文件夹
ls -lh

# 找到目标文件夹后，复制完整路径
pwd
# 输出示例：/home/Titan3_falcon/YourProject_20250704
```

**📝 记录你的数据路径：** `______________________________`

---

### 1.2 传输数据到处理服务器

```bash
# 登录到数据处理服务器
ssh <username>@<处理服务器IP>

# 进入数据存储盘
cd /fs/pool/<your_pool>/EM_data

# 使用 rsync 传输数据（保持权限和元数据）
rsync -avrP -e "ssh -p <端口号>" \
    <采集服务器用户名>@<采集服务器IP>:<原始数据路径> \
    .

# 参数说明：
# -a: 归档模式（保留权限、时间戳）
# -v: 显示详细信息
# -r: 递归复制子目录
# -P: 显示进度 + 断点续传
# -e "ssh -p <端口>": 指定SSH端口（默认22，如有修改则填写）
```

**⏱️ 传输时间估算：**
- 小数据集（<100GB）：5-10分钟
- 中型数据集（100-500GB）：30-60分钟
- 大型数据集（>500GB）：1-3小时

**💡 提示：** 传输过程中可以按 `Ctrl+Z` 暂停，输入 `fg` 恢复。

---

## 第二步：RELION 工作环境准备

### 2.1 创建工作目录

```bash
# 进入处理盘
cd /fs/pool/<your_pool>/EM_data

# 创建项目文件夹（命名规范：日期_项目名_蛋白名）
mkdir YourProject_20250704_ProteinName_Grid1
cd YourProject_20250704_ProteinName_Grid1

# 创建 Movies 子文件夹（存放原始拍照文件）
mkdir Movies
```

---

### 2.2 整理原始数据文件

**问题：** 原始数据可能散落在多个 `GridSquare_xxxx/Data/` 子目录中。

**解决方案：** 将所有 `.eer` 文件移动到统一位置。

```bash
# 方法1：如果数据已经在一个文件夹
# （跳过此步骤，直接进入2.3）

# 方法2：如果数据在多个 GridSquare 子目录中
# 查看数据结构
ls -R <传输的数据文件夹>/Images-Disc1/

# 批量移动所有 .eer 文件到当前目录
mv <数据文件夹>/Images-Disc1/GridSquare*/Data/*.eer .

# 或移动到 Movies 文件夹
mv <数据文件夹>/Images-Disc1/GridSquare*/Data/*.eer Movies/
```

**⚠️ 注意：** 确保移动后原始数据有备份！

---

### 2.3 创建软连接（推荐方式）

**为什么用软连接？**
- 节省磁盘空间（不复制数据）
- 保留原始数据结构
- 加快处理速度

```bash
# 进入工作目录
cd /fs/pool/<your_pool>/EM_data/YourProject_20250704/Movies

# 创建 EER 文件软连接
ln -s <原始数据路径>/*.eer .

# 创建 Gain 文件软连接
ln -s <原始数据路径>/*.gain .
# 或
ln -s <原始数据路径>/*.mrc .

# 验证软连接是否创建成功
ls -lh | head
# 应该看到类似：
# lrwxrwxrwx ... xxx.eer -> /path/to/original/xxx.eer
```

**📝 填写你的路径：**
- 原始数据路径：`______________________________`
- Gain 文件路径：`______________________________`

---

### 2.4 计算 EER 分组参数

```bash
# 使用 header 命令查看 EER 文件的帧数
header Movies/<任意一个eer文件>.eer

# 输出示例：
# ...
# Number of frames: 7420
# ...
```

**📝 记录帧数：** `_______` 帧

**计算分组数：**
```
总帧数 ÷ 目标每组帧数 = 分组数（向下取整）

示例：
- 总帧数：7420
- 目标每组：40 帧
- 分组数：7420 ÷ 40 = 185.5 → 185 组
```

**📝 你的分组数：** `_______` 组

---

## 第三步：RELION 软件操作

### 3.1 启动 RELION

```bash
# 返回工作目录（与 Movies 同级，不要进入 Movies 运行）
cd /fs/pool/<your_pool>/EM_data/YourProject_20250704

# 加载 RELION 模块（版本号根据实验室配置）
module load relion/5.0.4

# 启动 RELION GUI
relion &
```

**💡 提示：** `&` 表示后台运行，你可以继续使用终端。

---

### 3.2 导入数据（Import）

1. **打开 Import 标签页**

2. **不要点击 Browse 按钮**，而是**手动输入**：
   ```
   Movies/*.eer
   ```
   或
   ```
   Movies/*.tif
   ```

3. **填写参数：**
   | 参数 | 说明 | 你的值 |
   |------|------|--------|
   | Pixel size (Å) | 像素大小 | `_____` |
   | Voltage (kV) | 加速电压 | `_____` |
   | Cs (mm) | 球差 | `_____` |
   | EER grouping | 分组数（见2.4计算） | `_____` |
   | Gain reference | Gain 文件路径 | `Movies/*.gain` |

4. **点击 Run**

5. **验证导入成功：**
   - 下方窗口显示 `Import/job001`
   - 点击后看到 `.star` 文件生成

---

### 3.3 运动校正（Motion Correction）

1. **打开 Motion corr. 标签页**

2. **Input movies STAR file：**
   - 自动填充（上一步的输出）
   - 或手动选择：`Import/job001/movies.star`

3. **关键参数设置：**

   | 参数 | 推荐值 | 说明 |
   |------|--------|------|
   | **Dose per frame (e/Å²)** | 根据采集设置 | 总剂量 ÷ 总帧数 |
   | **Pre-exposure (e/Å²)** | `0` | 首帧前剂量（通常为0） |
   | **EER fractionation** | 见2.4计算 | 分组数 |
   | **Gain reference** | `Movies/*.gain` | Gain 文件路径 |
   | **B-factor** | `150` | 初始值（如失败可调至300-500） |
   | **Number of MPI procs** | `4-8` | 根据服务器空闲程度 |
   | **Number of threads** | `4-8` | 每个进程的线程数 |

   **💡 GPU 加速（如果可用）：**
   - 勾选 `Use RELION's own implementation`
   - 选择可用的 GPU（询问实验室管理员）

4. **运行前检查：**
   ```bash
   # 查看服务器负载（避免抢占他人资源）
   top
   # 按 'u' 键，输入你的用户名，查看自己的进程
   ```

5. **点击 Run**

---

### 3.4 监控运行状态

**正常运行：**
- 下方窗口显示进度：`Processing movie 1/500...`
- CPU/GPU 使用率升高（用 `top` 或 `nvidia-smi` 查看）

**运行成功：**
- 显示绿色 ✅
- 生成 `MotionCorr/job002/` 目录
- 包含校正后的 micrographs 和 drift plot

**运行失败：**
- 显示红色 ❌
- 查看错误日志：
  ```bash
  cat MotionCorr/job002/run.err
  ```

---

### 3.5 常见问题排查

#### **问题1：运行到一半停止了**

**可能原因：**
- 其他用户占用资源
- 内存不足
- 服务器断网

**解决方案：**
```bash
# 检查进程是否还在运行
top
# 按 'u'，输入你的用户名

# 如果进程还在，等待恢复
# 如果进程已终止，在 RELION GUI 点击 "Continue"
```

---

#### **问题2：报错 "local motion too large"**

**原因：** 漂移过大，B-factor 设置过小。

**解决方案：**
1. 停止当前任务
2. 修改 B-factor：`150` → `300` 或 `500`
3. 重新 Run

---

#### **问题3：Gain 文件未找到**

**错误信息：** `Cannot find gain reference file`

**解决方案：**
```bash
# 检查 Gain 文件是否存在
ls -lh Movies/*.gain

# 如果不存在，重新创建软连接
ln -s <原始Gain路径>/*.gain Movies/
```

---

## 第四步：结果验证

### 4.1 查看运动校正结果

1. **在 RELION GUI 中：**
   - 点击 `Display` 按钮
   - 选择几个 micrograph 查看质量

2. **查看 Drift Plot：**
   - 校正后的漂移轨迹应该平滑
   - 总漂移 < 50 Å（优秀）< 100 Å（良好）

---

### 4.2 统计输出

```bash
# 查看生成的文件数量
ls MotionCorr/job002/Movies/*.mrc | wc -l

# 应该等于输入的 movie 数量
```

---

## 📊 参数速查表（可打印）

| 参数 | 你的值 | 备注 |
|------|--------|------|
| 原始数据路径 | | |
| 处理目录 | | |
| 像素大小 (Å) | | |
| 电压 (kV) | | |
| 球差 Cs (mm) | | |
| 总剂量 (e/Å²) | | |
| EER 总帧数 | | |
| EER 分组数 | | |
| Gain 文件路径 | | |
| B-factor | 150（初始值） | 失败时调至300-500 |
| MPI 进程数 | 4-8 | 根据服务器负载 |

---

## 下一步

完成 Motion Correction 后，继续：

1. **CTF 估计（CTF estimation）**
2. **颗粒挑选（Particle picking）**
3. **颗粒提取（Particle extraction）**
4. **2D 分类（2D classification）**

**💡 提示：** 回到 StructPilot，系统会根据你的进度自动推荐下一步操作。

---

## 🆘 需要帮助？

- **技术问题：** 在 StructPilot 公共交流区提问
- **紧急错误：** 联系实验室管理员
- **经验分享：** 将你的经验提交到经验库，帮助其他人

---

**文档版本：** v1.0  
**最后更新：** 2025-01-25  
**维护者：** StructPilot 开发团队
