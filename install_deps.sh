#!/bin/bash
# Скрипт для установки зависимостей

echo "Установка зависимостей для тестирования..."

# Устанавливаем зависимости из requirements.txt
pip3 install -r requirements.txt

echo "Зависимости установлены!"
echo ""
echo "Теперь можно запускать тесты:"
echo "python3 test_ozon_api.py"
echo "python3 test_sheets.py"
echo "python3 test_telegram.py" 