# StructPilot 双重安全 + 跨组协作部署指南

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    学校 WiFi 网络                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🔒 课题组A私有空间 (192.168.1.100)                          │
│   ├─ IP白名单：192.168.1.0/24                               │
│   ├─ Nginx Basic Auth 密码：LabA_2024@Secure                │
│   ├─ StructPilot 登录：admin/member 账号                     │
│   └─ 可选择性公开经验到"公共区"                               │
│                                                             │
│  🔒 课题组B私有空间 (192.168.2.100)                          │
│   ├─ IP白名单：192.168.2.0/24                               │
│   ├─ Nginx Basic Auth 密码：LabB_2024@Secure                │
│   ├─ StructPilot 登录：admin/member 账号                     │
│   └─ 可选择性公开经验到"公共区"                               │
│                                                             │
│  🌍 公共交流平台 (192.168.0.100 或 云端)                     │
│   ├─ 无IP限制，所有课题组可访问                               │
│   ├─ 仅 StructPilot 密码保护                                 │
│   ├─ 论坛/讨论区                                              │
│   └─ 汇聚各组的"公开经验"                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 第一步：课题组私有空间部署（每个组独立配置）

### 1.1 确定IP段

```bash
# 方法1：询问网络管理员
"我们实验室的IP段是多少？"

# 方法2：查看多台设备IP，找共同前缀
# 设备A: 192.168.1.10
# 设备B: 192.168.1.15
# 设备C: 192.168.1.20
# → IP段：192.168.1.0/24

# 方法3：使用命令查看
ip addr show | grep inet
# 或 Windows:
ipconfig
```

**📝 记录你的IP段：** `__________`

---

### 1.2 安装 Nginx

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install nginx apache2-utils
```

**CentOS/RHEL:**
```bash
sudo yum install nginx httpd-tools
```

**macOS:**
```bash
brew install nginx
```

---

### 1.3 配置双重认证

#### A. 创建 Nginx 密码文件（第一层保护）

```bash
# 创建密码文件（会提示输入密码）
sudo htpasswd -c /etc/nginx/.htpasswd_labA admin_labA

