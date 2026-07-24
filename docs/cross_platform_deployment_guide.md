# StructPilot 跨平台部署完整指南

## 🎯 跨平台兼容性

### ✅ 支持的平台

| 操作系统 | 版本要求 | 状态 |
|---------|---------|------|
| **Windows** | 10/11 | ✅ 完全兼容 |
| **Ubuntu** | 20.04 / 22.04 | ✅ 完全兼容 |
| **CentOS** | 7 / 8 | ✅ 完全兼容 |
| **macOS** | 11+ | ✅ 完全兼容 |
| **其他 Linux** | Python 3.9+ | ✅ 应该可以 |

### 技术保证

- ✅ 所有依赖都是纯 Python 包
- ✅ 使用 `pathlib` 处理跨平台路径
- ✅ 无操作系统特定代码
- ✅ Streamlit 本身跨平台

---

## 📦 部署方式对比

| 方式 | 适用场景 | 难度 | 优势 |
|------|---------|------|------|
| **本地开发** | 个人测试 | ⭐ | 快速启动 |
| **服务器裸机** | 小型实验室 | ⭐⭐ | 简单直接 |
| **Docker容器** | 生产环境 | ⭐⭐⭐ | 隔离、易迁移 |
| **Systemd服务** | 长期运行 | ⭐⭐⭐⭐ | 自动重启 |

---

## 🚀 方案1：Windows 服务器部署

### 前提条件
- Windows 10 / 11 / Server 2019+
- Python 3.9 或更高版本
- 管理员权限

### 步骤1：安装 Python

```powershell
# 下载 Python 3.11（推荐）
# https://www.python.org/downloads/

# 验证安装
python --version  # 应显示 Python 3.9+
```

### 步骤2：克隆代码

```powershell
# 打开 PowerShell（管理员）
cd C:\
git clone https://github.com/hwl26/StructPilot-v6.0.git
cd StructPilot-v6.0
```

### 步骤3：安装依赖

```powershell
# 创建虚拟环境（推荐）
python -m venv venv
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 步骤4：首次启动

```powershell
streamlit run main.py

# 应该看到：
#   Local URL: http://localhost:8501
#   Network URL: http://192.168.x.x:8501
```

### 步骤5：配置开机自启（Windows）

**方法A：任务计划程序**

1. 创建启动脚本 `start_structpilot.bat`：
```batch
@echo off
cd C:\StructPilot-v6.0
call venv\Scripts\activate
streamlit run main.py --server.port 8501 --server.address 0.0.0.0
```

2. 打开「任务计划程序」
3. 创建基本任务：
   - 名称：StructPilot
   - 触发器：计算机启动时
   - 操作：启动程序
   - 程序：`C:\StructPilot-v6.0\start_structpilot.bat`

**方法B：NSSM（推荐）**

```powershell
# 下载 NSSM: https://nssm.cc/download
# 解压到 C:\nssm

C:\nssm\nssm.exe install StructPilot "C:\StructPilot-v6.0\venv\Scripts\streamlit.exe" "run main.py --server.port 8501 --server.address 0.0.0.0"
C:\nssm\nssm.exe set StructPilot AppDirectory "C:\StructPilot-v6.0"
C:\nssm\nssm.exe start StructPilot

# 验证服务
C:\nssm\nssm.exe status StructPilot
```

### 步骤6：配置防火墙

```powershell
# 允许 8501 端口（局域网）
netsh advfirewall firewall add rule name="StructPilot" dir=in action=allow protocol=TCP localport=8501
```

### 步骤7：测试访问

```
本机：http://localhost:8501
局域网其他电脑：http://服务器IP:8501
```

---

## 🐧 方案2：Ubuntu 服务器部署

### 前提条件
- Ubuntu 20.04 / 22.04
- sudo 权限
- 网络连接

### 步骤1：更新系统并安装 Python

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3.9 python3.9-venv python3-pip git
```

### 步骤2：克隆代码

```bash
cd /opt
sudo git clone https://github.com/hwl26/StructPilot-v6.0.git
cd StructPilot-v6.0
sudo chown -R $USER:$USER .
```

### 步骤3：安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 步骤4：首次启动测试

```bash
streamlit run main.py --server.port 8501 --server.address 0.0.0.0

# Ctrl+C 停止后继续下一步
```

### 步骤5：创建 Systemd 服务（自动重启）

```bash
sudo nano /etc/systemd/system/structpilot.service
```

写入以下内容：

```ini
[Unit]
Description=StructPilot v6.0 Web Service
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/opt/StructPilot-v6.0
Environment="PATH=/opt/StructPilot-v6.0/venv/bin"
ExecStart=/opt/StructPilot-v6.0/venv/bin/streamlit run main.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**注意**：将 `your_username` 替换为实际用户名

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable structpilot
sudo systemctl start structpilot

# 检查状态
sudo systemctl status structpilot

# 查看日志
sudo journalctl -u structpilot -f
```

### 步骤6：配置防火墙（UFW）

```bash
sudo ufw allow 8501/tcp
sudo ufw reload
sudo ufw status
```

### 步骤7：测试访问

```bash
# 获取服务器 IP
ip addr show | grep "inet " | grep -v 127.0.0.1

# 在其他电脑浏览器访问
http://服务器IP:8501
```

---

## 🐳 方案3：Docker 部署（最佳实践）

### 优势
- ✅ 环境隔离
- ✅ 一键部署
- ✅ 易于备份和迁移
- ✅ 跨平台一致

### 步骤1：安装 Docker

**Ubuntu**:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# 重新登录生效
```

**Windows**:
- 下载 Docker Desktop: https://www.docker.com/products/docker-desktop

### 步骤2：创建 Dockerfile

```bash
cd /path/to/StructPilot-v6.0
nano Dockerfile
```

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8501

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# 启动命令
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
```

