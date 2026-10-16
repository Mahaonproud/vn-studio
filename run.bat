@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (
    echo Создаю окружение...
    py -3 -m venv .venv || python -m venv .venv
)
call .venv\Scripts\activate.bat
echo Устанавливаю библиотеки (только в первый раз)...
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
python main.py
if errorlevel 1 pause
