#!/bin/bash

echo "🔧 Решение конфликта Git с сохранением данных ML..."

# Создаем резервную копию данных ML
echo "📦 Создание резервной копии данных ML..."
mkdir -p ml_data_backup
cp data/api_metrics.db ml_data_backup/ 2>/dev/null || echo "⚠️  api_metrics.db не найден"
cp data/stock_history.db ml_data_backup/ 2>/dev/null || echo "⚠️  stock_history.db не найден"
cp data/api_health.db ml_data_backup/ 2>/dev/null || echo "⚠️  api_health.db не найден"

echo "✅ Резервная копия создана в ml_data_backup/"

# Сохраняем все изменения в stash
echo "💾 Сохранение изменений в stash..."
git stash push -u -m "Сохранение данных ML перед pull"

# Выполняем pull
echo "⬇️  Выполнение git pull..."
git pull

# Восстанавливаем данные ML
echo "🔄 Восстановление данных ML..."
git stash pop

echo "✅ Конфликт решен!"
echo "📁 Ваши данные ML сохранены в ml_data_backup/"
echo "🔍 Проверьте статус: git status" 