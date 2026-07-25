#!/bin/bash
# StructPilot 性能监控脚本

echo "========== StructPilot 性能监控 =========="
echo ""

# 1. 检查进程数量（估算并发用户）
STREAMLIT_PROCS=$(pgrep -f "streamlit run" | wc -l)
echo "📊 Streamlit 进程数: $STREAMLIT_PROCS"

# 2. 内存使用
MEMORY_USAGE=$(ps aux | grep "[s]treamlit run" | awk '{sum+=$6} END {print sum/1024}')
echo "💾 内存占用: ${MEMORY_USAGE} MB"

# 3. CPU使用率
CPU_USAGE=$(ps aux | grep "[s]treamlit run" | awk '{sum+=$3} END {print sum}')
echo "⚡ CPU使用率: ${CPU_USAGE}%"

# 4. 连接数（估算在线用户）
if command -v netstat &> /dev/null; then
    CONNECTIONS=$(netstat -an | grep :8501 | grep ESTABLISHED | wc -l)
    echo "👥 当前连接数: $CONNECTIONS"
elif command -v ss &> /dev/null; then
    CONNECTIONS=$(ss -an | grep :8501 | grep ESTAB | wc -l)
    echo "👥 当前连接数: $CONNECTIONS"
fi

# 5. 性能评估
echo ""
echo "--- 性能评估 ---"
if (( $(echo "$MEMORY_USAGE > 4000" | bc -l) )); then
    echo "⚠️  警告：内存占用过高（>4GB）"
fi

if (( $(echo "$CPU_USAGE > 80" | bc -l) )); then
    echo "⚠️  警告：CPU负载过高（>80%）"
fi

if [ "$CONNECTIONS" -gt 20 ]; then
    echo "⚠️  警告：并发连接数较高（>20），建议优化"
fi

if [ "$CONNECTIONS" -lt 10 ]; then
    echo "✅ 性能良好，负载正常"
fi

echo ""
echo "=========================================="
