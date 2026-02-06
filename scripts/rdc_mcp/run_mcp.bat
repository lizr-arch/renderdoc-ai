@echo off
chcp 65001 >nul

:: 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"

:: 启动 MCP 服务器
py -3 "%SCRIPT_DIR%rdc_mcp\rdc_mcp.py" %*
