@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   RDC-AI-Analyzer 安装脚本
echo ============================================
echo.

:: 检查 Python
py -3 --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python 3，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [√] Python 3 已安装
py -3 --version

:: 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: 安装依赖
echo.
echo [*] 安装 Python 依赖...
py -3 -m pip install -r "%SCRIPT_DIR%rdc_mcp\requirements.txt" --quiet

if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

echo [√] 依赖安装完成

:: 检查 mcp 模块
py -3 -c "import mcp" >nul 2>&1
if errorlevel 1 (
    echo [警告] MCP 模块未正确安装，尝试重新安装...
    py -3 -m pip install mcp --quiet
)

:: 生成配置
echo.
echo ============================================
echo   Claude Desktop 配置
echo ============================================
echo.
echo 请将以下配置添加到 Claude Desktop 的配置文件:
echo.
echo 配置文件位置:
echo   %%APPDATA%%\Claude\claude_desktop_config.json
echo.
echo 配置内容:
echo {
echo   "mcpServers": {
echo     "rdc_analyzer": {
echo       "command": "py",
echo       "args": ["-3", "%SCRIPT_DIR%rdc_mcp\rdc_mcp.py"]
echo     }
echo   }
echo }
echo.
echo ============================================
echo.
echo 安装完成！配置 Claude Desktop 后重启即可使用。
echo.
pause
