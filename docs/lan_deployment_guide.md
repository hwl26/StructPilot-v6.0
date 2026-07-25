# StructPilot 多课题组隔离部署指南

## 问题场景

学校内多个课题组都部署了 StructPilot，连接同一WiFi的学生能访问所有系统，导致：
- ❌ 隐私泄露：其他组能看到本组的实验经验
- ❌ 数据混淆：不清楚哪些知识是本组的
- ❌ 误操作风险：学生可能在错误的系统提交数据

---

## 解决方案对比

| 方案 | 隔离效果 | 实施难度 | 协作支持 | 推荐场景 |
|------|---------|---------|---------|---------|
| **方案1：IP白名单** | ⭐⭐⭐⭐ | ★☆☆☆☆ | ❌ 不支持跨组协作 | 独立课题组（推荐） |
| **方案2：多租户模式** | ⭐⭐⭐⭐⭐ | ★★★☆☆ | ✅ 支持授权共享 | 同一学院统一平台 |
| **方案3：VPN隧道** | ⭐⭐⭐⭐⭐ | ★★★★☆ | ❌ 完全隔离 | 高度保密课题 |

---

## 方案1：IP 白名单隔离（推荐，5分钟配置）

### 原理

通过 Nginx 或防火墙限制访问IP范围，只有课题组内部IP能访问。

```
课题组A (192.168.1.0/24)
  └─ StructPilot A (192.168.1.100:8501)
      └─ 只允许 192.168.1.0/24 访问 ✅

课题组B学生 (192.168.2.50)
  └─ 访问 192.168.1.100:8501 ❌ 被拒绝
```

---

### 实施步骤

#### **步骤1：确定课题组IP段**

**询问网络管理员：** "我们实验室的IP段是多少？"

**或自行查看：**
```bash
# Linux/Mac
ip addr show | grep inet

# Windows
ipconfig
```

**常见IP段：**
- `192.168.1.0/24` → `192.168.1.1` ~ `192.168.1.254` (254个IP)
- `10.0.1.0/24` → `10.0.1.1` ~ `10.0.1.254`

---

#### **步骤2A：使用 Nginx（推荐，支持HTTPS）**

**安装 Nginx：**
```bash
# Ubuntu/Debian
sudo apt install nginx

# CentOS
sudo yum install nginx

# macOS
brew install nginx
```

**创建配置：** `/etc/nginx/sites-available/structpilot`

```nginx
server {
    listen 80;
    server_name structpilot.lab.local;

    # IP 白名单（修改为本课题组的IP段）
    allow 192.168.1.0/24;   # 允许本组
    deny all;               # 拒绝其他

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

**启用：**
```bash
sudo ln -s /etc/nginx/sites-available/structpilot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**修改 Streamlit 绑定本机：**
```toml
# .streamlit/config.toml
[server]
address = "127.0.0.1"  # 只监听本机
port = 8501
```

**访问地址变为：** `http://192.168.1.100` (无需端口号)

---

#### **步骤2B：使用防火墙（无Nginx时）**

**Linux (ufw):**
```bash
# 清空规则
sudo ufw --force reset

# 允许SSH（避免锁死）
sudo ufw allow 22/tcp

# 只允许本组访问 8501
sudo ufw allow from 192.168.1.0/24 to any port 8501

# 启用
sudo ufw enable
```

**Linux (iptables):**
```bash
# 清空
sudo iptables -F INPUT

# 允许本组
sudo iptables -A INPUT -p tcp --dport 8501 -s 192.168.1.0/24 -j ACCEPT

# 拒绝其他
sudo iptables -A INPUT -p tcp --dport 8501 -j DROP

# 保存
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

**Windows 防火墙：**
1. 控制面板 → Windows Defender 防火墙 → 高级设置
2. 入站规则 → 新建规则 → 端口 → TCP → 8501
3. 允许连接
4. **作用域** → 远程IP地址 → 添加：`192.168.1.0/24`
5. 命名：StructPilot 白名单

---

### 测试验证

**本组测试（应该成功）：**
```bash
curl http://192.168.1.100:8501
# 返回 HTML 内容
```

**其他组测试（应该失败）：**
```bash
curl http://192.168.1.100:8501
# 超时或 403 Forbidden
```

---

## 方案2：多租户模式（需要代码改造）

### 架构设计

一个 StructPilot 实例支持多个课题组：

```
StructPilot 统一平台 (192.168.0.100:8501)
├─ 租户A（李老师课题组）
│   ├─ 用户：admin_a, student_a1, student_a2
│   ├─ 知识库：knowledge_base/tenant_a/
│   └─ 权限：只能看到本组数据
├─ 租户B（王老师课题组）
│   ├─ 用户：admin_b, student_b1
│   ├─ 知识库：knowledge_base/tenant_b/
│   └─ 权限：只能看到本组数据
└─ 公共区（可选）
    └─ 允许跨组共享的通用经验
