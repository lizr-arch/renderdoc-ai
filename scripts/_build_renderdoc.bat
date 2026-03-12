@echo off
REM RenderDoc Build Script
REM 使用 VS 2022 编译 RenderDoc

set MSBUILD="E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\amd64\MSBuild.exe"
set SLN=d:\Code\git\renderdoc\renderdoc.sln

echo ============================================
echo Building RenderDoc (Development, x64)
echo ============================================
echo MSBuild: %MSBUILD%
echo Solution: %SLN%
echo ============================================

%MSBUILD% %SLN% /p:Configuration=Development /p:Platform=x64 /m /v:minimal

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================
    echo BUILD SUCCEEDED
    echo ============================================
    echo Output: d:\Code\git\renderdoc\x64\Development\
) else (
    echo.
    echo ============================================
    echo BUILD FAILED with error %ERRORLEVEL%
    echo ============================================
)
