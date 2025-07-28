#!/bin/bash
# Скрипт для установки зависимостей

echo "Создание виртуального окружения..."

# Создаем виртуальное окружение
python3 -m venv venv

# Активируем виртуальное окружение
source venv/bin/activate

echo "Установка зависимостей в виртуальное окружение..."

# Устанавливаем зависимости из requirements.txt
pip install -r requirements.txt

echo "Зависимости установлены!"
echo ""
echo "Для активации виртуального окружения:"
echo "source venv/bin/activate"
echo ""
echo "Теперь можно запускать тесты:"
echo "python test_ozon_api.py"
echo "python test_sheets.py"
echo "python test_telegram.py"
echo ""
echo "Для деактивации:"
echo "deactivate" 