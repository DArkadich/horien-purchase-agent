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
import asyncio

# Импорты модулей
from config import validate_config, logger
from ozon_api import OzonAPI
from cache_manager import CacheManager, CachedAPIClient
from api_monitor import APIMonitor, APIMonitoringService
from api_metrics import APIMetricsCollector
from sheets import GoogleSheets
from telegram_notify import TelegramNotifier
from forecast import PurchaseForecast
from stock_tracker import StockTracker

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
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
        cache_manager = CacheManager()
        cached_api = CachedAPIClient(ozon_api, cache_manager)
        api_monitor = APIMonitor()
        telegram = TelegramNotifier()
        monitoring_service = APIMonitoringService(ozon_api, api_monitor, telegram)
        metrics_collector = APIMetricsCollector()
        sheets = GoogleSheets()
        stock_tracker = StockTracker()
        
        # Очищаем истекший кэш
        expired_count = cache_manager.clear_expired_cache()
        if expired_count > 0:
            logger.info(f"Очищено {expired_count} истекших записей кэша")
        
        # Логируем статистику кэша
        cache_stats = cache_manager.get_cache_stats()
        if cache_stats:
            logger.info(f"Статистика кэша: {cache_stats['total_entries']} записей, {cache_stats['expired_entries']} истекших")
            for cache_type, stats in cache_stats.get('type_stats', {}).items():
                logger.info(f"  {cache_type}: {stats['count']} записей, {stats['total_size']} байт")
        
        # Проверяем здоровье API
        logger.info("Проверка здоровья API...")
        health_check = api_monitor.check_api_health(ozon_api, "products")
        logger.info(f"API статус: {health_check.status.value} ({health_check.response_time:.0f}мс)")
        
        if health_check.status.value == "down":
            logger.warning("API недоступен, но продолжаем работу с кэшированными данными")
            await telegram.send_message("⚠️ API недоступен, используем кэшированные данные")
        
        # Запускаем мониторинг API в фоне
        monitoring_task = asyncio.create_task(monitoring_service.start_monitoring())
        
        # Отправка уведомления о запуске
        await telegram.send_message("🚀 Агент закупок Horiens запущен")
        
        # Получение данных из Ozon API
        logger.info("Получение данных из Ozon API...")
        
        # Получаем товары с кэшированием
        products = cached_api.get_products_with_cache()
        if not products:
            logger.error("Не удалось получить товары из Ozon API")
            await telegram.send_message("❌ Критическая ошибка: Не удалось получить товары из Ozon API. Проверьте настройки API ключей и доступность сервиса.")
            return
        
        logger.info(f"Успешно получены товары: {len(products)} шт")
        
        # Сохранение данных об остатках
        logger.info("Сохранение данных об остатках...")
        current_stocks = cached_api.get_stocks_data_with_cache()
        
        # Отладочная информация
        logger.info(f"Получено данных об остатках: {len(current_stocks) if current_stocks else 0}")
        if current_stocks:
            logger.info(f"Пример данных об остатках: {current_stocks[:2]}")  # Показываем первые 2 записи
        
        if current_stocks:
            stock_tracker.save_stock_data(current_stocks)
            logger.info(f"Сохранено {len(current_stocks)} записей об остатках")
            
            # Очистка синтетических данных и запись реальных остатков
            logger.info("Очистка синтетических данных и запись реальных остатков...")
            sheets.clear_all_synthetic_data()
            sheets.write_stock_data(current_stocks)
        else:
            logger.warning("Нет данных об остатках для сохранения")
        
        # Получаем данные о продажах из API с кэшированием
        logger.info("Получение данных о продажах из API...")
        from config import SALES_HISTORY_DAYS
        sales_data = cached_api.get_sales_data_with_cache(days=SALES_HISTORY_DAYS)
        
        if not sales_data:
            logger.warning("Нет данных о продажах из API, используем оценку из изменений остатков")
            # Fallback: используем оценку из изменений остатков
            sales_data = stock_tracker.estimate_sales_from_stock_changes(days=SALES_HISTORY_DAYS)
            
            # Если все еще нет данных, пробуем с меньшим периодом
            if not sales_data:
                logger.warning("Нет данных за 180 дней, пробуем с доступными данными")
                sales_data = stock_tracker.estimate_sales_from_stock_changes(days=30)  # Пробуем 30 дней
                
                if not sales_data:
                    logger.warning("Нет данных за 30 дней, используем все доступные данные")
                    sales_data = stock_tracker.estimate_sales_from_stock_changes(days=1)  # Используем все данные
        
        logger.info(f"Получено {len(sales_data)} записей о продажах")
        
        # Получаем данные об остатках
        logger.info("Получение данных об остатках...")
        stocks_data = current_stocks if current_stocks else []
        
        if not stocks_data:
            logger.warning("Нет данных об остатках")
            await telegram.send_message("⚠️ Предупреждение: Нет данных об остатках для анализа")
            return
        
        logger.info(f"Получено {len(stocks_data)} записей об остатках")
        
        # Подготовка данных для анализа
        logger.info("Подготовка данных для анализа...")
        
        # Подготовка данных о продажах
        logger.info("Подготовка данных о продажах...")
        if sales_data:
            sales_df = pd.DataFrame(sales_data)
            logger.info(f"Подготовлено {len(sales_df)} записей о продажах")
        else:
            # Создаем пустой DataFrame для продаж
            sales_df = pd.DataFrame()
            logger.info("Нет данных о продажах, используем базовую логику")
        
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
        if not sales_df.empty:
            sales_df = calculator.prepare_sales_data(sales_data)
        stocks_df = calculator.prepare_stocks_data(stocks_data)
        
        # Рассчитываем прогноз
        forecast_data = calculator.calculate_forecast(sales_df, stocks_df)
        
        if forecast_data.empty:
            logger.error("Не удалось рассчитать прогноз закупок")
            await telegram.send_message("❌ Ошибка: Не удалось рассчитать прогноз закупок")
            return
        
        logger.info(f"Рассчитан прогноз для {len(forecast_data)} позиций")
        
        # Генерация отчета о закупках
        logger.info("Генерация отчета о закупках...")
        report_data = calculator.generate_purchase_report(forecast_data)
        
        if not report_data:
            logger.error("Не удалось сгенерировать отчет о закупках")
            await telegram.send_message("❌ Ошибка: Не удалось сгенерировать отчет о закупках")
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
        
        # Подготовка сводных данных для Telegram
        logger.info("Подготовка сводных данных...")
        summary_data = {
            'total_items': len(report_data),
            'high_priority': len([item for item in report_data if item.get('urgency') == 'HIGH']),
            'medium_priority': len([item for item in report_data if item.get('urgency') == 'MEDIUM']),
            'low_priority': len([item for item in report_data if item.get('urgency') == 'LOW'])
        }
        
        # Отправка отчета в Telegram
        logger.info("Отправка отчета в Telegram...")
        await telegram.send_purchase_report(report_data, summary_data)
        logger.info("Отчет о закупках отправлен в Telegram")
        
        # Отправка итогового уведомления
        execution_time = time.time() - start_time
        await telegram.send_message(
            f"✅ Агент закупок завершил работу за {execution_time:.2f} секунд\n"
            f"📊 Обработано {len(report_data)} позиций для закупки"
        )
        
        # Отправляем отчет о здоровье API
        await monitoring_service.send_health_report(hours=1)
        
        # Отправляем отчет о производительности API
        performance_report = metrics_collector.generate_performance_report(hours=1)
        await telegram.send_message(performance_report)
        
        # Останавливаем мониторинг
        monitoring_service.stop_monitoring()
        
        logger.info("=" * 50)
        logger.info("Агент закупок завершил работу за %.2f секунд", execution_time)
        logger.info("Обработано %d позиций для закупки", len(report_data))
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error("Ошибка в работе агента закупок: %s", str(e))
        try:
            if 'telegram' in locals():
                await telegram.send_message(f"❌ Ошибка в работе агента закупок: {str(e)}")
        except Exception as telegram_error:
            logger.error("Не удалось отправить сообщение об ошибке в Telegram: %s", str(telegram_error))

if __name__ == "__main__":
    asyncio.run(main()) 