```

---

### 数据库改造

**原结构：**
```json
{
  "entries": [
    {
      "id": "lab_001",
      "title": "Motion Correction 报错",
      "author": "王师兄"
    }
  ]
}
```

**多租户结构：**
```json
{
  "entries": [
    {
      "id": "lab_001",
      "tenant_id": "tenant_a",  // 新增：租户ID
      "title": "Motion Correction 报错",
      "author": "王师兄",
      "visibility": "private"  // private | public | shared_to:[tenant_b]
    }
  ]
}
```

---

### 用户体系改造

**原结构：**
```json
{
  "users": [
    {"username": "admin", "role": "admin"}
  ]
}
```

**多租户结构：**
```json
{
  "users": [
    {
      "username": "admin_a",
      "tenant_id": "tenant_a",  // 新增：所属租户
      "tenant_name": "李老师课题组",
      "role": "admin"
    },
    {
      "username": "student_a1",
      "tenant_id": "tenant_a",
      "role": "member"
    }
  ]
}
```

---

### 实施步骤（需要开发）

**如果你需要多租户模式，我可以帮你改造代码。需要修改的文件：**

1. `utils/auth.py` — 登录时加载租户信息
2. `utils/rag_*.py` — 检索时过滤租户数据
3. `main.py` — UI 显示租户名称
4. `components/onboarding_v3.py` — 问卷时选择租户

**工作量估计：** 2-3小时（我可以帮你做）

---

## 方案3：VPN 隧道（高度保密）

适用于涉密课题，完全物理隔离。

**原理：**
- 每个课题组搭建自己的 VPN 服务器
- 学生需要先连VPN才能访问 StructPilot
- 即使在同一WiFi，也无法互相访问

**实施：**
- 使用 WireGuard / OpenVPN
- 工作量较大，不展开

---

## 推荐配置矩阵

| 课题组规模 | 保密需求 | 推荐方案 | 原因 |
|----------|---------|---------|------|
| 5-20人 | 一般 | IP白名单 | 配置简单，满足基本需求 |
| 20-50人 | 一般 | IP白名单 + Nginx | 支持HTTPS，更专业 |
| 多课题组统一平台 | 一般 | 多租户模式 | 降低维护成本 |
| 涉密课题 | 高 | VPN + IP白名单 | 双重保护 |

---

## 常见问题

### Q1: IP段如何划分？

**询问网络管理员最准确。** 如果无法联系，可以这样判断：

```bash
# 查看本组多台设备IP
设备A: 192.168.1.10
设备B: 192.168.1.15
设备C: 192.168.1.20

# 前三段相同 → IP段为 192.168.1.0/24
```

---

### Q2: 配置后本组学生也无法访问？

**检查清单：**
1. 学生IP是否在白名单内？（`ip addr` 或 `ipconfig` 查看）
2. 防火墙规则是否生效？（`sudo ufw status` 查看）
3. Nginx 是否正常运行？（`sudo systemctl status nginx`）

---

### Q3: 如何允许特定的跨组协作？

**Nginx 添加多个 IP 段：**
```nginx
allow 192.168.1.0/24;   # 本组
allow 192.168.2.50;     # 协作者IP
deny all;
```

---

### Q4: 多租户模式何时需要？

**满足以下3个条件时推荐多租户：**
1. 多个课题组希望统一维护（不想各自部署）
2. 需要跨组共享部分经验（如通用的 CTF 参数）
3. 有专人负责运维（统一平台需要更多管理）

---

## 部署检查脚本

创建 `check_isolation.sh`：

```bash
#!/bin/bash

echo "========== 隔离配置检查 =========="
echo ""

# 1. 检查Nginx白名单
if systemctl is-active --quiet nginx; then
    echo "✅ Nginx 正在运行"
    grep -r "allow\|deny" /etc/nginx/sites-enabled/structpilot 2>/dev/null
else
    echo "⚠️  Nginx 未运行（使用防火墙模式）"
fi

# 2. 检查防火墙规则
echo ""
echo "--- 防火墙规则 ---"
if command -v ufw &> /dev/null; then
    sudo ufw status | grep 8501
elif command -v iptables &> /dev/null; then
    sudo iptables -L INPUT -n | grep 8501
fi

# 3. 测试本机访问
echo ""
echo "--- 本机访问测试 ---"
if curl -s http://localhost:8501 > /dev/null; then
    echo "✅ 本机可访问"
else
    echo "❌ 本机无法访问"
fi

# 4. 获取本机IP
echo ""
echo "--- 服务器IP ---"
hostname -I | awk '{print "本机IP: " $1}'

echo ""
echo "========== 检查完成 =========="
```

运行：
```bash
chmod +x check_isolation.sh
./check_isolation.sh
```

---

## 总结

| 需求 | 推荐方案 | 配置时间 |
|------|---------|---------|
| 快速隔离 | 防火墙IP白名单 | 5分钟 |
| 生产环境 | Nginx + IP白名单 | 15分钟 |
| 统一平台 | 多租户模式 | 需开发（联系我） |
| 最高保密 | VPN + IP白名单 | 1-2小时 |

**立即行动：**
1. 确定本课题组IP段（问管理员或查看设备IP）
2. 选择方案（推荐从IP白名单开始）
3. 按步骤配置
4. 用其他组设备测试是否被拒绝

需要帮助随时问我！n" > /dev/null; then
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
