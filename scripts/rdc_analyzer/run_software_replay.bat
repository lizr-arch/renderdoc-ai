@echo off
REM ============================================================
REM RenderDoc 软件渲染器回放启动脚本
REM 
REM 功能: 使用 Lavapipe/SwiftShader 软件渲染器回放 RDC 文件
REM       解决跨 GPU 回放兼容性问题
REM ============================================================

setlocal EnableDelayedExpansion

REM 配置路径
set "RENDERDOC_EXE=C:\Program Files\RenderDoc\qrenderdoc.exe"
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_FILE=%SCRIPT_DIR%poc_swiftshader_replay.py"

REM 软件渲染器 ICD 路径 (从 Android SDK Emulator 获取)
set "LAVAPIPE_ICD=C:\Users\lizhirui01\AppData\Local\Android\Sdk\emulator\lib64\vulkan\lvp_icd.x86_64.json"
set "SWIFTSHADER_ICD=C:\Users\lizhirui01\AppData\Local\Android\Sdk\emulator\lib64\vulkan\vk_swiftshader_icd.json"

echo ============================================================
echo RenderDoc 软件渲染器回放
echo ============================================================
echo.

REM 选择渲染器
echo 请选择软件渲染器:
echo   [1] Lavapipe (Mesa LLVMpipe) - Vulkan 1.3 - 推荐
echo   [2] SwiftShader (Google) - Vulkan 1.0
echo   [3] 使用默认 GPU (不修改环境变量)
echo.
set /p CHOICE="输入选项 (1/2/3): "

if "%CHOICE%"=="1" (
    set "VK_ICD_FILENAMES=%LAVAPIPE_ICD%"
    echo.
    echo 已选择: Lavapipe
) else if "%CHOICE%"=="2" (
    set "VK_ICD_FILENAMES=%SWIFTSHADER_ICD%"
    echo.
    echo 已选择: SwiftShader
) else (
    echo.
    echo 已选择: 默认 GPU
)

echo.
echo VK_ICD_FILENAMES = %VK_ICD_FILENAMES%
echo.

REM 检查文件存在
if not exist "%RENDERDOC_EXE%" (
    echo [ERROR] RenderDoc 未找到: %RENDERDOC_EXE%
    goto :error
)

if not exist "%SCRIPT_FILE%" (
    echo [ERROR] 脚本文件未找到: %SCRIPT_FILE%
    goto :error
)

if defined VK_ICD_FILENAMES (
    if not exist "%VK_ICD_FILENAMES%" (
        echo [ERROR] ICD 文件未找到: %VK_ICD_FILENAMES%
        goto :error
    )
)

REM 运行 RenderDoc
echo 正在启动 RenderDoc...
echo 命令: "%RENDERDOC_EXE%" --script "%SCRIPT_FILE%"
echo.
echo ============================================================
echo.

"%RENDERDOC_EXE%" --script "%SCRIPT_FILE%"

echo.
echo ============================================================
echo RenderDoc 已退出
echo.
echo 日志文件: D:\backup\software_replay_log.txt
echo 输出目录: D:\backup\rt_export\
echo ============================================================

goto :end

:error
echo.
echo [ERROR] 启动失败
pause
exit /b 1

:end
pause
