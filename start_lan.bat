@echo off
REM StructPilot 局域网启动脚本 (Windows)

echo ==========================================
echo StructPilot v6.0 正在启动...
echo ==========================================
echo.

REM 获取本机 IP 地址
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /R "IPv4.*192.168"') do (
    set SERVER_IP=%%a
    goto :found
)
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /R "IPv4.*10\."') do (
    set SERVER_IP=%%a
    goto :found
)
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /R "IPv4.*172\."') do (
    set SERVER_IP=%%a
    goto :found
)

:found
REM 去除空格
set SERVER_IP=%SERVER_IP: =%

echo 📡 局域网访问地址：
echo    http://%SERVER_IP%:8501
echo.
echo 🔐 默认管理员账号：
echo    用户名: admin
echo    密码: admin123
echo.
echo 💡 局域网内的其他电脑可以通过上述地址访问
echo    （确保防火墙允许 8501 端口）
echo.
echo ==========================================
echo.

REM 启动 Streamlit
streamlit run main.py --server.address 0.0.0.0 --server.port 8501
pause
