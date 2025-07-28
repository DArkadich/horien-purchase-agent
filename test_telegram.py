#!/usr/bin/env python3
"""
Тест Telegram для проверки реальных данных
"""

import logging
from telegram_notify import TelegramNotifier
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_telegram():
    """Тестирует Telegram с реальными данными"""
    
    print("=" * 50)
    print("ТЕСТ TELEGRAM")
    print("=" * 50)
    
    # Проверяем наличие настроек
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "your_telegram_bot_token_here":
        print("❌ TELEGRAM_TOKEN не настроен")
        print("Настройте токен бота в .env файле")
        return False
    
    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == "your_chat_id_here":
        print("❌ TELEGRAM_CHAT_ID не настроен")
        print("Настройте Chat ID в .env файле")
        return False
    
    print("✅ Telegram настройки присутствуют")
    
    try:
        # Создаем экземпляр Telegram
        telegram = TelegramNotifier()
        print("✅ Telegram объект создан")
        
        # Тестируем отправку простого сообщения
        print("\n📱 Тестирование отправки сообщения...")
        test_message = "🧪 Тестовое сообщение от агента закупок Horiens"
        
        success = telegram.send_message_sync(test_message)
        if success:
            print("✅ Тестовое сообщение отправлено")
        else:
            print("❌ Ошибка отправки тестового сообщения")
            return False
        
        # Тестируем отправку отчета
        print("\n📊 Тестирование отправки отчета...")
        
        test_report = [
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
        
        test_summary = {
            'total_items': 2,
            'high_priority': 1,
            'medium_priority': 1,
            'low_priority': 0,
            'total_value': 350,
            'items': test_report
        }
        
        telegram.send_purchase_report_sync(test_report, test_summary)
        print("✅ Тестовый отчет отправлен")
        
        # Тестируем уведомление о завершении
        print("\n✅ Тестирование уведомления о завершении...")
        telegram.send_completion_notification_sync(5.2, 2)
        print("✅ Уведомление о завершении отправлено")
        
        print("\n" + "=" * 50)
        print("РЕЗУЛЬТАТ ТЕСТА:")
        print("🎉 TELEGRAM РАБОТАЕТ КОРРЕКТНО!")
        print("✅ Сообщения отправляются успешно")
        print("✅ Система готова к работе с Telegram")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования Telegram: {e}")
        print("🔧 Проверьте токен бота и Chat ID")
        return False

if __name__ == "__main__":
    test_telegram() 