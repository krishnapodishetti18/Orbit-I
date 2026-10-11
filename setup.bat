@echo off
setlocal
py -3.11 -V >nul 2>nul || (echo Python 3.11 is required. Install it with the Python launcher.& exit /b 1)
where npm >nul 2>nul || (echo Node.js 20+ is required.& exit /b 1)
if not exist backend\.venv311 py -3.11 -m venv backend\.venv311
call backend\.venv311\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
pushd frontend
call npm install
popd
if not exist .env copy .env.example .env >nul
if not exist backend\.env copy backend\.env.example backend\.env >nul
echo Setup complete. Add OPENAI_API_KEY to .env or backend\.env for live AI; fallback planning works without it.
