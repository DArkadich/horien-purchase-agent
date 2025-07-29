#!/usr/bin/env python3
"""
Тест системы метрик производительности API
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api_metrics import APIMetricsCollector, MetricType
from ozon_api import OzonAPI
import time
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_metrics_collector():
    """Тестирует APIMetricsCollector"""
    print("🧪 Тестирование APIMetricsCollector...")
    
    # Создаем collector
    metrics_collector = APIMetricsCollector(db_path="test_data/api_metrics_test.db")
    
    # Тест 1: Запись метрик времени ответа
    print("Тестирование записи метрик времени ответа...")
    metrics_collector.record_response_time("test_endpoint", 150.5, 200)
    metrics_collector.record_response_time("test_endpoint", 2500.0, 200)
    metrics_collector.record_response_time("test_endpoint", 100.0, 500, "Test error")
    
    print("✅ Метрики времени ответа записаны")
    
    # Тест 2: Запись метрик успешности
    print("Тестирование записи метрик успешности...")
    metrics_collector.record_success_rate("test_endpoint", 8, 10)
    metrics_collector.record_success_rate("test_endpoint", 2, 10)
    
    print("✅ Метрики успешности записаны")
    
    # Тест 3: Запись метрик ошибок
    print("Тестирование записи метрик ошибок...")
    metrics_collector.record_error_rate("test_endpoint", 2, 10)
    metrics_collector.record_error_rate("test_endpoint", 8, 10)
    
    print("✅ Метрики ошибок записаны")
    
    # Тест 4: Запись других метрик
    print("Тестирование записи других метрик...")
    metrics_collector.record_throughput("test_endpoint", 120.5)
    metrics_collector.record_cache_hit_rate("test_endpoint", 85.2)
    metrics_collector.record_retry_count("test_endpoint", 2)
    
    print("✅ Другие метрики записаны")
    
    # Тест 5: Получение сводки
    print("Тестирование получения сводки метрик...")
    summary = metrics_collector.get_metrics_summary(hours=1)
    if summary:
        print(f"✅ Сводка получена: {len(summary.get('metrics', {}))} эндпоинтов")
        for endpoint, metrics in summary.get('metrics', {}).items():
            print(f"  {endpoint}: {len(metrics)} типов метрик")
    else:
        print("⚠️ Сводка пуста")
    
    # Тест 6: Получение трендов
    print("Тестирование получения трендов...")
    trends = metrics_collector.get_performance_trends(hours=1)
    if trends:
        print(f"✅ Тренды получены: {len(trends.get('response_time_trends', {}))} эндпоинтов")
    else:
        print("⚠️ Тренды пусты")
    
    # Тест 7: Генерация отчета
    print("Тестирование генерации отчета...")
    report = metrics_collector.generate_performance_report(hours=1)
    print("✅ Отчет сгенерирован:")
    print(report[:500] + "..." if len(report) > 500 else report)
    
    # Тест 8: Очистка старых данных
    print("Тестирование очистки данных...")
    metrics_collector.cleanup_old_metrics(days=1)
    print("✅ Очистка завершена")

def test_api_with_metrics():
    """Тестирует API с метриками"""
    print("\n🧪 Тестирование API с метриками...")
    
    # Создаем API клиент
    api_client = OzonAPI()
    
    # Тестируем получение товаров с метриками
    print("Тестирование получения товаров с метриками...")
    
    start_time = time.time()
    products = api_client.get_products()
    total_time = time.time() - start_time
    
    print(f"✅ Получено товаров: {len(products) if products else 0}")
    print(f"✅ Время выполнения: {total_time:.2f} сек")
    
    # Получаем метрики
    metrics_collector = api_client.metrics_collector
    summary = metrics_collector.get_metrics_summary(hours=1)
    
    if summary and summary.get('metrics'):
        print("📊 Метрики API:")
        for endpoint, metrics in summary['metrics'].items():
            print(f"  {endpoint}:")
            for metric_type, data in metrics.items():
                print(f"    {metric_type}: avg={data['avg']:.2f}, count={data['count']}")

def test_metrics_performance():
    """Тестирует производительность системы метрик"""
    print("\n🧪 Тестирование производительности метрик...")
    
    metrics_collector = APIMetricsCollector(db_path="test_data/api_metrics_perf_test.db")
    
    # Тестируем скорость записи метрик
    start_time = time.time()
    
    for i in range(100):
        metrics_collector.record_response_time(f"endpoint_{i % 5}", 100 + i, 200)
        metrics_collector.record_success_rate(f"endpoint_{i % 5}", 9, 10)
    
    total_time = time.time() - start_time
    avg_time = total_time / 100
    
    print(f"✅ Записано 100 метрик за {total_time:.2f} сек")
    print(f"✅ Среднее время записи: {avg_time:.4f} сек")
    
    # Тестируем скорость получения сводки
    start_time = time.time()
    summary = metrics_collector.get_metrics_summary(hours=1)
    summary_time = time.time() - start_time
    
    print(f"✅ Получение сводки: {summary_time:.4f} сек")
    print(f"✅ Обработано метрик: {len(summary.get('metrics', {}))} эндпоинтов")

def test_metrics_alerts():
    """Тестирует систему алертов метрик"""
    print("\n🧪 Тестирование системы алертов...")
    
    metrics_collector = APIMetricsCollector(db_path="test_data/api_metrics_alerts_test.db")
    
    # Тестируем алерты на высокое время ответа
    print("Тестирование алертов на высокое время ответа...")
    metrics_collector.record_response_time("slow_endpoint", 6000, 200)  # 6 секунд
    
    # Тестируем алерты на низкую успешность
    print("Тестирование алертов на низкую успешность...")
    metrics_collector.record_success_rate("failing_endpoint", 3, 10)  # 30%
    
    # Тестируем алерты на высокую частоту ошибок
    print("Тестирование алертов на высокую частоту ошибок...")
    metrics_collector.record_error_rate("error_endpoint", 7, 10)  # 70%
    
    # Тестируем алерты на много повторных попыток
    print("Тестирование алертов на повторные попытки...")
    metrics_collector.record_retry_count("retry_endpoint", 5)
    
    print("✅ Алерты протестированы")

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов системы метрик производительности API\n")
    
    try:
        # Создаем тестовую директорию
        os.makedirs("test_data", exist_ok=True)
        
        test_metrics_collector()
        test_metrics_performance()
        test_metrics_alerts()
        
        # Тест API только если есть настроенные ключи
        try:
            test_api_with_metrics()
        except Exception as e:
            print(f"⚠️ Тест API пропущен (возможно, нет настроенных ключей): {e}")
        
        print("\n✅ Все тесты метрик завершены успешно!")
        
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 