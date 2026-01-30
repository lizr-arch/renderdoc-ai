@echo off
setlocal
set PY36=D:\Program Files\Python36\python.exe
echo === Installing Sphinx and dependencies for Python 3.6 ===
"%PY36%" -m pip install sphinx sphinx_paramlinks sphinx_rtd_theme --upgrade
echo.
echo === Verifying installation ===
"%PY36%" -m sphinx --version
endlocal
