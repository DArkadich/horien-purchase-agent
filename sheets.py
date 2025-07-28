"""
Модуль для работы с Google Sheets API
"""

import json
import logging
from typing import Dict, List, Any
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from config import GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SPREADSHEET_ID, logger
from datetime import datetime

class GoogleSheets:
    """Класс для работы с Google Sheets"""
    
    def __init__(self):
        self.spreadsheet_id = GOOGLE_SPREADSHEET_ID
        self.credentials = None
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """
        Аутентификация в Google Sheets API
        """
        try:
            # Парсим JSON из переменной окружения
            service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
            
            # Создаем credentials
            self.credentials = Credentials.from_service_account_info(
                service_account_info,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            
            # Создаем сервис
            self.service = build('sheets', 'v4', credentials=self.credentials)
            
            logger.info("Успешная аутентификация в Google Sheets API")
            
        except Exception as e:
            logger.error(f"Ошибка аутентификации в Google Sheets API: {e}")
            raise
    
    def get_sheet_data(self, range_name: str) -> List[List[Any]]:
        """
        Получает данные из указанного диапазона листа
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            logger.info(f"Получено {len(values)} строк из диапазона {range_name}")
            return values
            
        except Exception as e:
            logger.error(f"Ошибка получения данных из Google Sheets: {e}")
            return []
    
    def update_sheet_data(self, range_name: str, values: List[List[Any]]):
        """
        Обновляет данные в указанном диапазоне листа
        """
        try:
            body = {
                'values': values
            }
            
            result = self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            logger.info(f"Обновлено {result.get('updatedCells')} ячеек в диапазоне {range_name}")
            
        except Exception as e:
            logger.error(f"Ошибка обновления данных в Google Sheets: {e}")
            raise
    
    def clear_sheet_range(self, range_name: str):
        """
        Очищает указанный диапазон листа
        """
        try:
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            logger.info(f"Очищен диапазон {range_name}")
            
        except Exception as e:
            logger.error(f"Ошибка очистки диапазона в Google Sheets: {e}")
            raise
    
    def format_header(self, range_name: str):
        """
        Форматирует заголовок таблицы
        """
        try:
            requests = [
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': 0,  # Предполагаем, что это первый лист
                            'startRowIndex': 0,
                            'endRowIndex': 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'backgroundColor': {
                                    'red': 0.2,
                                    'green': 0.6,
                                    'blue': 0.8
                                },
                                'textFormat': {
                                    'bold': True,
                                    'foregroundColor': {
                                        'red': 1.0,
                                        'green': 1.0,
                                        'blue': 1.0
                                    }
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                    }
                }
            ]
            
            body = {
                'requests': requests
            }
            
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
            logger.info(f"Отформатирован заголовок в диапазоне {range_name}")
            
        except Exception as e:
            logger.error(f"Ошибка форматирования заголовка: {e}")
    
    def write_purchase_report(self, report_data: List[Dict[str, Any]]):
        """
        Записывает отчет о закупках в Google Sheets
        """
        logger.info("Запись отчета о закупках в Google Sheets...")
        
        if not report_data:
            logger.warning("Нет данных для записи в таблицу")
            return
        
        # Подготавливаем заголовки
        headers = [
            'SKU',
            'Средняя продажа/день',
            'Текущий остаток',
            'Хватит на дней',
            'Рекомендуемое количество',
            'Минимальная партия',
            'Приоритет',
            'Дата последнего заказа'
        ]
        
        # Подготавливаем данные
        rows = [headers]
        for item in report_data:
            row = [
                item['sku'],
                item['avg_daily_sales'],
                item['current_stock'],
                item['days_until_stockout'],
                item['recommended_quantity'],
                item['moq'],
                item['urgency'],
                datetime.now().strftime('%Y-%m-%d')  # Дата последнего заказа
            ]
            rows.append(row)
        
        # Используем английское название листа для избежания проблем с кодировкой
        range_name = 'AI-Purchases!A1:H' + str(len(rows))
        
        try:
            # Очищаем существующие данные
            self.clear_sheet_range('AI-Purchases!A:H')
            
            # Записываем новые данные
            self.update_sheet_data(range_name, rows)
            
            # Форматируем заголовок
            self.format_header('AI-Purchases!A1:H1')
            
            logger.info(f"Отчет о закупках записан в Google Sheets: {len(report_data)} позиций")
            
        except Exception as e:
            logger.error(f"Ошибка записи отчета в Google Sheets: {e}")
            raise
    
    def get_last_order_dates(self) -> Dict[str, str]:
        """
        Получает даты последних заказов из таблицы
        """
        try:
            # Получаем данные из колонки с датами последних заказов
            range_name = 'AI-Purchases!H2:H'
            values = self.get_sheet_data(range_name)
            
            # Получаем SKU из первой колонки
            sku_range = 'AI-Purchases!A2:A'
            sku_values = self.get_sheet_data(sku_range)
            
            last_orders = {}
            for i, (sku_row, date_row) in enumerate(zip(sku_values, values)):
                if sku_row and date_row:
                    sku = sku_row[0]
                    date = date_row[0]
                    last_orders[sku] = date
            
            logger.info(f"Получено {len(last_orders)} дат последних заказов")
            return last_orders
            
        except Exception as e:
            logger.error(f"Ошибка получения дат последних заказов: {e}")
            return {}
    
    def create_summary_sheet(self, summary_data: Dict[str, Any]):
        """
        Создает сводный лист с общей статистикой
        """
        logger.info("Создание сводного листа...")
        
        # Подготавливаем данные для сводки
        summary_rows = [
            ['Сводка по закупкам'],
            [''],
            ['Дата отчета', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Всего позиций для закупки', summary_data.get('total_items', 0)],
            ['Высокий приоритет', summary_data.get('high_priority', 0)],
            ['Средний приоритет', summary_data.get('medium_priority', 0)],
            ['Низкий приоритет', summary_data.get('low_priority', 0)],
            ['Общая сумма закупки', summary_data.get('total_value', 0)],
            [''],
            ['Детализация по SKU:']
        ]
        
        # Добавляем детализацию
        for item in summary_data.get('items', []):
            summary_rows.append([
                item['sku'],
                f"Заказать {item['recommended_quantity']} шт",
                f"Хватит на {item['days_until_stockout']} дней"
            ])
        
        # Записываем в отдельный лист
        range_name = 'Summary!A1:C' + str(len(summary_rows))
        self.update_sheet_data(range_name, summary_rows)
        
        logger.info("Сводный лист создан") 