# 示例密码：LabA_2024@Secure（请改为你的强密码）
```

#### B. 配置 Nginx（第二层保护：IP白名单）

```bash
# 创建配置文件
sudo nano /etc/nginx/sites-available/structpilot-labA
```

粘贴配置（修改IP段为你的）：
```nginx
server {
    listen 80;
    server_name structpilot-labA.local;

    # 第一层保护：IP 白名单
    allow 192.168.1.0/24;  # 修改为你的IP段
    deny all;

    # 第二层保护：密码认证
    auth_basic "Lab A Private Area - Authorized Personnel Only";
    auth_basic_user_file /etc/nginx/.htpasswd_labA;

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

#### C. 启用配置

```bash
# 创建软连接
sudo ln -s /etc/nginx/sites-available/structpilot-labA /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx  # 开机自启
```

---

### 1.4 修改 Streamlit 配置

```bash
# 编辑配置文件
nano .streamlit/config.toml
```

修改为：
```toml
[server]
address = "127.0.0.1"  # 只监听本机，通过 Nginx 访问
port = 8501
```

---

### 1.5 启动 StructPilot

```bash
# 后台启动（推荐）
nohup streamlit run main.py > structpilot.log 2>&1 &

# 或使用 PM2（推荐生产环境）
pm2 start "streamlit run main.py" --name structpilot-labA
pm2 save
pm2 startup  # 开机自启
```

---

### 1.6 测试访问

**本组成员（192.168.1.x）访问：**
1. 浏览器输入：`http://192.168.1.100`
2. 弹出 Nginx 认证窗口，输入密码：`admin_labA / LabA_2024@Secure`
3. 进入 StructPilot 登录页面，输入内部账号：`admin / admin123`
4. ✅ 成功访问

**其他组成员（192.168.2.x）访问：**
1. 浏览器输入：`http://192.168.1.100`
2. ❌ 403 Forbidden（IP不在白名单内）

---

## 第二步：公共交流平台部署

### 2.1 选择部署位置

**方案A：独立服务器（推荐）**
- 在中立的服务器上部署（如学院公共服务器）
- IP: 192.168.0.100（任意不冲突的IP）

**方案B：云端部署**
- Streamlit Community Cloud（免费）
- 或自建云服务器

---

### 2.2 Nginx 配置（无IP限制）

```nginx
server {
    listen 80;
    server_name structpilot-public.local;

    # 无IP白名单，所有人可访问
    # 仅通过 StructPilot 内置登录保护

    location / {
        proxy_pass http://127.0.0.1:8500;  # 注意端口与私有空间不同
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

### 2.3 配置用户权限

编辑 `runtime/config/users.json`：

```json
{
  "users": [
    {
      "username": "public_viewer",
      "password_hash": "<hash>",
      "role": "member",
      "display_name": "访客",
      "can_view_all_public": true
    }
  ]
}
```

---

## 第三步：经验共享机制

### 3.1 修改经验数据结构

在私有实例中，管理员可以选择性公开某些经验：

**经验库 JSON 结构增强：**
```json
{
  "id": "lab_001",
  "title": "Motion Correction 报错 local motion too large",
  "author": "王师兄",
  "author_lab": "labA",  // 新增：来源课题组
  "visibility": "private",  // private | public
  "share_to_public_at": null,  // 公开时间戳
  "sensitivity": "low",  // low | medium | high
  "solution": "增大 B-factor 到 500...",
  "tags": ["运动校正", "漂移", "B-factor"]
}
```

---

### 3.2 公开经验的 UI（管理员功能）

在经验详情页增加按钮：

```python
# 伪代码示例
if st.session_state.role == "admin":
    if experience["visibility"] == "private":
        if st.button("📤 公开到交流平台"):
            # 1. 修改 visibility 为 public
            # 2. 同步到公共实例的数据库
            # 3. 记录公开时间和操作人
            sync_to_public_platform(experience)
            st.success("已公开到交流平台")
```

---

### 3.3 同步机制

**方案A：API 同步（实时）**
```python
import requests

def sync_to_public_platform(experience):
    """将经验同步到公共平台"""
    public_api_url = "http://192.168.0.100:8500/api/sync_experience"
    
    payload = {
        "experience": experience,
        "source_lab": "labA",
        "sync_time": datetime.now().isoformat()
    }
    
    response = requests.post(public_api_url, json=payload)
    return response.status_code == 200
```

**方案B：文件同步（定时）**
```bash
# cron 定时任务：每天凌晨同步公开经验
0 2 * * * rsync -avz /path/to/labA/public_experiences/ \
    public_server:/path/to/public_platform/experiences/labA/
```

---

## 第四步：论坛/讨论区（可选）

### 方案A：集成 GitHub Discussions

在公共实例中增加链接：
```python
st.markdown("""
### 💬 跨组讨论区

[前往 GitHub Discussions →](https://github.com/your-org/structpilot-forum/discussions)

- 提问/回答
- 经验分享
- 功能建议
""")
```

---

### 方案B：内置简易论坛

使用 Streamlit 组件构建：
```python
# 伪代码
posts = load_forum_posts()

for post in posts:
    with st.expander(f"[{post['lab']}] {post['title']}"):
        st.markdown(post['content'])
        st.caption(f"发布者：{post['author']} | {post['date']}")
        
        # 回复功能
        if st.button("回复", key=f"reply_{post['id']}"):
            reply_text = st.text_area("输入回复")
            if st.button("提交"):
                add_reply(post['id'], reply_text)
```

---

## 第五步：安全检查清单

### ✅ 私有空间检查

- [ ] IP白名单配置正确（只允许本组IP段）
- [ ] Nginx 密码认证启用
- [ ] StructPilot 内部账号密码强度足够
- [ ] 防火墙规则生效
- [ ] SSL证书配置（可选，HTTPS）

**测试：**
```bash
# 从其他组IP访问（应该被拒绝）
curl -I http://192.168.1.100
# 预期：403 Forbidden

# 从本组IP访问（应该要求密码）
curl -I http://192.168.1.100
# 预期：401 Unauthorized（需要密码）
```

---

### ✅ 公共平台检查

- [ ] 所有IP都能访问
- [ ] 只显示"已公开"的经验
- [ ] 私有经验不可见
- [ ] 用户权限正确

---

## 常见问题

### Q1: 如果需要临时允许其他组访问怎么办？

**场景：** 课题组A和B需要临时协作。

**解决方案：**
```nginx
# 临时修改 Nginx 配置
allow 192.168.1.0/24;  # 本组
allow 192.168.2.0/24;  # 临时允许B组
deny all;
```

重启 Nginx：
```bash
sudo systemctl reload nginx
```

---

### Q2: 出差时如何访问私有空间？

**方案A：VPN**
1. 连接学校VPN
2. 获得学校内网IP
3. 正常访问

**方案B：临时解除IP限制**
```nginx
# 临时注释IP白名单（仅Nginx密码保护）
# allow 192.168.1.0/24;
# deny all;
```

---

### Q3: 如何撤销已公开的经验？

**操作：**
1. 在私有实例中找到该经验
2. 点击"🔒 撤销公开"
3. 系统自动从公共平台移除

---

## 性能和维护

### 监控脚本

```bash
# 检查所有实例状态
./monitor_performance.sh

# 查看 Nginx 日志
sudo tail -f /var/log/nginx/access.log

# 查看 StructPilot 日志
tail -f structpilot.log
```

---

### 定期任务

| 任务 | 频率 | 命令 |
|------|------|------|
| 备份数据 | 每天 | `./backup_data.sh` |
| 同步公开经验 | 每小时 | `./sync_public_experiences.sh` |
| 检查更新 | 每周 | `git pull origin main` |
| 密码轮换 | 每季度 | `python change_password.py` |

---

## 总结

**你现在拥有：**
1. ✅ 每个课题组独立的私有空间（IP白名单 + 密码双重保护）
2. ✅ 公共交流平台（跨组协作，无IP限制）
3. ✅ 选择性经验共享机制（管理员控制）
4. ✅ 去敏化的 RELION 教程（可填空式）

**安全级别：**
- 私有空间：🔒🔒🔒🔒🔒（最高）
- 公共平台：🔒🔒🔒（密码保护）

**下一步：**
- 部署你的第一个私有实例
- 配置公共交流平台
- 邀请课题组成员测试
