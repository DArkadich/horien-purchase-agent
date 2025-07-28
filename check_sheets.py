#!/usr/bin/env python3
"""
Скрипт для проверки данных в Google Sheets
"""

import json
import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from config import GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SPREADSHEET_ID

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_sheets_data():
    """Проверяет данные в Google Sheets"""
    
    try:
        # Аутентификация
        service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        credentials = Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        service = build('sheets', 'v4', credentials=credentials)
        
        # Получаем информацию о таблице
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=GOOGLE_SPREADSHEET_ID
        ).execute()
        
        print("=" * 50)
        print("ПРОВЕРКА GOOGLE SHEETS")
        print("=" * 50)
        
        # Показываем все листы
        sheets = spreadsheet['sheets']
        print(f"Всего листов: {len(sheets)}")
        for i, sheet in enumerate(sheets, 1):
            title = sheet['properties']['title']
            print(f"{i}. {title}")
        
        print("\n" + "=" * 50)
        
        # Проверяем данные в Sheet1
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=GOOGLE_SPREADSHEET_ID,
                range='Sheet1!A1:H10'
            ).execute()
            
            values = result.get('values', [])
            print("ДАННЫЕ В SHEET1:")
            print(f"Найдено строк: {len(values)}")
            
            if values:
                for i, row in enumerate(values, 1):
                    print(f"Строка {i}: {row}")
            else:
                print("Данных в Sheet1 нет")
                
        except Exception as e:
            print(f"Ошибка чтения Sheet1: {e}")
        
        print("\n" + "=" * 50)
        
        # Проверяем данные в Summary
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=GOOGLE_SPREADSHEET_ID,
                range='Summary!A1:C10'
            ).execute()
            
            values = result.get('values', [])
            print("ДАННЫЕ В SUMMARY:")
            print(f"Найдено строк: {len(values)}")
            
            if values:
                for i, row in enumerate(values, 1):
                    print(f"Строка {i}: {row}")
            else:
                print("Данных в Summary нет")
                
        except Exception as e:
            print(f"Ошибка чтения Summary: {e}")
        
        print("=" * 50)
        
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    check_sheets_data() 