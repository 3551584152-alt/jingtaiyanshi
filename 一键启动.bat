@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title 智枢词训 - 一键启动

echo ============================================
echo   智枢词训 CET-4 自适应词汇学习系统
echo ============================================
echo.

set "PORT=8002"
set "PYTHON="
where py >nul 2>&1 && py -3 --version >nul 2>&1 && set "PYTHON=py -3"
if not defined PYTHON (
  where python >nul 2>&1 && python --version >nul 2>&1 && set "PYTHON=python"
)
if not defined PYTHON (
  echo [错误] 未找到 Python。请安装 Python 3.12 或更高版本，并勾选 Add Python to PATH。
  echo https://www.python.org/downloads/
  pause
  exit /b 1
)

%PYTHON% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)" >nul 2>&1
if errorlevel 1 (
  echo [错误] Python 版本低于 3.12，无法运行 Django 6。
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/4] 创建 Python 虚拟环境...
  %PYTHON% -m venv .venv
  if errorlevel 1 goto fail
) else (
  echo [1/4] Python 虚拟环境已存在。
)

echo [2/4] 安装或检查后端依赖...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail

echo [3/4] 初始化数据库与词库...
".venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 goto fail
".venv\Scripts\python.exe" manage.py seed_words
if errorlevel 1 goto fail

if not exist "frontend\dist\index.html" (
  echo [4/4] 未发现前端构建产物，开始构建...
  where npm >nul 2>&1
  if errorlevel 1 (
    echo [错误] 缺少 npm，无法构建前端。请安装 Node.js 20 或更高版本。
    pause
    exit /b 1
  )
  pushd frontend
  call npm ci
  if errorlevel 1 (popd & goto fail)
  call npm run build
  if errorlevel 1 (popd & goto fail)
  popd
) else (
  echo [4/4] 已找到前端构建产物。
)

echo.
echo 正在启动：http://127.0.0.1:%PORT%/
echo 关闭本窗口即可停止服务。
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:%PORT%/'"
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:%PORT%
echo.
echo 服务已停止。
pause
exit /b 0

:fail
echo.
echo [错误] 启动失败，请检查上方信息。
pause
exit /b 1