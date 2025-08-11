#!/usr/bin/env python3
"""
Система кэширования данных для повышения надежности
"""

import os
import json
import sqlite3
import pickle
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from config import logger, CACHE_TTL_PRODUCTS, CACHE_TTL_SALES, CACHE_TTL_STOCKS, CACHE_TTL_ANALYTICS

class CacheManager:
    """Менеджер кэширования данных"""
    
    def __init__(self, cache_dir: str = "cache", db_path: str = "cache/cache.db"):
        self.cache_dir = cache_dir
        self.db_path = db_path
        
        # Создаем директорию кэша если её нет
        os.makedirs(cache_dir, exist_ok=True)
        
        # Создаем директорию для базы данных если её нет
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        # Инициализируем базу данных кэша
        self._init_cache_db()
    
    def _init_cache_db(self):
        """Инициализация базы данных кэша"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Создаем таблицу для метаданных кэша
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache_metadata (
                key_hash TEXT PRIMARY KEY,
                cache_key TEXT NOT NULL,
                cache_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                data_size INTEGER DEFAULT 0
            )
        ''')
        
        # Создаем индекс для быстрого поиска
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_cache_type_expires 
            ON cache_metadata(cache_type, expires_at)
        ''')
        
        conn.commit()
        conn.close()
        logger.info("База данных кэша инициализирована")
    
    def _get_cache_key_hash(self, cache_key: str) -> str:
        """Генерирует хеш для ключа кэша"""
        return hashlib.md5(cache_key.encode()).hexdigest()
    
    def _get_cache_file_path(self, cache_key: str) -> str:
        """Получает путь к файлу кэша"""
        key_hash = self._get_cache_key_hash(cache_key)
        return os.path.join(self.cache_dir, f"{key_hash}.cache")
    
    def set_cache(self, cache_key: str, data: Any, cache_type: str, 
                  ttl_hours: int = 24) -> bool:
        """
        Сохраняет данные в кэш
        
        Args:
            cache_key: Уникальный ключ кэша
            data: Данные для кэширования
            cache_type: Тип кэша (products, sales, stocks, analytics)
            ttl_hours: Время жизни кэша в часах
            
        Returns:
            True если успешно сохранено, False иначе
        """
        try:
            # Валидация TTL
            if ttl_hours is None:
                return False
            try:
                ttl_hours_val = float(ttl_hours)
            except Exception:
                return False
            if ttl_hours_val <= 0:
                return False
            key_hash = self._get_cache_key_hash(cache_key)
            cache_file = self._get_cache_file_path(cache_key)
            expires_at = datetime.now() + timedelta(hours=ttl_hours_val)
            
            # Сохраняем данные в файл
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
            
            # Сохраняем метаданные в БД
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO cache_metadata 
                (key_hash, cache_key, cache_type, expires_at, data_size)
                VALUES (?, ?, ?, ?, ?)
            ''', (key_hash, cache_key, cache_type, expires_at, len(pickle.dumps(data))))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Данные сохранены в кэш: {cache_key} (тип: {cache_type}, TTL: {ttl_hours}ч)")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении в кэш: {e}")
            return False
    
    def get_cache(self, cache_key: str) -> Optional[Any]:
        """
        Получает данные из кэша
        
        Args:
            cache_key: Уникальный ключ кэша
            
        Returns:
            Данные из кэша или None если не найдено/истекло
        """
        try:
            key_hash = self._get_cache_key_hash(cache_key)
            cache_file = self._get_cache_file_path(cache_key)
            
            # Проверяем существование файла
            if not os.path.exists(cache_file):
                return None
            
            # Проверяем метаданные в БД
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT expires_at FROM cache_metadata 
                WHERE key_hash = ?
            ''', (key_hash,))
            
            result = cursor.fetchone()
            if not result:
                conn.close()
                return None
            
            expires_at = datetime.fromisoformat(result[0])
            
            # Проверяем не истек ли кэш
            if datetime.now() > expires_at:
                logger.info(f"Кэш истек: {cache_key}")
                self._remove_cache(cache_key)
                conn.close()
                return None
            
            # Обновляем статистику доступа
            cursor.execute('''
                UPDATE cache_metadata 
                SET last_accessed = CURRENT_TIMESTAMP, access_count = access_count + 1
                WHERE key_hash = ?
            ''', (key_hash,))
            
            conn.commit()
            conn.close()
            
            # Загружаем данные из файла
            with open(cache_file, 'rb') as f:
                data = pickle.load(f)
            
            logger.info(f"Данные загружены из кэша: {cache_key}")
            return data
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке из кэша: {e}")
            return None
    
    def _remove_cache(self, cache_key: str) -> bool:
        """Удаляет кэш"""
        try:
            key_hash = self._get_cache_key_hash(cache_key)
            cache_file = self._get_cache_file_path(cache_key)
            
            # Удаляем файл
            if os.path.exists(cache_file):
                os.remove(cache_file)
            
            # Удаляем метаданные из БД
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM cache_metadata WHERE key_hash = ?', (key_hash,))
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при удалении кэша: {e}")
            return False
    
    def clear_expired_cache(self) -> int:
        """
        Очищает истекший кэш
        
        Returns:
            Количество удаленных записей
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Находим истекшие записи
            cursor.execute('''
                SELECT cache_key FROM cache_metadata 
                WHERE expires_at < CURRENT_TIMESTAMP
            ''')
            
            expired_keys = [row[0] for row in cursor.fetchall()]
            
            # Удаляем истекшие записи
            for cache_key in expired_keys:
                self._remove_cache(cache_key)
            
            conn.close()
            
            logger.info(f"Удалено {len(expired_keys)} истекших записей кэша")
            return len(expired_keys)
            
        except Exception as e:
            logger.error(f"Ошибка при очистке кэша: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Получает статистику кэша"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Общая статистика
            cursor.execute('SELECT COUNT(*) FROM cache_metadata')
            total_entries = cursor.fetchone()[0]
            
            # Статистика по типам
            cursor.execute('''
                SELECT cache_type, COUNT(*) as count, 
                       SUM(data_size) as total_size,
                       AVG(access_count) as avg_access
                FROM cache_metadata 
                GROUP BY cache_type
            ''')
            
            type_stats = {}
            for row in cursor.fetchall():
                type_stats[row[0]] = {
                    'count': row[1],
                    'total_size': row[2] or 0,
                    'avg_access': row[3] or 0
                }
            
            # Истекшие записи
            cursor.execute('''
                SELECT COUNT(*) FROM cache_metadata 
                WHERE expires_at < CURRENT_TIMESTAMP
            ''')
            expired_count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_entries': total_entries,
                'expired_entries': expired_count,
                'type_stats': type_stats
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики кэша: {e}")
            return {}
    
    def clear_all_cache(self) -> int:
        """
        Очищает весь кэш
        
        Returns:
            Количество удаленных записей
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем все ключи
            cursor.execute('SELECT cache_key FROM cache_metadata')
            all_keys = [row[0] for row in cursor.fetchall()]
            
            # Удаляем все записи
            for cache_key in all_keys:
                self._remove_cache(cache_key)
            
            conn.close()
            
            logger.info(f"Удалено {len(all_keys)} записей кэша")
            return len(all_keys)
            
        except Exception as e:
            logger.error(f"Ошибка при очистке всего кэша: {e}")
            return 0

class CachedAPIClient:
    """Клиент API с кэшированием"""
    
    def __init__(self, api_client, cache_manager: CacheManager):
        self.api_client = api_client
        self.cache_manager = cache_manager
        # Флаг для отключения кэша в тестах/окружении
        self.cache_enabled = True
    
    def get_products_with_cache(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Получает товары с кэшированием
        """
        cache_key = "products_list"
        
        # Проверяем кэш если не принудительное обновление
        if self.cache_enabled and not force_refresh:
            cached_data = self.cache_manager.get_cache(cache_key)
            if cached_data:
                logger.info("Используем кэшированные данные о товарах")
                return cached_data
        
        # Получаем свежие данные
        logger.info("Получение свежих данных о товарах")
        fresh_data = self.api_client.get_products()
        
        if self.cache_enabled and fresh_data:
            # Сохраняем в кэш на 2 часа
            self.cache_manager.set_cache(cache_key, fresh_data, "products", ttl_hours=CACHE_TTL_PRODUCTS)
            logger.info("Свежие данные о товарах сохранены в кэш")
        
        return fresh_data
    
    def get_sales_data_with_cache(self, days: int = 180, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Получает данные о продажах с кэшированием
        """
        cache_key = f"sales_data_{days}days"
        
        # Проверяем кэш если не принудительное обновление
        if self.cache_enabled and not force_refresh:
            cached_data = self.cache_manager.get_cache(cache_key)
            if cached_data:
                logger.info("Используем кэшированные данные о продажах")
                return cached_data
        
        # Получаем свежие данные
        logger.info("Получение свежих данных о продажах")
        fresh_data = self.api_client.get_sales_data(days)
        
        if self.cache_enabled and fresh_data:
            # Сохраняем в кэш на 1 час
            self.cache_manager.set_cache(cache_key, fresh_data, "sales", ttl_hours=CACHE_TTL_SALES)
            logger.info("Свежие данные о продажах сохранены в кэш")
        
        return fresh_data
    
    def get_stocks_data_with_cache(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Получает данные об остатках с кэшированием
        """
        cache_key = "stocks_data"
        
        # Проверяем кэш если не принудительное обновление
        if self.cache_enabled and not force_refresh:
            cached_data = self.cache_manager.get_cache(cache_key)
            if cached_data:
                logger.info("Используем кэшированные данные об остатках")
                return cached_data
        
        # Получаем свежие данные
        logger.info("Получение свежих данных об остатках")
        fresh_data = self.api_client.get_stocks_data()
        
        if self.cache_enabled and fresh_data:
            # Сохраняем в кэш на 30 минут
            self.cache_manager.set_cache(cache_key, fresh_data, "stocks", ttl_hours=CACHE_TTL_STOCKS)
            logger.info("Свежие данные об остатках сохранены в кэш")
        
        return fresh_data
    
    def get_analytics_data_with_cache(self, days: int = 180, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Получает аналитические данные с кэшированием
        """
        cache_key = f"analytics_data_{days}days"
        
        # Проверяем кэш если не принудительное обновление
        if self.cache_enabled and not force_refresh:
            cached_data = self.cache_manager.get_cache(cache_key)
            if cached_data:
                logger.info("Используем кэшированные аналитические данные")
                return cached_data
        
        # Получаем свежие данные
        logger.info("Получение свежих аналитических данных")
        fresh_data = self.api_client.get_analytics_data(days)
        
        if self.cache_enabled and fresh_data:
            # Сохраняем в кэш на 1 час
            self.cache_manager.set_cache(cache_key, fresh_data, "analytics", ttl_hours=CACHE_TTL_ANALYTICS)
            logger.info("Свежие аналитические данные сохранены в кэш")
        
        return fresh_data 