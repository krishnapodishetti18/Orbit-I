@echo off
setlocal
if not exist backend\.venv311\Scripts\python.exe (echo Run setup.bat first.& exit /b 1)
start "Orbit AI API" cmd /k "cd /d %~dp0backend && ..\.venv311\Scripts\python.exe -m uvicorn main:app --reload --port 8003"
start "Orbit AI Web" cmd /k "cd /d %~dp0frontend && npm run dev -- --host 127.0.0.1"
timeout /t 3 >nul
start http://localhost:5173
