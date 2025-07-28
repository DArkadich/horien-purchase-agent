#!/usr/bin/env python3
"""
Главный модуль агента закупок Horiens
"""

import logging
import time
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any
import os

# Импорты модулей
from config import validate_config, logger
from ozon_api import OzonAPI
from sheets import GoogleSheets
from telegram_notify import TelegramNotifier
from forecast import PurchaseForecast
from stock_tracker import StockTracker

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Основная функция агента закупок"""
    start_time = time.time()
    
    try:
        # Инициализация конфигурации
        if not validate_config():
            logger.error("Ошибка конфигурации. Завершение работы.")
            return
        
        # Инициализация компонентов
        logger.info("Инициализация компонентов...")
        ozon_api = OzonAPI()
        sheets = GoogleSheets()
        telegram = TelegramNotifier()
        stock_tracker = StockTracker()
        
        # Отправка уведомления о запуске
        telegram.send_message("🚀 Агент закупок Horiens запущен")
        
        # Получение данных из Ozon API
        logger.info("Получение данных из Ozon API...")
        
        # Получаем товары
        products = ozon_api.get_products()
        if not products:
            logger.error("Не удалось получить товары")
            telegram.send_message("❌ Ошибка: Не удалось получить товары из Ozon API")
            return
        
        logger.info(f"Успешно получены товары: {len(products)} шт")
        
        # Сохраняем текущие остатки в базу данных
        logger.info("Сохранение данных об остатках...")
        current_stocks = ozon_api.get_stocks_data()
        if current_stocks:
            stock_tracker.save_stock_data(current_stocks)
            logger.info(f"Сохранено {len(current_stocks)} записей об остатках")
        else:
            logger.warning("Нет данных об остатках для сохранения")
        
        # Получаем данные о продажах на основе истории остатков
        logger.info("Получение данных о продажах на основе истории остатков...")
        sales_data = stock_tracker.estimate_sales_from_stock_changes(days=90)
        
        if not sales_data:
            logger.warning("Нет данных о продажах из истории остатков")
            telegram.send_message("⚠️ Предупреждение: Нет данных о продажах для анализа")
            return
        
        logger.info(f"Получено {len(sales_data)} записей о продажах из истории остатков")
        
        # Получаем данные об остатках
        logger.info("Получение данных об остатках...")
        stocks_data = current_stocks if current_stocks else []
        
        if not stocks_data:
            logger.warning("Нет данных об остатках")
            telegram.send_message("⚠️ Предупреждение: Нет данных об остатках для анализа")
            return
        
        logger.info(f"Получено {len(stocks_data)} записей об остатках")
        
        # Подготовка данных для анализа
        logger.info("Подготовка данных для анализа...")
        
        # Подготовка данных о продажах
        logger.info("Подготовка данных о продажах...")
        sales_df = pd.DataFrame(sales_data)
        if not sales_df.empty:
            logger.info(f"Подготовлено {len(sales_df)} записей о продажах")
        else:
            logger.warning("Нет данных о продажах для анализа")
            return
        
        # Подготовка данных об остатках
        logger.info("Подготовка данных об остатках...")
        stocks_df = pd.DataFrame(stocks_data)
        if not stocks_df.empty:
            logger.info(f"Подготовлено {len(stocks_df)} записей об остатках")
        else:
            logger.warning("Нет данных об остатках для анализа")
            return
        
        # Расчет прогноза закупок
        logger.info("Расчет прогноза закупок...")
        calculator = PurchaseForecast()
        
        # Подготавливаем данные
        sales_df = calculator.prepare_sales_data(sales_data)
        stocks_df = calculator.prepare_stocks_data(stocks_data)
        
        # Рассчитываем прогноз
        forecast_data = calculator.calculate_forecast(sales_df, stocks_df)
        
        if not forecast_data:
            logger.error("Не удалось рассчитать прогноз закупок")
            telegram.send_message("❌ Ошибка: Не удалось рассчитать прогноз закупок")
            return
        
        logger.info(f"Рассчитан прогноз для {len(forecast_data)} позиций")
        
        # Генерация отчета о закупках
        logger.info("Генерация отчета о закупках...")
        report_data = calculator.generate_purchase_report(forecast_data)
        
        if not report_data:
            logger.error("Не удалось сгенерировать отчет о закупках")
            telegram.send_message("❌ Ошибка: Не удалось сгенерировать отчет о закупках")
            return
        
        logger.info(f"Сгенерирован отчет для {len(report_data)} SKU")
        
        # Запись отчета в Google Sheets
        logger.info("Запись отчета в Google Sheets...")
        sheets.write_purchase_report(report_data)
        logger.info("Отчет о закупках записан в Google Sheets")
        
        # Создание сводного листа
        logger.info("Создание сводного листа...")
        sheets.create_summary_sheet(report_data)
        logger.info("Сводный лист создан")
        
        # Отправка отчета в Telegram
        logger.info("Отправка отчета в Telegram...")
        telegram.send_purchase_report(report_data)
        logger.info("Отчет о закупках отправлен в Telegram")
        
        # Отправка итогового уведомления
        execution_time = time.time() - start_time
        telegram.send_message(
            f"✅ Агент закупок завершил работу за {execution_time:.2f} секунд\n"
            f"📊 Обработано {len(report_data)} позиций для закупки"
        )
        
        logger.info("=" * 50)
        logger.info("Агент закупок завершил работу за %.2f секунд", execution_time)
        logger.info("Обработано %d позиций для закупки", len(report_data))
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error("Ошибка в работе агента закупок: %s", str(e))
        try:
            if 'telegram' in locals():
                telegram.send_message(f"❌ Ошибка в работе агента закупок: {str(e)}")
        except Exception as telegram_error:
            logger.error("Не удалось отправить сообщение об ошибке в Telegram: %s", str(telegram_error))

if __name__ == "__main__":
    main() 