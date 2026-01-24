@echo off
setlocal
set PY36=D:\Program Files\Python36\python.exe
set SPHINXBUILD="%PY36%" -m sphinx

echo === Building RenderDoc HTML Documentation ===
cd /d d:\Code\git\renderdoc\docs
%SPHINXBUILD% -b html -d ..\Documentation\doctrees . ..\Documentation\html

echo.
echo === Build complete ===
if exist "..\Documentation\html\index.html" (
    echo SUCCESS: Documentation built at d:\Code\git\renderdoc\Documentation\html\index.html
) else (
    echo WARNING: index.html not found, check for errors above
)
endlocal
