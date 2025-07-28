"""
Модуль для отправки уведомлений в Telegram
"""

import asyncio
import logging
from typing import Dict, List, Any
from telegram import Bot
from telegram.error import TelegramError
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, logger

class TelegramNotifier:
    """Класс для отправки уведомлений в Telegram"""
    
    def __init__(self):
        self.token = TELEGRAM_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.bot = None
        self._initialize_bot()
    
    def _initialize_bot(self):
        """
        Инициализирует Telegram бота
        """
        try:
            self.bot = Bot(token=self.token)
            logger.info("Telegram бот инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации Telegram бота: {e}")
            raise
    
    async def send_message(self, message: str) -> bool:
        """
        Отправляет сообщение в Telegram
        """
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'  # Используем HTML вместо Markdown
            )
            logger.info("Сообщение отправлено в Telegram")
            return True
            
        except TelegramError as e:
            logger.error(f"Ошибка отправки сообщения в Telegram: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке в Telegram: {e}")
            return False
    
    async def send_purchase_report(self, report_data: List[Dict[str, Any]], summary_data: Dict[str, Any]):
        """
        Отправляет отчет о закупках в Telegram
        """
        logger.info("Отправка отчета о закупках в Telegram...")
        
        if not report_data:
            message = "📊 <b>Отчет о закупках</b>\n\nНет товаров, требующих закупки."
            await self.send_message(message)
            return
        
        # Формируем основное сообщение
        message = "🛒 <b>Отчет о закупках</b>\n\n"
        
        # Добавляем сводку
        message += f"📈 <b>Сводка:</b>\n"
        message += f"• Всего позиций: {summary_data.get('total_items', 0)}\n"
        message += f"• Высокий приоритет: {summary_data.get('high_priority', 0)}\n"
        message += f"• Средний приоритет: {summary_data.get('medium_priority', 0)}\n"
        message += f"• Низкий приоритет: {summary_data.get('low_priority', 0)}\n\n"
        
        # Добавляем детализацию (первые 10 позиций)
        message += "📋 <b>Детализация:</b>\n"
        for i, item in enumerate(report_data[:10], 1):
            sku = item['sku']
            days_left = item['days_until_stockout']
            quantity = item['recommended_quantity']
            
            urgency_emoji = "🔴" if item['urgency'] == 'HIGH' else "🟡" if item['urgency'] == 'MEDIUM' else "🟢"
            
            message += f"{i}. {urgency_emoji} {sku}\n"
            message += f"   → хватит на {days_left} дней\n"
            message += f"   → заказать {quantity} шт\n\n"
        
        # Если есть еще позиции, добавляем информацию
        if len(report_data) > 10:
            message += f"... и еще {len(report_data) - 10} позиций\n\n"
        
        # Добавляем рекомендации
        message += "💡 <b>Рекомендации:</b>\n"
        high_priority = summary_data.get('high_priority', 0)
        if high_priority > 0:
            message += f"• 🔴 {high_priority} позиций требуют срочной закупки (< 10 дней)\n"
        
        medium_priority = summary_data.get('medium_priority', 0)
        if medium_priority > 0:
            message += f"• 🟡 {medium_priority} позиций требуют внимания (< 20 дней)\n"
        
        message += "\n📊 Полный отчет доступен в Google Sheets"
        
        # Отправляем сообщение
        success = await self.send_message(message)
        
        if success:
            logger.info(f"Отчет о закупках отправлен в Telegram: {len(report_data)} позиций")
        else:
            logger.error("Не удалось отправить отчет в Telegram")
    
    async def send_error_notification(self, error_message: str):
        """
        Отправляет уведомление об ошибке
        """
        # Очищаем сообщение от HTML тегов для безопасности
        clean_message = error_message.replace('<', '&lt;').replace('>', '&gt;')
        message = f"❌ <b>Ошибка в работе агента закупок</b>\n\n{clean_message}"
        await self.send_message(message)
    
    async def send_startup_notification(self):
        """
        Отправляет уведомление о запуске агента
        """
        from datetime import datetime
        message = f"🚀 <b>Агент закупок запущен</b>\n\nВремя запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        await self.send_message(message)
    
    async def send_completion_notification(self, execution_time: float, items_processed: int):
        """
        Отправляет уведомление о завершении работы
        """
        message = f"✅ <b>Агент закупок завершил работу</b>\n\n"
        message += f"⏱ Время выполнения: {execution_time:.2f} сек\n"
        message += f"📦 Обработано SKU: {items_processed}\n"
        message += f"🕐 Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await self.send_message(message)
    
    def send_message_sync(self, message: str) -> bool:
        """
        Синхронная версия отправки сообщения
        """
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.send_message(message))
        except RuntimeError:
            # Если нет активного event loop, создаем новый
            return asyncio.run(self.send_message(message))
    
    def send_purchase_report_sync(self, report_data: List[Dict[str, Any]], summary_data: Dict[str, Any]):
        """
        Синхронная версия отправки отчета о закупках
        """
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.send_purchase_report(report_data, summary_data))
        except RuntimeError:
            # Если нет активного event loop, создаем новый
            asyncio.run(self.send_purchase_report(report_data, summary_data))
    
    def send_error_notification_sync(self, error_message: str):
        """
        Синхронная версия отправки уведомления об ошибке
        """
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.send_error_notification(error_message))
        except RuntimeError:
            # Если нет активного event loop, создаем новый
            asyncio.run(self.send_error_notification(error_message))
    
    def send_startup_notification_sync(self):
        """
        Синхронная версия отправки уведомления о запуске
        """
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.send_startup_notification())
        except RuntimeError:
            # Если нет активного event loop, создаем новый
            asyncio.run(self.send_startup_notification())
    
    def send_completion_notification_sync(self, execution_time: float, items_processed: int):
        """
        Синхронная версия отправки уведомления о завершении
        """
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.send_completion_notification(execution_time, items_processed))
        except RuntimeError:
            # Если нет активного event loop, создаем новый
            asyncio.run(self.send_completion_notification(execution_time, items_processed)) 