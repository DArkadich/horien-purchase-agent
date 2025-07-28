#!/usr/bin/env python3
"""
Система отслеживания остатков товаров
Собирает данные об остатках каждый день для анализа изменений
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dotenv import load_dotenv
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

class StockTracker:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Создаем папку data если её нет
            os.makedirs("data", exist_ok=True)
            db_path = "data/stock_history.db"
        
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных для хранения истории остатков"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Создаем таблицу для хранения истории остатков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                sku TEXT NOT NULL,
                stock INTEGER NOT NULL,
                reserved INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Создаем индекс для быстрого поиска
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_date_sku 
            ON stock_history(date, sku)
        ''')
        
        conn.commit()
        conn.close()
        logger.info("База данных истории остатков инициализирована")
    
    def save_stock_data(self, stock_data: List[Dict[str, Any]]):
        """Сохраняет данные об остатках в базу данных"""
        if not stock_data:
            logger.warning("Нет данных об остатках для сохранения")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        for item in stock_data:
            cursor.execute('''
                INSERT INTO stock_history (date, sku, stock, reserved)
                VALUES (?, ?, ?, ?)
            ''', (
                today,
                item.get("sku", ""),
                item.get("stock", 0),
                item.get("reserved", 0)
            ))
        
        conn.commit()
        conn.close()
        logger.info(f"Сохранено {len(stock_data)} записей об остатках за {today}")
    
    def get_stock_history(self, sku: str, days: int = 30) -> List[Dict[str, Any]]:
        """Получает историю остатков для конкретного SKU"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        cursor.execute('''
            SELECT date, stock, reserved 
            FROM stock_history 
            WHERE sku = ? AND date >= ?
            ORDER BY date ASC
        ''', (sku, start_date))
        
        results = cursor.fetchall()
        conn.close()
        
        history = []
        for row in results:
            history.append({
                "date": row[0],
                "stock": row[1],
                "reserved": row[2]
            })
        
        return history
    
    def estimate_sales_from_stock_changes(self, days: int = 180) -> List[Dict[str, Any]]:
        """Оценивает продажи на основе изменений остатков"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Получаем все уникальные SKU
        cursor.execute('SELECT DISTINCT sku FROM stock_history WHERE date >= ?', (start_date,))
        skus = [row[0] for row in cursor.fetchall()]
        
        sales_data = []
        
        for sku in skus:
            # Получаем историю остатков для этого SKU
            cursor.execute('''
                SELECT date, stock 
                FROM stock_history 
                WHERE sku = ? AND date >= ?
                ORDER BY date ASC
            ''', (sku, start_date))
            
            stock_history = cursor.fetchall()
            
            # Анализируем изменения остатков
            for i in range(1, len(stock_history)):
                prev_date, prev_stock = stock_history[i-1]
                curr_date, curr_stock = stock_history[i]
                
                # Если остатки уменьшились - это продажи
                if prev_stock > curr_stock:
                    sold_quantity = prev_stock - curr_stock
                    # Оцениваем выручку (примерная цена)
                    estimated_price = 1000  # Можно сделать более сложную логику
                    revenue = sold_quantity * estimated_price
                    
                    sales_data.append({
                        "sku": sku,
                        "date": curr_date,
                        "quantity": sold_quantity,
                        "revenue": revenue
                    })
        
        conn.close()
        logger.info(f"Оценено {len(sales_data)} записей о продажах на основе изменений остатков")
        return sales_data
    
    def get_all_skus(self) -> List[str]:
        """Получает список всех SKU в базе данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT DISTINCT sku FROM stock_history')
        skus = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return skus

def main():
    """Основная функция для ежедневного сбора данных"""
    tracker = StockTracker()
    
    # Здесь нужно будет добавить получение данных из Ozon API
    # Пока используем тестовые данные
    test_stock_data = [
        {"sku": "TEST001", "stock": 10, "reserved": 2},
        {"sku": "TEST002", "stock": 15, "reserved": 1},
        {"sku": "TEST003", "stock": 5, "reserved": 0}
    ]
    
    tracker.save_stock_data(test_stock_data)
    logger.info("Ежедневный сбор данных об остатках завершен")

if __name__ == "__main__":
    main() 