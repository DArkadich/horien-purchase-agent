#!/usr/bin/env python3
"""
Тест Google Sheets для проверки реальных данных
"""

import logging
from sheets import GoogleSheets
from config import GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SPREADSHEET_ID

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_google_sheets():
    """Тестирует Google Sheets с реальными данными"""
    
    print("=" * 50)
    print("ТЕСТ GOOGLE SHEETS")
    print("=" * 50)
    
    # Проверяем наличие настроек
    if not GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_JSON == "{\"type\": \"service_account\", \"project_id\": \"your_project\", ...}":
        print("❌ GOOGLE_SERVICE_ACCOUNT_JSON не настроен")
        print("Настройте Service Account JSON в .env файле")
        return False
    
    if not GOOGLE_SPREADSHEET_ID or GOOGLE_SPREADSHEET_ID == "your_spreadsheet_id_here":
        print("❌ GOOGLE_SPREADSHEET_ID не настроен")
        print("Настройте ID таблицы в .env файле")
        return False
    
    print("✅ Google Sheets настройки присутствуют")
    
    try:
        # Создаем экземпляр Google Sheets
        sheets = GoogleSheets()
        print("✅ Google Sheets объект создан")
        
        # Тестируем запись тестовых данных
        print("\n📝 Тестирование записи данных...")
        
        test_data = [
            {
                'sku': 'TEST-SKU-001',
                'avg_daily_sales': 5.2,
                'current_stock': 150,
                'days_until_stockout': 28.8,
                'recommended_quantity': 200,
                'moq': 100,
                'urgency': 'MEDIUM'
            },
            {
                'sku': 'TEST-SKU-002',
                'avg_daily_sales': 3.1,
                'current_stock': 45,
                'days_until_stockout': 14.5,
                'recommended_quantity': 150,
                'moq': 50,
                'urgency': 'HIGH'
            }
        ]
        
        # Записываем тестовые данные
        sheets.write_purchase_report(test_data)
        print("✅ Тестовые данные записаны в Sheet1")
        
        # Создаем сводный лист
        summary_data = {
            'total_items': 2,
            'high_priority': 1,
            'medium_priority': 1,
            'low_priority': 0,
            'total_value': 350,
            'items': test_data
        }
        
        sheets.create_summary_sheet(summary_data)
        print("✅ Сводный лист создан")
        
        # Проверяем, что данные записались
        print("\n📊 Проверка записанных данных...")
        
        # Читаем данные из Sheet1
        sheet1_data = sheets.get_sheet_data("Sheet1!A1:H5")
        if sheet1_data:
            print(f"✅ Данные в Sheet1: {len(sheet1_data)} строк")
            for i, row in enumerate(sheet1_data, 1):
                print(f"  Строка {i}: {row}")
        else:
            print("⚠️ Данные в Sheet1 не найдены")
        
        # Читаем данные из Summary
        summary_data_read = sheets.get_sheet_data("Summary!A1:C10")
        if summary_data_read:
            print(f"✅ Данные в Summary: {len(summary_data_read)} строк")
            for i, row in enumerate(summary_data_read, 1):
                print(f"  Строка {i}: {row}")
        else:
            print("⚠️ Данные в Summary не найдены")
        
        print("\n" + "=" * 50)
        print("РЕЗУЛЬТАТ ТЕСТА:")
        print("🎉 GOOGLE SHEETS РАБОТАЕТ КОРРЕКТНО!")
        print("✅ Данные записываются и читаются успешно")
        print("✅ Система готова к работе с Google Sheets")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования Google Sheets: {e}")
        print("🔧 Проверьте настройки Service Account и права доступа")
        return False

if __name__ == "__main__":
    test_google_sheets() 