# StructPilot 局域网部署指南

## 适用场景

✅ **课题组服务器部署** — 同一WiFi/局域网内所有人可访问  
✅ **实验室共享电脑** — 多人轮流使用同一台机器  
✅ **离线环境** — 无需互联网，内网访问  

---

## 快速开始（5分钟）

### Windows 环境

1. **双击运行启动脚本**
   ```
   start_lan.bat
   ```

2. **记下显示的局域网地址**
   ```
   📡 局域网访问地址：
      http://192.168.1.100:8501
   ```

3. **局域网内其他电脑访问**
   - 手机/笔记本连接同一WiFi
   - 浏览器输入上述地址

---

### Linux/macOS 环境

1. **运行启动脚本**
   ```bash
   chmod +x start_lan.sh
   ./start_lan.sh
   ```

2. **或手动启动**
   ```bash
   streamlit run main.py --server.address 0.0.0.0 --server.port 8501
   ```

---

## 网络架构说明

```
┌─────────────────────────────────────────────┐
│ 学校WiFi / 实验室局域网 (192.168.x.x)        │
│                                             │
│  ┌─────────────┐                            │
│  │ 服务器电脑   │  运行 StructPilot           │
│  │ 192.168.1.100│  端口: 8501                │
│  └──────┬──────┘                            │
│         │                                   │
│    ┌────┴────┬──────┬──────┐                │
│    │         │      │      │                │
│ ┌──▼──┐  ┌──▼──┐ ┌─▼──┐ ┌─▼──┐             │
│ │ PC1 │  │ PC2 │ │笔记本│ │手机│             │
│ └─────┘  └─────┘ └────┘ └────┘             │
│                                             │
│ 所有设备通过浏览器访问:                       │
│ http://192.168.1.100:8501                   │
└─────────────────────────────────────────────┘
```

---

## 防火墙配置

### Windows 防火墙

**方法1：自动添加规则（推荐）**

首次启动时 Streamlit 会弹窗请求防火墙权限，点击「允许访问」即可。

**方法2：手动添加规则**

```powershell
# 以管理员身份运行 PowerShell
New-NetFirewallRule -DisplayName "StructPilot" -Direction Inbound -Protocol TCP -LocalPort 8501 -Action Allow
```

---

### Linux 防火墙 (ufw)

```bash
sudo ufw allow 8501/tcp
sudo ufw reload
```

---

### Linux 防火墙 (firewalld)

```bash
sudo firewall-cmd --permanent --add-port=8501/tcp
sudo firewall-cmd --reload
```

---

## 访问方式对比

| 方式 | 访问地址 | 适用场景 | 需要配置 |
|------|---------|---------|---------|
| **本机访问** | `http://localhost:8501` | 服务器自己用 | 无 |
| **局域网访问** | `http://192.168.x.x:8501` | 课题组共享 | 防火墙 + `address=0.0.0.0` |
| **公网访问** | `http://your-domain.com` | 全球访问 | 域名 + 反向代理 + SSL |
| **Streamlit Cloud** | `https://structpilot.streamlit.app` | 免费托管 | GitHub 连接 |

---

## 常见问题

### Q1: 局域网内其他电脑无法访问

**检查清单：**

1. **服务器 IP 是否正确？**
   ```bash
   # Linux/Mac
   hostname -I
   
   # Windows
   ipconfig
   ```
   找到 `192.168.x.x` 或 `10.x.x.x` 开头的地址

2. **防火墙是否开放 8501 端口？**
   - Windows: 控制面板 → Windows Defender 防火墙 → 高级设置 → 入站规则
   - Linux: `sudo ufw status`

3. **Streamlit 是否绑定到 0.0.0.0？**
   ```bash
   # 检查启动日志，应该看到：
   Network URL: http://192.168.x.x:8501
   ```
   如果只显示 `http://localhost:8501`，说明未绑定到局域网

4. **客户端和服务器是否在同一网段？**
   - 服务器: `192.168.1.100`
   - 客户端: `192.168.1.50` ✅ 可以访问
   - 客户端: `10.0.0.50` ❌ 不同网段，无法访问

---

### Q2: 手机能访问，但电脑不能？

可能是电脑防火墙更严格。临时关闭防火墙测试：

**Windows:**
```
控制面板 → Windows Defender 防火墙 → 启用或关闭 Windows Defender 防火墙
→ 关闭专用网络防火墙（仅测试用）
```

**测试成功后记得重新开启，并添加 8501 端口规则！**

---

### Q3: 如何修改端口（8501 被占用）？

**方法1：命令行指定**
```bash
streamlit run main.py --server.address 0.0.0.0 --server.port 8080
```

**方法2：修改配置文件**
```toml
# .streamlit/config.toml
[server]
port = 8080
```

---

### Q4: 多个课题组能同时部署吗？

可以！每个课题组用不同端口：

