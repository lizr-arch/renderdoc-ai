@echo off
setlocal

REM Default preset for quick visual verification.
set "DEFAULT_RDC=D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc"
set "DEFAULT_OUT=D:\backup\endfield_report"

if "%~1"=="" (
  set "RDC_FILE=%DEFAULT_RDC%"
) else (
  set "RDC_FILE=%~1"
)

if "%~2"=="" (
  set "OUT_DIR=%DEFAULT_OUT%"
) else (
  set "OUT_DIR=%~2"
)

echo [one-click preset] rdc: "%RDC_FILE%"
echo [one-click preset] out: "%OUT_DIR%"

py -3 "%~dp0one_click_bundle_report.py" "%RDC_FILE%" -o "%OUT_DIR%" --smoke-no-fail --smoke-no-screenshots
if errorlevel 1 (
  echo [one-click preset] failed with exit code %errorlevel%
  exit /b %errorlevel%
)

set "INDEX_HTML=%OUT_DIR%\index.html"
if exist "%INDEX_HTML%" (
  start "" "%INDEX_HTML%"
)

echo [one-click preset] done
exit /b 0
