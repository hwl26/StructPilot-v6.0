#!/bin/bash

# StructPilot 一键部署脚本（Ubuntu 22.04）
# 使用方法：sudo bash deploy.sh

set -e

echo "========================================="
echo "  StructPilot 自动部署脚本"
echo "  适用于：Ubuntu 22.04 LTS"
echo "========================================="
echo ""

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 root 权限运行此脚本"
    echo "   使用命令：sudo bash deploy.sh"
    exit 1
fi

# 配置变量
APP_DIR="/opt/structpilot"
APP_NAME="structpilot"
DOMAIN=""
EMAIL=""

# 询问域名
echo "📝 请输入域名（例如：structpilot.yourdomain.com）"
read -p "   域名: " DOMAIN

if [ -z "$DOMAIN" ]; then
    echo "❌ 域名不能为空"
    exit 1
fi

# 询问邮箱（用于 SSL 证书）
echo ""
echo "📝 请输入邮箱地址（用于 SSL 证书通知）"
read -p "   邮箱: " EMAIL

if [ -z "$EMAIL" ]; then
    echo "❌ 邮箱不能为空"
    exit 1
fi

echo ""
echo "========================================="
echo "  开始部署..."
echo "========================================="
echo ""

# 1. 更新系统
echo "📦 [1/10] 更新系统..."
apt update && apt upgrade -y

# 2. 安装依赖
echo "📦 [2/10] 安装依赖..."
apt install -y \
    python3.10 \
    python3.10-venv \
    python3-pip \
    git \
    nginx \
    supervisor \
    certbot \
    python3-certbot-nginx \
    curl

# 3. 创建应用目录
echo "📂 [3/10] 创建应用目录..."
mkdir -p $APP_DIR
cd $APP_DIR

# 4. 下载代码
echo "⬇️  [4/10] 下载代码..."
if [ -d "$APP_DIR/app" ]; then
    echo "   应用目录已存在，跳过下载"
else
    echo "   请选择下载方式："
    echo "   1) 从 GitHub 克隆"
    echo "   2) 从本地上传"
    read -p "   选择 (1/2): " DOWNLOAD_METHOD

    if [ "$DOWNLOAD_METHOD" == "1" ]; then
        read -p "   请输入 GitHub 仓库地址: " GIT_REPO
        git clone $GIT_REPO app
    else
        echo "   请先上传代码到 $APP_DIR/app/"
        echo "   上传命令示例："
        echo "   scp -r StructPilot_v6/ root@$DOMAIN:$APP_DIR/app/"
        read -p "   上传完成后按回车继续..."
    fi
fi

cd $APP_DIR/app

# 5. 创建虚拟环境
echo "🐍 [5/10] 创建 Python 虚拟环境..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 6. 配置环境变量
echo "⚙️  [6/10] 配置环境变量..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "   ⚠️  请编辑 .env 文件，填入你的 API Key"
    echo "   编辑命令：nano $APP_DIR/app/.env"
    read -p "   编辑完成后按回车继续..."
fi

# 创建运行目录
mkdir -p runtime/{memory,cache,uploads}
chmod 750 runtime -R

# 7. 配置 Supervisor
echo "👷 [7/10] 配置 Supervisor..."
cat > /etc/supervisor/conf.d/$APP_NAME.conf << EOF
[program:$APP_NAME]
directory=$APP_DIR/app
command=$APP_DIR/app/.venv/bin/streamlit run main.py --server.port 8501 --server.address 127.0.0.1
user=root
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/$APP_NAME.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=5
EOF

supervisorctl reread
supervisorctl update
supervisorctl start $APP_NAME

echo "   ✅ Supervisor 配置完成"
sleep 3

# 8. 配置 Nginx
echo "🌐 [8/10] 配置 Nginx..."
cat > /etc/nginx/sites-available/$APP_NAME << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }

    client_max_body_size 200M;
}
EOF

ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

echo "   ✅ Nginx 配置完成"

# 9. 配置 SSL 证书
echo "🔒 [9/10] 配置 SSL 证书..."
certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m $EMAIL --redirect

echo "   ✅ SSL 证书配置完成"

# 10. 配置防火墙
echo "🔥 [10/10] 配置防火墙..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
echo "y" | ufw enable

echo "   ✅ 防火墙配置完成"

# 完成
echo ""
echo "========================================="
echo "  🎉 部署完成！"
echo "========================================="
echo ""
echo "访问地址："
echo "  https://$DOMAIN"
echo ""
echo "常用管理命令："
echo "  查看状态：supervisorctl status $APP_NAME"
echo "  重启应用：supervisorctl restart $APP_NAME"
echo "  查看日志：tail -f /var/log/$APP_NAME.log"
echo ""
echo "下一步："
echo "  1. 访问 https://$DOMAIN 验证部署"
echo "  2. 编辑 $APP_DIR/app/.env 配置 API Key"
echo "  3. 重启应用：supervisorctl restart $APP_NAME"
echo ""
echo "========================================="
