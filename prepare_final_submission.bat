@echo off
REM StructPilot v5.1 最终提交打包脚本
REM 清理临时文件并创建提交压缩包

echo ========================================
echo StructPilot v5.1 最终提交打包工具
echo ========================================
echo.
echo 正在准备提交文件...
echo.

cd /d "%~dp0"

REM 1. 清理 Python 缓存
echo [1/5] 清理 Python 缓存文件...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc 2>nul
del /s /q *.pyo 2>nul
echo   √ Python 缓存已清理

REM 2. 清理运行时数据（保留目录结构）
echo.
echo [2/5] 清理运行时数据...
if exist "runtime\logs\*.log" del /q "runtime\logs\*.log" 2>nul
if exist "runtime\cache\*" del /q "runtime\cache\*" 2>nul
if exist "memory\*.sqlite3-journal" del /q "memory\*.sqlite3-journal" 2>nul
echo   √ 运行时数据已清理

REM 3. 清理测试输出
echo.
echo [3/5] 清理测试输出...
if exist "tests\.pytest_cache" rd /s /q "tests\.pytest_cache" 2>nul
if exist ".pytest_cache" rd /s /q ".pytest_cache" 2>nul
if exist "htmlcov" rd /s /q "htmlcov" 2>nul
if exist ".coverage" del /q ".coverage" 2>nul
echo   √ 测试输出已清理

REM 4. 检查敏感文件
echo.
echo [4/5] 检查敏感文件...
set HAS_SENSITIVE=0
if exist ".env" (
    echo   ⚠ 警告: 发现 .env 文件
    echo      请确认是否包含 API Key 等敏感信息
    set HAS_SENSITIVE=1
)
if exist "config\*.key" (
    echo   ⚠ 警告: 发现 .key 文件
    set HAS_SENSITIVE=1
)
if %HAS_SENSITIVE%==0 (
    echo   √ 未发现敏感文件
) else (
    echo.
    echo   请按任意键继续，或 Ctrl+C 取消
    pause >nul
)

REM 5. 创建提交压缩包
echo.
echo [5/5] 创建提交压缩包...
set TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set OUTPUT_NAME=StructPilot_v5.1_Final_Submission_%TIMESTAMP%.zip

cd ..
powershell -Command "& {Compress-Archive -Path 'StructPilot_v5.1' -DestinationPath '%OUTPUT_NAME%' -Force}"

if %errorlevel% equ 0 (
    echo   √ 压缩包创建成功！
    echo.
    echo ========================================
    echo 提交文件信息
    echo ========================================
    for %%F in ("%OUTPUT_NAME%") do (
        echo 文件名: %%~nxF
        echo 大小: %%~zF 字节
        echo 位置: %%~dpF
    )
    echo ========================================
    echo.
    echo ✓ 打包完成！
    echo.
    echo 📋 提交清单：
    echo   √ 完整源代码
    echo   √ requirements.txt
    echo   √ README.md
    echo   √ OPTIMIZATION_SUMMARY.md
    echo   √ SUBMISSION_NOTES.md
    echo   √ 知识库文件
    echo   √ 启动脚本
    echo.
    echo 下一步：
    echo 1. 验证压缩包内容
    echo 2. 填写 SUBMISSION_NOTES.md 中的团队信息
    echo 3. 根据比赛要求提交（邮件/平台/Git）
    echo.
    echo 📧 提交方式参考 SUBMISSION_GUIDE.md
    echo.
) else (
    echo   ✗ 压缩失败
    echo.
    echo 请手动打包：
    echo 1. 打开上级目录
    echo 2. 右键 StructPilot_v5.1 文件夹
    echo 3. 选择"发送到" - "压缩文件夹"
)

echo.
pause