### 步骤3：构建镜像

```bash
docker build -t structpilot:v6.0 .
```

### 步骤4：运行容器

```bash
docker run -d \
  --name structpilot \
  --restart always \
  -p 8501:8501 \
  -v /data/structpilot:/app/runtime \
  structpilot:v6.0
```

**参数说明**：
- `-d`: 后台运行
- `--restart always`: 自动重启
- `-p 8501:8501`: 端口映射
- `-v /data/structpilot:/app/runtime`: 数据持久化

### 步骤5：管理容器

```bash
# 查看日志
docker logs -f structpilot

# 停止容器
docker stop structpilot

# 启动容器
docker start structpilot

# 重启容器
docker restart structpilot

# 进入容器调试
docker exec -it structpilot /bin/bash
```

### 步骤6：备份和恢复

**备份数据**:
```bash
tar -czf structpilot_backup_$(date +%Y%m%d).tar.gz /data/structpilot
```

**迁移到新服务器**:
```bash
# 在新服务器上
docker pull structpilot:v6.0
docker run -d --name structpilot --restart always -p 8501:8501 \
  -v /data/structpilot:/app/runtime structpilot:v6.0
```

---

## 🔧 常见问题排查

### Q1：端口被占用

**错误**：`Port 8501 is already in use`

**解决**：
```bash
# Windows
netstat -ano | findstr :8501
taskkill /PID <PID> /F

# Linux
sudo lsof -i :8501
sudo kill -9 <PID>

# 或者换个端口
streamlit run main.py --server.port 8502
```

### Q2：局域网无法访问

**检查清单**：
1. 服务器防火墙是否开放 8501 端口
2. `--server.address` 是否设置为 `0.0.0.0`
3. 网络是否在同一局域网
4. IP 地址是否正确

**测试连接**：
```bash
# 在客户端电脑
ping 服务器IP
telnet 服务器IP 8501  # Windows 需先启用 telnet 功能
```

### Q3：权限问题（Linux）

**错误**：`Permission denied: '/opt/StructPilot-v6.0/runtime'`

**解决**：
```bash
sudo chown -R $USER:$USER /opt/StructPilot-v6.0
chmod -R 755 /opt/StructPilot-v6.0
```

### Q4：依赖安装失败

**错误**：`error: Microsoft Visual C++ 14.0 is required` (Windows)

**解决**：
```powershell
# 安装 Visual C++ Build Tools
# https://visualstudio.microsoft.com/visual-cpp-build-tools/

# 或者使用预编译轮子
pip install --only-binary :all: <package>
```

### Q5：Graphviz 渲染失败

**错误**：`Graphviz executables not found`

**解决**：
```bash
# Ubuntu
sudo apt install graphviz

# Windows
# 下载安装：https://graphviz.org/download/
# 添加到 PATH: C:\Program Files\Graphviz\bin
```

---

## 📊 性能优化建议

### 1. 硬件配置

**最低配置**（10人以下）：
- CPU: 2核
- 内存: 4GB
- 硬盘: 50GB

**推荐配置**（50人以下）：
- CPU: 4核
- 内存: 8GB
- 硬盘: 100GB SSD

**高性能配置**（100人以上）：
- CPU: 8核+
- 内存: 16GB+
- 硬盘: 500GB SSD

### 2. 系统优化

**Linux**:
```bash
# 增加文件句柄限制
sudo nano /etc/security/limits.conf
# 添加：
*  soft  nofile  65536
*  hard  nofile  65536

# 优化 TCP 参数
sudo sysctl -w net.core.somaxconn=65535
```

**Windows**:
```powershell
# 增加并发连接数
REG ADD "HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters" /v TcpNumConnections /t REG_DWORD /d 16777214 /f
```

### 3. Streamlit 配置

创建 `.streamlit/config.toml`：

```toml
[server]
port = 8501
address = "0.0.0.0"
maxUploadSize = 200
enableXsrfProtection = true

[browser]
gatherUsageStats = false

[theme]
base = "light"
```

---

## 🔐 安全加固

### 1. HTTPS 加密（生产环境必需）

使用 Nginx 反向代理：

```nginx
# /etc/nginx/sites-available/structpilot
server {
    listen 80;
    server_name structpilot.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name structpilot.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. 访问控制

```bash
# 只允许局域网访问
sudo ufw deny 8501
sudo ufw allow from 192.168.0.0/16 to any port 8501
```

### 3. 定期备份

```bash
# 添加到 crontab
crontab -e

# 每天凌晨2点备份
0 2 * * * tar -czf /backup/structpilot_$(date +\%Y\%m\%d).tar.gz /opt/StructPilot-v6.0/runtime
```

---

## 📝 部署检查清单

部署完成后，请逐项确认：

- [ ] Python 版本 >= 3.9
- [ ] 所有依赖安装成功
- [ ] 服务器 IP 固定（或使用 DHCP 保留）
- [ ] 防火墙开放 8501 端口
- [ ] 服务自动启动配置
- [ ] 本机访问测试通过（http://localhost:8501）
- [ ] 局域网访问测试通过（http://IP:8501）
- [ ] 管理员账号密码已修改
- [ ] 课题组成员账号已创建
- [ ] 数据备份策略已配置
- [ ] 使用文档已分发给成员

---

## 🆘 获取帮助

- GitHub Issues: https://github.com/hwl26/StructPilot-v6.0/issues
- 邮件支持: [你的邮箱]
- 文档：`docs/` 目录下的所有指南

---

**最后更新**：2026-07-24
**适用版本**：StructPilot v6.0+
