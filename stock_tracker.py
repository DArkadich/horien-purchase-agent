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
        logger.info(f"Попытка сохранения {len(stock_data) if stock_data else 0} записей об остатках")
        
        if not stock_data:
            logger.warning("Нет данных об остатках для сохранения")
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            today = datetime.now().strftime("%Y-%m-%d")
            logger.info(f"Сохраняем данные за дату: {today}")
            
            saved_count = 0
            for item in stock_data:
                sku = item.get("sku", "")
                stock = item.get("stock", 0)
                reserved = item.get("reserved", 0)
                
                cursor.execute('''
                    INSERT INTO stock_history (date, sku, stock, reserved)
                    VALUES (?, ?, ?, ?)
                ''', (today, sku, stock, reserved))
                saved_count += 1
            
            conn.commit()
            logger.info(f"Транзакция зафиксирована в базе данных")
            conn.close()
            logger.info(f"Успешно сохранено {saved_count} записей об остатках за {today}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения данных об остатках: {e}")
            logger.error(f"Тип ошибки: {type(e).__name__}")
            import traceback
            logger.error(f"Полный traceback: {traceback.format_exc()}")
            if 'conn' in locals():
                try:
                    conn.rollback()
                    conn.close()
                except:
                    pass
    
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
        
        # Проверяем, какие даты есть в БД
        cursor.execute('SELECT DISTINCT date FROM stock_history ORDER BY date')
        available_dates = [row[0] for row in cursor.fetchall()]
        logger.info(f"Доступные даты в БД: {available_dates}")
        
        if not available_dates:
            logger.warning("В БД нет данных об остатках")
            conn.close()
            return []
        
        # Fallback логика: используем все доступные данные
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        logger.info(f"Запрашиваем данные об остатках с {start_date} (за {days} дней)")
        
        # Получаем все уникальные SKU с запрашиваемой даты
        cursor.execute('SELECT DISTINCT sku FROM stock_history WHERE date >= ?', (start_date,))
        skus = [row[0] for row in cursor.fetchall()]
        
        # Если нет данных за запрашиваемый период, используем все доступные данные
        if not skus:
            logger.warning(f"Нет данных с {start_date}, используем все доступные данные")
            cursor.execute('SELECT DISTINCT sku FROM stock_history')
            skus = [row[0] for row in cursor.fetchall()]
            start_date = available_dates[0]  # Используем самую раннюю доступную дату
        
        logger.info(f"Найдено {len(skus)} SKU с данными с {start_date}")
        logger.info(f"Используем данные с {start_date} по {available_dates[-1]}")
        logger.info(f"Список SKU для анализа: {skus[:5]}...")  # Показываем первые 5 SKU
        
        sales_data = []
        
        for sku in skus:
            # Получаем историю остатков для этого SKU с учётом времени создания записи
            # Берём последнее значение за день (по created_at) для корректной дневной динамики
            cursor.execute('''
                SELECT date, stock, created_at
                FROM stock_history
                WHERE sku = ? AND date >= ?
                ORDER BY date ASC, datetime(created_at) ASC
            ''', (sku, start_date))

            raw_rows = cursor.fetchall()

            # Дедупликация по дате: оставляем последнюю запись дня
            latest_by_date: Dict[str, Dict[str, Any]] = {}
            for row in raw_rows:
                d, stock_value, created = row[0], row[1], row[2]
                latest_by_date[d] = {
                    'date': d,
                    'stock': stock_value,
                    'created_at': created
                }

            stock_history = [(v['date'], v['stock']) for v in sorted(latest_by_date.values(), key=lambda x: x['date'])]
            
            logger.info(f"Анализ SKU {sku}: найдено {len(stock_history)} записей об остатках")
            
            if len(stock_history) < 2:
                logger.info(f"SKU {sku}: недостаточно данных для анализа (нужно минимум 2 записи)")
                continue
            
            # Показываем историю остатков для отладки
            logger.info(f"SKU {sku} история остатков: {stock_history}")
            
            # Анализируем изменения остатков между уникальными днями
            for i in range(1, len(stock_history)):
                prev_date, prev_stock = stock_history[i-1]
                curr_date, curr_stock = stock_history[i]
                
                logger.info(f"SKU {sku}: {prev_date}({prev_stock}) -> {curr_date}({curr_stock})")
                
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
                    logger.info(f"ПРОДАЖА {sku}: {sold_quantity} шт. ({prev_stock} -> {curr_stock}) на дату {curr_date}")
                
                # Если остатки не изменились и товар был в наличии - день без продаж (учитываем для статистики, но не раздуваем записи)
                elif prev_stock == curr_stock and curr_stock > 0:
                    # Не добавляем запись в sales_data, чтобы не раздувать нулевые продажи
                    logger.info(f"День без продаж {sku}: {curr_stock} шт. на дату {curr_date}")
                
                # Если остатки увеличились - это поставка, НЕ учитываем как продажи
                elif prev_stock < curr_stock:
                    supplied_quantity = curr_stock - prev_stock
                    logger.info(f"Поставка {sku}: +{supplied_quantity} шт. ({prev_stock} -> {curr_stock}) на дату {curr_date}")
                    # НЕ добавляем в sales_data - поставки не являются продажами
                
                # Если остатки не изменились и товар отсутствует - это день без остатков
                elif prev_stock == curr_stock and curr_stock == 0:
                    logger.debug(f"День без остатков {sku}: 0 шт. на дату {curr_date}")
                    # НЕ добавляем в sales_data - нет товара для продажи
        
        conn.close()
        logger.info(f"Оценено {len(sales_data)} записей о продажах на основе изменений остатков")
        
        # Отладочная информация о найденных продажах
        if sales_data:
            unique_dates = set(record['date'] for record in sales_data)
            unique_skus = set(record['sku'] for record in sales_data)
            total_quantity = sum(record['quantity'] for record in sales_data)
            logger.info(f"Найдены продажи за даты: {sorted(unique_dates)}")
            logger.info(f"SKU с продажами: {len(unique_skus)}")
            logger.info(f"Общее количество проданных единиц: {total_quantity}")
            logger.info(f"Примеры записей о продажах: {sales_data[:3]}")
        else:
            logger.warning("Не найдено изменений остатков для оценки продаж")
        
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
    
    # TODO: Интегрировать с Ozon API для получения реальных данных об остатках
    # Пока функция не используется в production
    logger.info("StockTracker main() - требуется интеграция с API для получения реальных данных")

if __name__ == "__main__":
    main() 