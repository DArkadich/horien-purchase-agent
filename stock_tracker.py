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
import random

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
            
            if len(stock_history) < 2:
                continue
            
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
                    logger.debug(f"Продажа {sku}: {sold_quantity} шт. ({prev_stock} -> {curr_stock})")
                
                # Если остатки не изменились и товар был в наличии - это день без продаж
                elif prev_stock == curr_stock and curr_stock > 0:
                    sales_data.append({
                        "sku": sku,
                        "date": curr_date,
                        "quantity": 0,
                        "revenue": 0
                    })
                    logger.debug(f"День без продаж {sku}: {curr_stock} шт.")
                
                # Если остатки увеличились - это поставка, НЕ учитываем как продажи
                elif prev_stock < curr_stock:
                    supplied_quantity = curr_stock - prev_stock
                    logger.info(f"Поставка {sku}: +{supplied_quantity} шт. ({prev_stock} -> {curr_stock})")
                    # НЕ добавляем в sales_data - поставки не являются продажами
                
                # Если остатки не изменились и товар отсутствует - это день без остатков
                elif prev_stock == curr_stock and curr_stock == 0:
                    logger.debug(f"День без остатков {sku}: 0 шт.")
                    # НЕ добавляем в sales_data - нет товара для продажи
        
        conn.close()
        logger.info(f"Оценено {len(sales_data)} записей о продажах на основе изменений остатков")
        return sales_data
    
    def generate_realistic_sales_data(self, days: int = 180) -> List[Dict[str, Any]]:
        """Генерирует реалистичные синтетические данные о продажах для тестирования"""
        logger.info(f"Генерация реалистичных синтетических данных о продажах за {days} дней...")
        
        sales_data = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Получаем список всех SKU из базы данных
        skus = self.get_all_skus()
        
        if not skus:
            logger.warning("Нет SKU в базе данных, создаем тестовые SKU")
            skus = ['300050', '300075', '300125', '300150', '300175', '300200', '300225', '300250']
        
        for sku in skus:
            # Генерируем реалистичные продажи для каждого SKU
            base_daily_sales = random.uniform(0.5, 3.0)  # Базовая дневная продажа
            weekly_pattern = [1.2, 1.0, 0.8, 0.9, 1.1, 1.3, 1.4]  # Недельный паттерн (пн-вс)
            monthly_trend = random.uniform(0.8, 1.2)  # Месячный тренд
            
            current_date = start_date
            while current_date <= end_date:
                # Базовые продажи
                daily_sales = base_daily_sales
                
                # Применяем недельный паттерн
                day_of_week = current_date.weekday()
                weekly_multiplier = weekly_pattern[day_of_week]
                daily_sales *= weekly_multiplier
                
                # Применяем месячный тренд
                month_progress = current_date.day / 30.0
                monthly_multiplier = 1 + (monthly_trend - 1) * month_progress
                daily_sales *= monthly_multiplier
                
                # Добавляем случайные колебания
                noise = random.uniform(0.7, 1.3)
                daily_sales *= noise
                
                # Округляем до целых чисел
                quantity = max(0, int(round(daily_sales)))
                
                # Оцениваем выручку (примерная цена)
                estimated_price = random.uniform(800, 1500)
                revenue = quantity * estimated_price
                
                if quantity > 0:  # Добавляем только дни с продажами
                    sales_data.append({
                        "sku": sku,
                        "date": current_date.strftime("%Y-%m-%d"),
                        "quantity": quantity,
                        "revenue": revenue
                    })
                
                current_date += timedelta(days=1)
        
        logger.info(f"Сгенерировано {len(sales_data)} реалистичных записей о продажах")
        return sales_data
    
    def generate_realistic_stocks_data(self) -> List[Dict[str, Any]]:
        """Генерирует реалистичные синтетические данные об остатках для тестирования"""
        logger.info("Генерация реалистичных синтетических данных об остатках...")
        
        stocks_data = []
        
        # Получаем список всех SKU из базы данных
        skus = self.get_all_skus()
        
        if not skus:
            logger.warning("Нет SKU в базе данных, создаем тестовые SKU")
            skus = ['300050', '300075', '300125', '300150', '300175', '300200', '300225', '300250']
        
        for sku in skus:
            # Генерируем реалистичные остатки для каждого SKU
            base_stock = random.randint(5, 50)  # Базовый остаток
            reserved = random.randint(0, min(5, base_stock))  # Зарезервировано
            
            # Добавляем случайные колебания
            stock_variation = random.uniform(0.7, 1.3)
            final_stock = max(0, int(round(base_stock * stock_variation)))
            
            # Генерируем название товара на основе SKU
            if sku.startswith('300'):
                name = f"Контактные линзы Horien на 1 день -{sku[3:5]},{sku[5:]} 30 шт."
            elif sku.startswith('305'):
                name = f"Контактные линзы Horien Diamond55 на месяц -{sku[3:5]},{sku[5:]} 3 шт."
            elif sku.startswith('60'):
                name = f"Контактные линзы Horien Diamond55 на месяц -{sku[2:4]},{sku[4:]} 6 шт."
            else:
                name = f"Товар {sku}"
            
            stocks_data.append({
                "sku": sku,
                "name": name,
                "stock": final_stock,
                "reserved": reserved
            })
        
        logger.info(f"Сгенерировано {len(stocks_data)} реалистичных записей об остатках")
        return stocks_data
    
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
    
    # TODO: Интегрировать с Ozon API для получения реальных данных об остатках
    # Пока функция не используется в production
    logger.info("StockTracker main() - требуется интеграция с API для получения реальных данных")

if __name__ == "__main__":
    main() 