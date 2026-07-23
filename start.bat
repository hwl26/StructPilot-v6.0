@echo off
chcp 65001 > nul
echo ================================
echo   StructPilot v6.0 Final
echo   三模式智能陪跑系统
echo ================================
echo.
echo [1/2] 检查环境...

python --version
if %errorlevel% neq 0 (
    echo [ERROR] Python 未安装或未添加到 PATH
    pause
    exit /b 1
)

pip show streamlit > nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] Streamlit 未安装，正在安装...
    pip install streamlit
)

echo.
echo [2/2] 启动应用...
echo.
echo 应用将在浏览器中自动打开
echo 访问地址: http://localhost:8501
echo.
echo 按 Ctrl+C 停止应用
echo ================================
echo.

streamlit run main.py

pause
