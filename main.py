#!/usr/bin/env python3
"""
Главный модуль агента закупок Horiens
"""

import time
import logging
import os
from datetime import datetime
from typing import Dict, List, Any

# Импорты модулей
from config import validate_config, logger
from ozon_api import OzonAPI
from forecast import PurchaseForecast
from sheets import GoogleSheets
from telegram_notify import TelegramNotifier

def main():
    """
    Главная функция приложения
    """
    start_time = time.time()
    
    try:
        logger.info("=" * 50)
        logger.info("Запуск агента закупок Horiens")
        logger.info("=" * 50)
        
        # Проверяем конфигурацию
        if not validate_config():
            logger.error("Ошибка конфигурации. Завершение работы.")
            return 1
        
        # Инициализируем компоненты
        logger.info("Инициализация компонентов...")
        
        ozon_api = OzonAPI()
        forecast = PurchaseForecast()
        sheets = GoogleSheets()
        telegram = TelegramNotifier()
        
        # Отправляем уведомление о запуске
        telegram.send_startup_notification_sync()
        
        # Получаем данные из Ozon API
        logger.info("Получение данных из Ozon API...")
        
        # Получаем данные о продажах
        sales_data = ozon_api.get_sales_data()
        if not sales_data:
            logger.error("Не удалось получить данные о продажах")
            telegram.send_error_notification_sync("Не удалось получить данные о продажах из Ozon API")
            return 1
        
        # Получаем данные об остатках
        stocks_data = ozon_api.get_stocks_data()
        if not stocks_data:
            logger.error("Не удалось получить данные об остатках")
            telegram.send_error_notification_sync("Не удалось получить данные об остатках из Ozon API")
            return 1
        
        # Подготавливаем данные для анализа
        logger.info("Подготовка данных для анализа...")
        
        sales_df = forecast.prepare_sales_data(sales_data)
        stocks_df = forecast.prepare_stocks_data(stocks_data)
        
        if sales_df.empty or stocks_df.empty:
            logger.error("Недостаточно данных для анализа")
            telegram.send_error_notification_sync("Недостаточно данных для анализа")
            return 1
        
        # Рассчитываем прогноз закупок
        logger.info("Расчет прогноза закупок...")
        
        forecast_df = forecast.calculate_forecast(sales_df, stocks_df)
        
        if forecast_df.empty:
            logger.warning("Нет данных для прогноза закупок")
            telegram.send_message_sync("📊 Нет товаров, требующих закупки.")
            return 0
        
        # Генерируем отчет о закупках
        logger.info("Генерация отчета о закупках...")
        
        purchase_report = forecast.generate_purchase_report(forecast_df)
        
        if not purchase_report:
            logger.info("Нет товаров, требующих закупки")
            telegram.send_message_sync("📊 Нет товаров, требующих закупки.")
            return 0
        
        # Генерируем сводные данные
        summary_data = generate_summary_data(purchase_report)
        
        # Записываем отчет в Google Sheets
        logger.info("Запись отчета в Google Sheets...")
        
        try:
            sheets.write_purchase_report(purchase_report)
            sheets.create_summary_sheet(summary_data)
            logger.info("Отчет успешно записан в Google Sheets")
        except Exception as e:
            logger.error(f"Ошибка записи в Google Sheets: {e}")
            telegram.send_error_notification_sync(f"Ошибка записи в Google Sheets: {e}")
            return 1
        
        # Отправляем отчет в Telegram
        logger.info("Отправка отчета в Telegram...")
        
        try:
            telegram.send_purchase_report_sync(purchase_report, summary_data)
            logger.info("Отчет успешно отправлен в Telegram")
        except Exception as e:
            logger.error(f"Ошибка отправки в Telegram: {e}")
            # Не прерываем выполнение, так как основная работа уже выполнена
        
        # Рассчитываем время выполнения
        execution_time = time.time() - start_time
        
        # Отправляем уведомление о завершении
        telegram.send_completion_notification_sync(execution_time, len(purchase_report))
        
        logger.info("=" * 50)
        logger.info(f"Агент закупок завершил работу за {execution_time:.2f} секунд")
        logger.info(f"Обработано {len(purchase_report)} позиций для закупки")
        logger.info("=" * 50)
        
        return 0
        
    except Exception as e:
        execution_time = time.time() - start_time
        error_message = f"Критическая ошибка: {str(e)}"
        logger.error(error_message, exc_info=True)
        
        # Отправляем уведомление об ошибке
        try:
            telegram = TelegramNotifier()
            telegram.send_error_notification_sync(error_message)
        except:
            logger.error("Не удалось отправить уведомление об ошибке")
        
        return 1

def generate_summary_data(report_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Генерирует сводные данные для отчета
    """
    if not report_data:
        return {
            'total_items': 0,
            'high_priority': 0,
            'medium_priority': 0,
            'low_priority': 0,
            'total_value': 0,
            'items': []
        }
    
    # Подсчитываем приоритеты
    high_priority = sum(1 for item in report_data if item['urgency'] == 'HIGH')
    medium_priority = sum(1 for item in report_data if item['urgency'] == 'MEDIUM')
    low_priority = sum(1 for item in report_data if item['urgency'] == 'LOW')
    
    # Рассчитываем общую стоимость (примерно)
    total_value = sum(item['recommended_quantity'] for item in report_data)
    
    return {
        'total_items': len(report_data),
        'high_priority': high_priority,
        'medium_priority': medium_priority,
        'low_priority': low_priority,
        'total_value': total_value,
        'items': report_data
    }

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code) 