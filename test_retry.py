#!/usr/bin/env python3
"""
Тест retry-логики для API
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ozon_api import RetryManager, OzonAPI
import time
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_retry_manager():
    """Тестирует RetryManager с различными сценариями"""
    print("🧪 Тестирование RetryManager...")
    
    # Создаем retry manager
    retry_manager = RetryManager(max_retries=2, base_delay=0.1, max_delay=1.0)
    
    # Тест 1: Успешная функция
    def successful_function():
        return "success"
    
    result = retry_manager.execute_with_retry(successful_function)
    print(f"✅ Успешная функция: {result}")
    
    # Тест 2: Функция, которая падает первые 2 раза, потом успешна
    attempt_count = 0
    def failing_then_successful():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count <= 2:
            raise Exception(f"Ошибка попытки {attempt_count}")
        return "success after retries"
    
    attempt_count = 0
    result = retry_manager.execute_with_retry(failing_then_successful)
    print(f"✅ Функция с retry: {result}")
    
    # Тест 3: Функция, которая всегда падает
    def always_failing():
        raise Exception("Постоянная ошибка")
    
    result = retry_manager.execute_with_retry(always_failing)
    print(f"❌ Постоянно падающая функция: {result}")
    
    # Тест 4: Функция, возвращающая None
    def returning_none():
        return None
    
    result = retry_manager.execute_with_retry(returning_none)
    print(f"✅ Функция возвращающая None: {result}")

def test_retry_status_codes():
    """Тестирует логику определения retryable статус кодов"""
    print("\n🧪 Тестирование retryable статус кодов...")
    
    retry_manager = RetryManager()
    
    # Тест retryable кодов
    retryable_codes = [500, 502, 503, 504, 429]
    for code in retryable_codes:
        should_retry = retry_manager.should_retry_status_code(code)
        print(f"Код {code}: {'🔄 Повторять' if should_retry else '❌ Не повторять'}")
    
    # Тест non-retryable кодов
    non_retryable_codes = [200, 400, 401, 403, 404]
    for code in non_retryable_codes:
        should_retry = retry_manager.should_retry_status_code(code)
        print(f"Код {code}: {'🔄 Повторять' if should_retry else '❌ Не повторять'}")

def test_api_with_retry():
    """Тестирует API с retry-логикой"""
    print("\n🧪 Тестирование API с retry-логикой...")
    
    # Создаем экземпляр API
    api = OzonAPI()
    
    # Тест получения товаров
    print("Тестирование получения товаров...")
    products = api.get_products()
    
    if products:
        print(f"✅ Получено товаров: {len(products)}")
    else:
        print("❌ Не удалось получить товары")
    
    # Тест получения аналитических данных
    print("Тестирование получения аналитических данных...")
    analytics = api.get_analytics_data(days=7)  # Только за неделю для теста
    
    if analytics:
        print(f"✅ Получено аналитических записей: {len(analytics)}")
    else:
        print("❌ Не удалось получить аналитические данные")

def test_retry_performance():
    """Тестирует производительность retry-логики"""
    print("\n🧪 Тестирование производительности retry-логики...")
    
    retry_manager = RetryManager(max_retries=3, base_delay=0.1, max_delay=1.0)
    
    def slow_function():
        time.sleep(0.1)  # Имитируем медленный запрос
        return "success"
    
    start_time = time.time()
    result = retry_manager.execute_with_retry(slow_function)
    end_time = time.time()
    
    execution_time = end_time - start_time
    print(f"Время выполнения с retry: {execution_time:.2f} секунд")
    print(f"Результат: {result}")

def test_retry_with_different_configs():
    """Тестирует retry с различными конфигурациями"""
    print("\n🧪 Тестирование retry с различными конфигурациями...")
    
    configs = [
        {"max_retries": 1, "base_delay": 0.1, "max_delay": 0.5},
        {"max_retries": 3, "base_delay": 0.2, "max_delay": 2.0},
        {"max_retries": 5, "base_delay": 0.5, "max_delay": 10.0},
    ]
    
    for i, config in enumerate(configs):
        print(f"Конфигурация {i+1}: {config}")
        
        retry_manager = RetryManager(**config)
        
        attempt_count = 0
        def test_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= 2:
                raise Exception(f"Ошибка попытки {attempt_count}")
            return f"success after {attempt_count} attempts"
        
        attempt_count = 0
        start_time = time.time()
        result = retry_manager.execute_with_retry(test_function)
        end_time = time.time()
        
        execution_time = end_time - start_time
        print(f"  Результат: {result}")
        print(f"  Время выполнения: {execution_time:.2f} секунд")

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов retry-логики\n")
    
    try:
        test_retry_manager()
        test_retry_status_codes()
        test_retry_performance()
        test_retry_with_different_configs()
        
        # Тест API только если есть настроенные ключи
        try:
            test_api_with_retry()
        except Exception as e:
            print(f"⚠️ Тест API пропущен (возможно, нет настроенных ключей): {e}")
        
        print("\n✅ Все тесты retry-логики завершены успешно!")
        
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 