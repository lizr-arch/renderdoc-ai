@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ============================================================
:: RDC Analyzer - 启动脚本
:: ============================================================
:: 用法:
::   run_analyzer.bat analyze capture.rdc -o output/
::   run_analyzer.bat extract-resources capture.rdc --all
::   run_analyzer.bat --help
::
:: 说明:
::   此脚本自动配置 RenderDoc 环境，无需手动设置 PATH
:: ============================================================

:: 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:: 设置 RenderDoc DLL 搜索路径
set "BIN_DIR=%SCRIPT_DIR%\bin"
set "ANALYZER_DIR=%SCRIPT_DIR%\analyzer"

:: 检查必要文件
if not exist "%BIN_DIR%\renderdoc.dll" (
    echo [错误] 找不到 renderdoc.dll
    echo        请确保 bin 目录包含完整的 RenderDoc 文件
    exit /b 1
)

if not exist "%BIN_DIR%\renderdoc.pyd" (
    echo [错误] 找不到 renderdoc.pyd
    echo        请确保 bin 目录包含 Python 绑定文件
    exit /b 1
)

:: 设置环境变量
set "PATH=%BIN_DIR%;%PATH%"
set "PYTHONPATH=%BIN_DIR%;%ANALYZER_DIR%;%PYTHONPATH%"

:: 显示帮助信息
if "%~1"=="" (
    echo RDC Analyzer - RenderDoc 帧分析工具
    echo.
    echo 用法:
    echo   %~nx0 ^<command^> [options]
    echo.
    echo 命令:
    echo   analyze            分析 RDC 文件并生成报告
    echo   extract-resources  从 RDC 提取资源 ^(纹理、Shader^)
    echo   compare            对比两个 RDC/JSON 文件
    echo   rules              列出可用的分析规则
    echo.
    echo 示例:
    echo   %~nx0 analyze capture.rdc -o ./output
    echo   %~nx0 extract-resources capture.rdc --all
    echo   %~nx0 --help
    echo.
    exit /b 0
)

:: 查找 Python 3.6 解释器
:: 优先级: 嵌入式 Python > py -3.6 > python3.6

if exist "%BIN_DIR%\python.exe" (
    set "PYTHON_EXE=%BIN_DIR%\python.exe"
    goto :run
)

:: 尝试 py launcher
where py >nul 2>&1
if %errorlevel%==0 (
    py -3.6 --version >nul 2>&1
    if %errorlevel%==0 (
        set "PYTHON_EXE=py -3.6"
        goto :run
    )
)

:: 尝试直接调用 python3.6
where python3.6 >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_EXE=python3.6"
    goto :run
)

:: 尝试 python (可能是 3.6)
where python >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do (
        echo %%v | findstr /b "3.6" >nul
        if !errorlevel!==0 (
            set "PYTHON_EXE=python"
            goto :run
        )
    )
)

echo [错误] 找不到 Python 3.6
echo        RenderDoc Python 绑定需要 Python 3.6
echo.
echo 解决方案:
echo   1. 安装 Python 3.6: https://www.python.org/downloads/release/python-368/
echo   2. 或者使用 py launcher: py -3.6
exit /b 1

:run
:: 运行分析器
%PYTHON_EXE% -m analyzer %*
exit /b %errorlevel%
