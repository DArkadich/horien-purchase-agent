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
            
            # Проверяем и создаем необходимые листы
            self._ensure_sheets_exist()
            
        except Exception as e:
            logger.error(f"Ошибка аутентификации в Google Sheets API: {e}")
            raise
    
    def _ensure_sheets_exist(self):
        """
        Проверяет существование необходимых листов и создает их при необходимости
        """
        try:
            # Получаем информацию о таблице
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            existing_sheets = [sheet['properties']['title'] for sheet in spreadsheet['sheets']]
            logger.info(f"Существующие листы: {existing_sheets}")
            
            # Проверяем наличие необходимых листов
            required_sheets = ['Sheet1', 'Summary']
            missing_sheets = [sheet for sheet in required_sheets if sheet not in existing_sheets]
            
            if missing_sheets:
                logger.info(f"Создаем недостающие листы: {missing_sheets}")
                
                requests = []
                for sheet_name in missing_sheets:
                    requests.append({
                        'addSheet': {
                            'properties': {
                                'title': sheet_name
                            }
                        }
                    })
                
                if requests:
                    body = {'requests': requests}
                    self.service.spreadsheets().batchUpdate(
                        spreadsheetId=self.spreadsheet_id,
                        body=body
                    ).execute()
                    
                    logger.info(f"Созданы листы: {missing_sheets}")
            else:
                logger.info("Все необходимые листы существуют")
                
        except Exception as e:
            logger.error(f"Ошибка проверки/создания листов: {e}")
            # Не прерываем выполнение, продолжаем работу
            pass
    
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
            # Используем простой подход без кавычек
            if "!" in range_name:
                sheet_name, cell_range = range_name.split("!", 1)
                # Убираем кавычки если они есть
                sheet_name = sheet_name.strip("'")
                range_name = f"{sheet_name}!{cell_range}"
            
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            logger.info(f"Очищен диапазон {range_name}")
            
        except Exception as e:
            logger.error(f"Ошибка очистки диапазона в Google Sheets: {e}")
            # Не прерываем выполнение, продолжаем работу
            pass
    
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
            # Не прерываем выполнение, продолжаем работу
            pass
    
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
        
        # Используем простой подход без кавычек
        range_name = f"Sheet1!A1:H{len(rows)}"
        
        try:
            # Очищаем существующие данные (конкретный диапазон)
            clear_range = f"Sheet1!A1:H{len(rows) + 10}"  # Очищаем с запасом
            self.clear_sheet_range(clear_range)
            
            # Записываем новые данные
            self.update_sheet_data(range_name, rows)
            
            # Форматируем заголовок
            self.format_header("Sheet1!A1:H1")
            
            logger.info(f"Отчет о закупках записан в Google Sheets: {len(report_data)} позиций")
            
        except Exception as e:
            logger.error(f"Ошибка записи отчета в Google Sheets: {e}")
            # Не прерываем выполнение, продолжаем работу
            pass
    
    def get_last_order_dates(self) -> Dict[str, str]:
        """
        Получает даты последних заказов из таблицы
        """
        try:
            # Получаем данные из колонки с датами последних заказов
            range_name = "Sheet1!H2:H"
            values = self.get_sheet_data(range_name)
            
            # Получаем SKU из первой колонки
            sku_range = "Sheet1!A2:A"
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
        
        # Записываем в отдельный лист без кавычек
        range_name = f"Summary!A1:C{len(summary_rows)}"
        self.update_sheet_data(range_name, summary_rows)
        
        logger.info("Сводный лист создан") 
    
    def write_stock_data(self, stock_data: List[Dict[str, Any]]):
        """
        Записывает реальные данные об остатках в Google Sheets
        """
        logger.info("Запись данных об остатках в Google Sheets...")
        
        if not stock_data:
            logger.warning("Нет данных об остатках для записи в таблицу")
            return
        
        # Подготавливаем заголовки
        headers = [
            'SKU',
            'Остаток',
            'Зарезервировано',
            'Доступно',
            'Дата обновления'
        ]
        
        # Подготавливаем данные
        rows = [headers]
        for item in stock_data:
            available = item.get('stock', 0) - item.get('reserved', 0)
            row = [
                item.get('sku', ''),
                item.get('stock', 0),
                item.get('reserved', 0),
                available,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
            rows.append(row)
        
        # Записываем в лист "Остатки"
        range_name = f"Остатки!A1:E{len(rows)}"
        
        try:
            # Очищаем существующие данные
            clear_range = f"Остатки!A1:E{len(rows) + 10}"
            self.clear_sheet_range(clear_range)
            
            # Записываем новые данные
            self.update_sheet_data(range_name, rows)
            
            # Форматируем заголовок
            self.format_header("Остатки!A1:E1")
            
            logger.info(f"Данные об остатках записаны в Google Sheets: {len(stock_data)} позиций")
            
        except Exception as e:
            logger.error(f"Ошибка записи данных об остатках в Google Sheets: {e}")
            pass
    
    def clear_all_synthetic_data(self):
        """
        Очищает все синтетические данные из таблицы
        """
        logger.info("Очистка синтетических данных из Google Sheets...")
        
        try:
            # Очищаем основные листы
            sheets_to_clear = ['Sheet1', 'Summary', 'Остатки']
            
            for sheet_name in sheets_to_clear:
                try:
                    # Очищаем весь лист
                    range_name = f"{sheet_name}!A:Z"
                    self.clear_sheet_range(range_name)
                    logger.info(f"Очищен лист: {sheet_name}")
                except Exception as e:
                    logger.warning(f"Не удалось очистить лист {sheet_name}: {e}")
            
            # Записываем заголовок о том, что данные очищены
            header_data = [
                ['Данные очищены'],
                [''],
                ['Дата очистки', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                ['Примечание', 'Синтетические данные удалены. Ожидание реальных данных.']
            ]
            
            self.update_sheet_data("Sheet1!A1:D4", header_data)
            
            logger.info("Синтетические данные очищены из Google Sheets")
            
        except Exception as e:
            logger.error(f"Ошибка очистки синтетических данных: {e}")
            pass 