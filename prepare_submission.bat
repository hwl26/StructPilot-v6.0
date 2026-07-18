@echo off
REM StructPilot v5.1 提交打包脚本
REM 用于清理临时文件并打包提交版本

echo ================================================
echo StructPilot v5.1 提交打包工具
echo ================================================
echo.

REM 设置项目目录
set PROJECT_DIR=%~dp0
cd /d "%PROJECT_DIR%"

echo [1/4] 清理 Python 缓存文件...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc 2>nul
del /s /q *.pyo 2>nul
echo ✓ Python 缓存已清理

echo.
echo [2/4] 清理运行时临时文件...
if exist "runtime\logs\*" del /q "runtime\logs\*" 2>nul
if exist "runtime\cache\*" del /q "runtime\cache\*" 2>nul
echo ✓ 运行时文件已清理

echo.
echo [3/4] 检查敏感文件...
if exist ".env" (
    echo ⚠ 警告: 发现 .env 文件，请确认是否包含敏感信息
    echo   如包含 API Key 等敏感信息，请手动删除或修改
    pause
)
echo ✓ 敏感文件检查完成

echo.
echo [4/4] 创建提交压缩包...

REM 使用 PowerShell 压缩
powershell -Command "& {Compress-Archive -Path '%PROJECT_DIR%' -DestinationPath '%PROJECT_DIR%..\StructPilot_v5.1_Submission.zip' -Force}"

if %errorlevel% equ 0 (
    echo ✓ 压缩包创建成功！
    echo.
    echo 提交文件位置: %PROJECT_DIR%..\StructPilot_v5.1_Submission.zip
    echo.
    echo ================================================
    echo 提交清单：
    echo ================================================
    echo ✓ 源代码完整
    echo ✓ requirements.txt
    echo ✓ README.md
    echo ✓ OPTIMIZATION_SUMMARY.md
    echo ✓ SUBMISSION_NOTES.md
    echo ✓ SUBMISSION_GUIDE.md
    echo ✓ knowledge_base/ 目录
    echo ================================================
    echo.
    echo 下一步：
    echo 1. 验证压缩包大小和内容
    echo 2. 阅读 SUBMISSION_GUIDE.md 了解提交方式
    echo 3. 根据比赛要求选择提交方式（邮件/平台/Git）
    echo.
) else (
    echo ✗ 压缩失败，请手动打包
    echo.
    echo 手动打包步骤：
    echo 1. 右键点击 StructPilot_v5.1 文件夹
    echo 2. 选择"发送到" -> "压缩(zipped)文件夹"
    echo 3. 重命名为 StructPilot_v5.1_Submission.zip
)

echo.
pause
