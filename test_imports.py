#!/usr/bin/env python3
"""
Тестовый скрипт для проверки импортов модулей
"""

import sys
import os

def test_imports():
    """Тестирует импорт всех модулей"""
    
    print("Тестирование импортов модулей...")
    
    try:
        # Тестируем импорт config
        print("✓ Импорт config...")
        import config
        
        # Тестируем импорт ozon_api
        print("✓ Импорт ozon_api...")
        import ozon_api
        
        # Тестируем импорт forecast
        print("✓ Импорт forecast...")
        import forecast
        
        # Тестируем импорт sheets
        print("✓ Импорт sheets...")
        import sheets
        
        # Тестируем импорт telegram_notify
        print("✓ Импорт telegram_notify...")
        import telegram_notify
        
        print("\n✅ Все модули успешно импортированы!")
        return True
        
    except ImportError as e:
        print(f"\n❌ Ошибка импорта: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        return False

def test_config_validation():
    """Тестирует валидацию конфигурации"""
    
    print("\nТестирование валидации конфигурации...")
    
    try:
        # Устанавливаем тестовые переменные окружения
        os.environ['OZON_API_KEY'] = 'test_key'
        os.environ['OZON_CLIENT_ID'] = 'test_client'
        os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'] = '{"test": "json"}'
        os.environ['GOOGLE_SPREADSHEET_ID'] = 'test_spreadsheet'
        os.environ['TELEGRAM_TOKEN'] = 'test_token'
        os.environ['TELEGRAM_CHAT_ID'] = 'test_chat'
        
        # Перезагружаем config для применения новых переменных
        import importlib
        import config
        importlib.reload(config)
        
        # Тестируем валидацию
        if config.validate_config():
            print("✅ Конфигурация валидна")
            return True
        else:
            print("❌ Конфигурация невалидна")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования конфигурации: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Тестирование агента закупок Horiens")
    print("=" * 50)
    
    # Тестируем импорты
    imports_ok = test_imports()
    
    # Тестируем конфигурацию
    config_ok = test_config_validation()
    
    print("\n" + "=" * 50)
    if imports_ok and config_ok:
        print("✅ Все тесты пройдены успешно!")
        print("Приложение готово к запуску")
    else:
        print("❌ Некоторые тесты не пройдены")
        print("Проверьте конфигурацию и зависимости")
    print("=" * 50) 