#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
    echo "Создаю окружение..."
    python3 -m venv .venv || { echo "Установите python3-venv: sudo apt install python3-venv"; exit 1; }
fi
source .venv/bin/activate
echo "Устанавливаю библиотеки (только в первый раз)..."
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
python main.py
