# StructPilot 部署指南总览

> 完整的网站部署方案 - 从本地到公网

---

## 📚 文档索引

| 文档 | 适用场景 | 难度 | 时间 |
|------|---------|------|------|
| [01_部署方案概览.md](01_部署方案概览.md) | 了解所有方案，选择最适合的 | ⭐ | 10 分钟 |
| [03_云服务器部署.md](03_云服务器部署.md) | 生产环境，完全控制 | ⭐⭐⭐ | 60 分钟 |
| [04_Docker_部署.md](04_Docker_部署.md) | 容器化，易于迁移 | ⭐⭐⭐⭐ | 45 分钟 |
| [deploy.sh](deploy.sh) | 一键自动部署脚本 | ⭐ | 15 分钟 |

---

## 🚀 快速开始

### 方案 1：一键部署脚本（最快）

**前提条件**：
- Ubuntu 22.04 服务器
- 已绑定域名到服务器 IP
- Root 权限

**部署步骤**：

```bash
# 1. 上传代码到服务器
scp -r StructPilot_v6/ root@你的服务器IP:/tmp/

# 2. 连接服务器
ssh root@你的服务器IP

# 3. 运行部署脚本
cd /tmp/StructPilot_v6/部署指南
bash deploy.sh

# 4. 按提示输入域名和邮箱
# 5. 等待自动部署完成（约 15 分钟）
# 6. 访问 https://你的域名
```

### 方案 2：手动部署（详细控制）

阅读 [03_云服务器部署.md](03_云服务器部署.md)，按步骤手动配置。

### 方案 3：Docker 部署（容器化）

阅读 [04_Docker_部署.md](04_Docker_部署.md)，使用 Docker Compose 部署。

---

## 🎯 方案选择建议

### 你应该选择哪个方案？

#### 选择云服务器部署，如果：
- ✅ 需要完全控制服务器
- ✅ 对 Linux 运维有一定了解
- ✅ 预算充足（¥150-500/月）
- ✅ 需要长期稳定运行

**推荐指数**：⭐⭐⭐⭐⭐  
**参考文档**：[03_云服务器部署.md](03_云服务器部署.md)

#### 选择 Docker 部署，如果：
- ✅ 团队熟悉 Docker
- ✅ 需要在多个环境部署
- ✅ 追求环境一致性
- ✅ 计划使用 Kubernetes

**推荐指数**：⭐⭐⭐⭐  
**参考文档**：[04_Docker_部署.md](04_Docker_部署.md)

#### 选择一键部署脚本，如果：
- ✅ 快速上线，节省时间
- ✅ 不熟悉 Linux 运维
- ✅ Ubuntu 22.04 服务器
- ✅ 标准需求，无特殊定制

**推荐指数**：⭐⭐⭐⭐⭐  
**参考文档**：直接运行 [deploy.sh](deploy.sh)

---

## 📋 部署前检查清单

### 服务器准备

- [ ] 已购买云服务器（阿里云/腾讯云/华为云等）
- [ ] 操作系统：Ubuntu 22.04 LTS（推荐）
- [ ] 配置：至少 2 核 4GB（推荐 4 核 8GB）
- [ ] 已获得服务器 IP 地址
- [ ] 可以通过 SSH 连接服务器

### 域名配置

- [ ] 已购买域名
- [ ] 已完成域名备案（国内服务器必需）
- [ ] 已添加 DNS 记录（A 记录指向服务器 IP）
- [ ] DNS 已生效（ping 域名能解析到正确 IP）

### 代码准备

- [ ] 代码已上传到服务器或 GitHub
- [ ] `.env.example` 文件存在
- [ ] `requirements.txt` 完整
- [ ] 排除了敏感文件（`.env`、`runtime/`、`.venv/`）

### API 配置

- [ ] 已获取 LLM API Key
- [ ] 已获取 Embedding API Key（可选）
- [ ] 已获取 Audio API Key（可选）
- [ ] 已测试 API Key 可用性

---

## 🛠️ 部署后配置

### 1. 配置 API Key

```bash
# 编辑配置文件
nano /opt/structpilot/app/.env

# 填入实际的 API Key
STRUCTPILOT_LLM_API_KEY=你的实际密钥
STRUCTPILOT_EMBEDDING_API_KEY=你的实际密钥
STRUCTPILOT_AUDIO_API_KEY=你的实际密钥

# 重启应用
supervisorctl restart structpilot
```

### 2. 测试访问

```bash
# 测试 HTTP（应自动跳转到 HTTPS）
curl http://你的域名

# 测试 HTTPS
curl https://你的域名

# 浏览器访问
# https://你的域名
```

