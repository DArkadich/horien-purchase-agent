#!/usr/bin/env python3
"""
Тест системы мониторинга API
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api_monitor import APIMonitor, APIMonitoringService, APIStatus
from ozon_api import OzonAPI
import time
import logging
import asyncio

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_api_monitor():
    """Тестирует APIMonitor"""
    print("🧪 Тестирование APIMonitor...")
    
    # Создаем API клиент и монитор
    api_client = OzonAPI()
    monitor = APIMonitor(db_path="test_data/api_health_test.db")
    
    # Тест 1: Проверка здоровья API
    print("Тестирование проверки здоровья API...")
    health_check = monitor.check_api_health(api_client, "products")
    
    print(f"✅ Статус API: {health_check.status.value}")
    print(f"✅ Время ответа: {health_check.response_time:.0f}мс")
    print(f"✅ Код статуса: {health_check.status_code}")
    if health_check.error_message:
        print(f"⚠️ Ошибка: {health_check.error_message}")
    
    # Тест 2: Получение статистики
    print("\nТестирование получения статистики...")
    stats = monitor.get_health_stats(hours=1)
    if stats:
        print(f"✅ Общая статистика: {stats['total_checks']} проверок")
        print(f"✅ Uptime: {stats['uptime_percentage']:.1f}%")
        print(f"✅ Среднее время ответа: {stats['avg_response_time']:.0f}мс")
    else:
        print("⚠️ Нет данных для статистики")
    
    # Тест 3: Получение инцидентов
    print("\nТестирование получения инцидентов...")
    incidents = monitor.get_recent_incidents(hours=1)
    print(f"✅ Найдено {len(incidents)} инцидентов")
    
    # Тест 4: Генерация отчета
    print("\nТестирование генерации отчета...")
    report = monitor.generate_health_report(hours=1)
    print("✅ Отчет сгенерирован:")
    print(report[:500] + "..." if len(report) > 500 else report)
    
    # Тест 5: Очистка старых данных
    print("\nТестирование очистки данных...")
    monitor.cleanup_old_data(days=1)
    print("✅ Очистка завершена")

async def test_monitoring_service():
    """Тестирует APIMonitoringService"""
    print("\n🧪 Тестирование APIMonitoringService...")
    
    # Создаем компоненты
    api_client = OzonAPI()
    monitor = APIMonitor(db_path="test_data/api_health_test.db")
    
    # Создаем простой telegram notifier для тестов
    class TestTelegramNotifier:
        async def send_message(self, message):
            print(f"📱 Telegram: {message[:100]}...")
    
    telegram_notifier = TestTelegramNotifier()
    monitoring_service = APIMonitoringService(api_client, monitor, telegram_notifier)
    
    # Запускаем мониторинг на короткое время
    print("Запуск мониторинга на 10 секунд...")
    monitoring_task = asyncio.create_task(monitoring_service.start_monitoring())
    
    # Ждем 10 секунд
    await asyncio.sleep(10)
    
    # Останавливаем мониторинг
    monitoring_service.stop_monitoring()
    
    # Отправляем отчет
    await monitoring_service.send_health_report(hours=1)
    
    print("✅ Тест мониторинга завершен")

def test_api_endpoints():
    """Тестирует различные эндпоинты API"""
    print("\n🧪 Тестирование различных эндпоинтов API...")
    
    api_client = OzonAPI()
    monitor = APIMonitor(db_path="test_data/api_health_test.db")
    
    endpoints = ["products", "stocks", "sales", "analytics"]
    
    for endpoint in endpoints:
        print(f"\nТестирование эндпоинта: {endpoint}")
        try:
            health_check = monitor.check_api_health(api_client, endpoint)
            print(f"  Статус: {health_check.status.value}")
            print(f"  Время ответа: {health_check.response_time:.0f}мс")
            print(f"  Код статуса: {health_check.status_code}")
            
            if health_check.error_message:
                print(f"  Ошибка: {health_check.error_message}")
                
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")

def test_monitoring_performance():
    """Тестирует производительность мониторинга"""
    print("\n🧪 Тестирование производительности мониторинга...")
    
    api_client = OzonAPI()
    monitor = APIMonitor(db_path="test_data/api_health_test.db")
    
    # Тестируем скорость проверок
    start_time = time.time()
    
    for i in range(5):
        health_check = monitor.check_api_health(api_client, "products")
        print(f"Проверка {i+1}: {health_check.response_time:.0f}мс")
    
    total_time = time.time() - start_time
    avg_time = total_time / 5
    
    print(f"✅ Среднее время проверки: {avg_time:.2f} сек")
    print(f"✅ Общее время: {total_time:.2f} сек")

async def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов системы мониторинга API\n")
    
    try:
        # Создаем тестовую директорию
        os.makedirs("test_data", exist_ok=True)
        
        test_api_monitor()
        test_api_endpoints()
        test_monitoring_performance()
        
        # Тест асинхронного сервиса
        await test_monitoring_service()
        
        print("\n✅ Все тесты мониторинга завершены успешно!")
        
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 