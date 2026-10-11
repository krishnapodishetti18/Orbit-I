@echo off
setlocal
call backend\.venv311\Scripts\activate.bat
set PYTHONPATH=.
python -m pytest tests -q
pushd frontend
call npm run build
popd