```
课题组A: http://192.168.1.100:8501
课题组B: http://192.168.1.100:8502
课题组C: http://192.168.1.100:8503
```

启动命令：
```bash
# 课题组A
streamlit run main.py --server.port 8501

# 课题组B
streamlit run main.py --server.port 8502

# 课题组C
streamlit run main.py --server.port 8503
```

---

## 性能优化

### 1. 使用后台守护进程（推荐生产环境）

**systemd 服务（Linux）**

创建 `/etc/systemd/system/structpilot.service`：

```ini
[Unit]
Description=StructPilot Streamlit App
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/final_struct
ExecStart=/usr/local/bin/streamlit run main.py --server.address 0.0.0.0 --server.port 8501
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动：
```bash
sudo systemctl daemon-reload
sudo systemctl enable structpilot
sudo systemctl start structpilot
```

---

**nohup（Linux/Mac）**

```bash
nohup streamlit run main.py --server.address 0.0.0.0 --server.port 8501 > structpilot.log 2>&1 &
```

停止：
```bash
ps aux | grep streamlit
kill <进程ID>
```

---

**PM2（跨平台推荐）**

```bash
# 安装 PM2
npm install -g pm2

# 启动
pm2 start "streamlit run main.py --server.address 0.0.0.0 --server.port 8501" --name structpilot

# 开机自启
pm2 startup
pm2 save

# 查看状态
pm2 list

# 查看日志
pm2 logs structpilot

# 停止
pm2 stop structpilot
```

---

### 2. 使用反向代理（Nginx）

**优势：**
- 隐藏端口（通过 80/443 访问）
- 支持 HTTPS（SSL 加密）
- 支持多应用（通过子路径区分）

**Nginx 配置示例：**

```nginx
server {
    listen 80;
    server_name structpilot.lab.edu.cn;

    location / {
        proxy_pass http://localhost:8501;
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

访问地址变为：`http://structpilot.lab.edu.cn`（无需端口号）

---

## 安全建议

### 1. 修改默认密码

编辑 `runtime/user_db.json`：
```json
{
  "users": [
    {
      "username": "admin",
      "password": "your-strong-password",  // 改为复杂密码
      "role": "admin"
    }
  ]
}
```

---

### 2. 限制访问IP（可选）

**Nginx IP 白名单：**
```nginx
location / {
    allow 192.168.1.0/24;  # 只允许局域网访问
    deny all;
    proxy_pass http://localhost:8501;
}
```

---

### 3. 定期备份数据

```bash
# 备份知识库
tar -czf backup_$(date +%Y%m%d).tar.gz \
    knowledge_base/ \
    runtime/user_db.json \
    runtime/presets/
```

---

## 监控和日志

### 查看 Streamlit 日志

```bash
# 实时查看
tail -f ~/.streamlit/logs/streamlit.log

# 查看最近错误
grep ERROR ~/.streamlit/logs/streamlit.log
```

---

### 监控资源占用

```bash
# 查看 CPU/内存
top -p $(pgrep -f streamlit)

# 或使用 htop
htop -p $(pgrep -f streamlit)
```

---

## 故障排查脚本

创建 `check_deployment.sh`：

```bash
#!/bin/bash

echo "========== StructPilot 部署检查 =========="
echo ""

# 1. 检查服务是否运行
if pgrep -f "streamlit run" > /dev/null; then
    echo "✅ Streamlit 进程运行中"
else
    echo "❌ Streamlit 未运行"
fi

# 2. 检查端口
if netstat -tuln | grep 8501 > /dev/null; then
    echo "✅ 端口 8501 已监听"
else
    echo "❌ 端口 8501 未监听"
fi

# 3. 检查防火墙
if sudo ufw status | grep 8501 > /dev/null 2>&1; then
    echo "✅ 防火墙规则已配置"
else
    echo "⚠️  防火墙可能未配置 8501 端口"
fi

# 4. 检查局域网 IP
echo ""
echo "📡 当前局域网 IP:"
hostname -I | awk '{print "   http://"$1":8501"}'

echo ""
echo "=========================================="
```

运行：
```bash
chmod +x check_deployment.sh
./check_deployment.sh
```

---

## 总结

### 快速部署清单

- [x] 安装依赖：`pip install -r requirements.txt`
- [x] 运行启动脚本：`start_lan.bat` (Windows) 或 `./start_lan.sh` (Linux)
- [x] 配置防火墙：允许 8501 端口
- [x] 记录局域网地址：`http://192.168.x.x:8501`
- [x] 分享给课题组成员

### 访问地址

- **本机访问:** `http://localhost:8501`
- **局域网访问:** `http://<服务器IP>:8501`
- **Streamlit Cloud:** `https://your-app.streamlit.app`

### 技术支持

遇到问题？检查以下资源：
- 📖 本文档的「常见问题」章节
- 🐛 运行 `check_deployment.sh` 诊断脚本
- 📝 查看 Streamlit 日志：`~/.streamlit/logs/streamlit.log`
