#!/bin/bash
# StructPilot 局域网启动脚本

# 获取服务器 IP 地址
echo "=========================================="
echo "StructPilot v6.0 正在启动..."
echo "=========================================="

# 检测操作系统
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    SERVER_IP=$(hostname -I | awk '{print $1}')
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    SERVER_IP=$(ipconfig getifaddr en0)
else
    # Windows (Git Bash)
    SERVER_IP=$(ipconfig | grep "IPv4" | grep -v "127.0.0.1" | head -1 | awk '{print $NF}')
fi

echo ""
echo "📡 局域网访问地址："
echo "   http://${SERVER_IP}:8501"
echo ""
echo "🔐 默认管理员账号："
echo "   用户名: admin"
echo "   管理员密码: 请使用私有 Secrets 中配置的强密码"
echo ""
echo "💡 局域网内的其他电脑可以通过上述地址访问"
echo "   （确保防火墙允许 8501 端口）"
echo ""
echo "=========================================="
echo ""

# 启动 Streamlit
streamlit run main.py --server.address 0.0.0.0 --server.port 8501