### 3. 查看日志

```bash
# 应用日志
tail -f /var/log/structpilot.log

# Nginx 访问日志
tail -f /var/log/nginx/access.log

# Nginx 错误日志
tail -f /var/log/nginx/error.log
```

---

## 🔧 常见问题

### Q1: 部署脚本执行失败

**检查项**：
```bash
# 检查系统版本
lsb_release -a
# 应显示 Ubuntu 22.04

# 检查网络连接
ping -c 4 baidu.com

# 检查权限
whoami
# 应显示 root
```

### Q2: 访问域名显示 502 错误

**排查步骤**：

```bash
# 1. 检查应用是否运行
supervisorctl status structpilot

# 2. 如果状态是 STOPPED，查看日志
tail -100 /var/log/structpilot.log

# 3. 手动启动测试
cd /opt/structpilot/app
source .venv/bin/activate
streamlit run main.py

# 4. 如果能正常启动，重启 supervisor
supervisorctl restart structpilot
```

### Q3: SSL 证书申请失败

**原因**：
- 域名未解析到服务器
- 80 端口被占用
- certbot 服务异常

**解决**：

```bash
# 1. 测试域名解析
ping 你的域名

# 2. 检查 80 端口
netstat -tulnp | grep :80

# 3. 重新申请证书
certbot --nginx -d 你的域名 --force-renewal
```

### Q4: 上传文件失败

**解决**：

```bash
# 检查 Nginx 文件大小限制
grep client_max_body_size /etc/nginx/sites-available/structpilot

# 如果没有或值太小，添加：
# client_max_body_size 200M;

# 重载 Nginx
nginx -t && systemctl reload nginx
```

---

## 📊 性能监控

### 系统资源监控

```bash
# 安装 htop
apt install htop -y

# 查看实时资源使用
htop

# 查看内存使用
free -h

# 查看磁盘使用
df -h
```

### 应用监控

```bash
# 查看进程状态
ps aux | grep streamlit

# 查看端口占用
netstat -tulnp | grep 8501

# 查看连接数
netstat -an | grep :8501 | wc -l
```

---

## 🔐 安全加固

### 1. 更改 SSH 端口

```bash
# 编辑 SSH 配置
nano /etc/ssh/sshd_config

# 修改端口（例如改为 2222）
Port 2222

# 重启 SSH
systemctl restart sshd

# 更新防火墙规则
ufw allow 2222/tcp
ufw delete allow 22/tcp
```

### 2. 禁用 root 登录

```bash
# 创建普通用户
adduser admin
usermod -aG sudo admin

# 禁用 root SSH 登录
nano /etc/ssh/sshd_config
# PermitRootLogin no

systemctl restart sshd
```

### 3. 配置自动备份

```bash
# 参考 03_云服务器部署.md 中的备份脚本
```

---

## 🔄 更新应用

### 方式 1：Git 拉取更新

```bash
cd /opt/structpilot/app
git pull
source .venv/bin/activate
pip install -r requirements.txt
supervisorctl restart structpilot
```

### 方式 2：上传新版本

```bash
# 本地打包
tar -czf structpilot_new.tar.gz StructPilot_v6/

# 上传到服务器
scp structpilot_new.tar.gz root@服务器IP:/tmp/

# 在服务器上解压和替换
cd /opt/structpilot
supervisorctl stop structpilot
rm -rf app.bak
mv app app.bak
tar -xzf /tmp/structpilot_new.tar.gz
mv StructPilot_v6 app
supervisorctl start structpilot
```

---

## 💡 优化建议

### 1. 启用 Redis 缓存（可选）

```bash
# 安装 Redis
apt install redis-server -y

# 在应用中配置 Redis
# 参考 04_Docker_部署.md 中的 Redis 集成
```

### 2. 配置 CDN（可选）

- 阿里云 CDN
- 腾讯云 CDN
- Cloudflare CDN

### 3. 负载均衡（大流量）

使用 Nginx 或云服务商的负载均衡服务分发流量到多台服务器。

---

## 📞 技术支持

遇到问题时：

1. **查看文档**：先查阅对应的部署文档
2. **查看日志**：检查应用和 Nginx 日志
3. **搜索错误**：在搜索引擎查找错误信息
4. **反馈问题**：提交 Issue 或联系技术支持

---

## 📈 下一步

部署完成后，建议：

1. ✅ 完整测试所有功能
2. ✅ 配置监控和告警
3. ✅ 设置定期备份
4. ✅ 编写运维文档
5. ✅ 培训使用人员

---

**文档版本**：v1.0  
**最后更新**：2026-07-18  
**维护者**：StructPilot Team
