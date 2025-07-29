#!/usr/bin/env python3
"""
Система мониторинга доступности API
"""

import time
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio
from config import logger, API_MONITORING_DB_PATH, API_HEALTHY_THRESHOLD, API_DEGRADED_THRESHOLD, API_MONITORING_INTERVAL

class APIStatus(Enum):
    """Статусы API"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"

@dataclass
class APIHealthCheck:
    """Результат проверки здоровья API"""
    timestamp: datetime
    endpoint: str
    status: APIStatus
    response_time: float
    status_code: Optional[int]
    error_message: Optional[str]
    retry_count: int = 0

class APIMonitor:
    """Монитор доступности API"""
    
    def __init__(self, db_path: str = API_MONITORING_DB_PATH):
        self.db_path = db_path
        self._init_db()
        
        # Настройки мониторинга
        self.healthy_threshold = API_HEALTHY_THRESHOLD  # мс
        self.degraded_threshold = API_DEGRADED_THRESHOLD  # мс
        self.max_retries = 3
        self.check_interval = API_MONITORING_INTERVAL  # 5 минут
        
        # Статистика
        self.uptime_percentage = 0.0
        self.avg_response_time = 0.0
        self.total_checks = 0
        self.failed_checks = 0
    
    def _init_db(self):
        """Инициализация базы данных для мониторинга"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица для результатов проверок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                endpoint TEXT NOT NULL,
                status TEXT NOT NULL,
                response_time REAL,
                status_code INTEGER,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0
            )
        ''')
        
        # Таблица для инцидентов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                endpoint TEXT NOT NULL,
                status TEXT NOT NULL,
                duration_minutes INTEGER,
                description TEXT
            )
        ''')
        
        # Индексы для быстрого поиска
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_health_timestamp 
            ON api_health_checks(timestamp)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_health_endpoint 
            ON api_health_checks(endpoint)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_incidents_endpoint 
            ON api_incidents(endpoint)
        ''')
        
        conn.commit()
        conn.close()
        logger.info("База данных мониторинга API инициализирована")
    
    def check_api_health(self, api_client, endpoint: str = "products") -> APIHealthCheck:
        """
        Проверяет здоровье API
        
        Args:
            api_client: Клиент API
            endpoint: Эндпоинт для проверки
            
        Returns:
            APIHealthCheck с результатами проверки
        """
        start_time = time.time()
        status = APIStatus.UNKNOWN
        status_code = None
        error_message = None
        retry_count = 0
        
        try:
            # Выполняем тестовый запрос в зависимости от эндпоинта
            if endpoint == "products":
                result = api_client.get_products()
            elif endpoint == "stocks":
                result = api_client.get_stocks_data()
            elif endpoint == "sales":
                result = api_client.get_sales_data(days=1)
            elif endpoint == "analytics":
                result = api_client.get_analytics_data(days=1)
            else:
                raise ValueError(f"Неизвестный эндпоинт: {endpoint}")
            
            response_time = (time.time() - start_time) * 1000  # в миллисекундах
            
            # Определяем статус на основе времени ответа
            if response_time <= self.healthy_threshold:
                status = APIStatus.HEALTHY
            elif response_time <= self.degraded_threshold:
                status = APIStatus.DEGRADED
            else:
                status = APIStatus.DEGRADED
            
            status_code = 200 if result is not None else None
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            status = APIStatus.DOWN
            error_message = str(e)
            retry_count = 1
        
        # Создаем результат проверки
        health_check = APIHealthCheck(
            timestamp=datetime.now(),
            endpoint=endpoint,
            status=status,
            response_time=response_time,
            status_code=status_code,
            error_message=error_message,
            retry_count=retry_count
        )
        
        # Сохраняем результат
        self._save_health_check(health_check)
        
        return health_check
    
    def _save_health_check(self, health_check: APIHealthCheck):
        """Сохраняет результат проверки в БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO api_health_checks 
                (timestamp, endpoint, status, response_time, status_code, error_message, retry_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                health_check.timestamp,
                health_check.endpoint,
                health_check.status.value,
                health_check.response_time,
                health_check.status_code,
                health_check.error_message,
                health_check.retry_count
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении результата проверки: {e}")
    
    def get_health_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        Получает статистику здоровья API за последние N часов
        
        Args:
            hours: Количество часов для анализа
            
        Returns:
            Словарь со статистикой
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Время начала периода
            start_time = datetime.now() - timedelta(hours=hours)
            
            # Общая статистика
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_checks,
                    COUNT(CASE WHEN status = 'healthy' THEN 1 END) as healthy_count,
                    COUNT(CASE WHEN status = 'degraded' THEN 1 END) as degraded_count,
                    COUNT(CASE WHEN status = 'down' THEN 1 END) as down_count,
                    AVG(response_time) as avg_response_time,
                    MAX(response_time) as max_response_time,
                    MIN(response_time) as min_response_time
                FROM api_health_checks 
                WHERE timestamp >= ?
            ''', (start_time,))
            
            row = cursor.fetchone()
            if row:
                total_checks, healthy_count, degraded_count, down_count, avg_response_time, max_response_time, min_response_time = row
                
                # Рассчитываем процент uptime
                uptime_percentage = (healthy_count / total_checks * 100) if total_checks > 0 else 0
                
                # Статистика по эндпоинтам
                cursor.execute('''
                    SELECT 
                        endpoint,
                        COUNT(*) as checks,
                        COUNT(CASE WHEN status = 'healthy' THEN 1 END) as healthy,
                        AVG(response_time) as avg_time
                    FROM api_health_checks 
                    WHERE timestamp >= ?
                    GROUP BY endpoint
                ''', (start_time,))
                
                endpoint_stats = {}
                for row in cursor.fetchall():
                    endpoint, checks, healthy, avg_time = row
                    endpoint_stats[endpoint] = {
                        'checks': checks,
                        'healthy': healthy,
                        'uptime_percentage': (healthy / checks * 100) if checks > 0 else 0,
                        'avg_response_time': avg_time or 0
                    }
                
                conn.close()
                
                return {
                    'period_hours': hours,
                    'total_checks': total_checks,
                    'healthy_count': healthy_count,
                    'degraded_count': degraded_count,
                    'down_count': down_count,
                    'uptime_percentage': uptime_percentage,
                    'avg_response_time': avg_response_time or 0,
                    'max_response_time': max_response_time or 0,
                    'min_response_time': min_response_time or 0,
                    'endpoint_stats': endpoint_stats
                }
            
            conn.close()
            return {}
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики здоровья: {e}")
            return {}
    
    def get_recent_incidents(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Получает недавние инциденты
        
        Args:
            hours: Количество часов для поиска
            
        Returns:
            Список инцидентов
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            start_time = datetime.now() - timedelta(hours=hours)
            
            cursor.execute('''
                SELECT 
                    endpoint,
                    status,
                    COUNT(*) as duration_minutes,
                    MIN(timestamp) as start_time,
                    MAX(timestamp) as end_time,
                    AVG(response_time) as avg_response_time
                FROM api_health_checks 
                WHERE timestamp >= ? AND status IN ('degraded', 'down')
                GROUP BY endpoint, status
                ORDER BY start_time DESC
            ''', (start_time,))
            
            incidents = []
            for row in cursor.fetchall():
                endpoint, status, duration_minutes, start_time, end_time, avg_response_time = row
                incidents.append({
                    'endpoint': endpoint,
                    'status': status,
                    'duration_minutes': duration_minutes,
                    'start_time': start_time,
                    'end_time': end_time,
                    'avg_response_time': avg_response_time or 0
                })
            
            conn.close()
            return incidents
            
        except Exception as e:
            logger.error(f"Ошибка при получении инцидентов: {e}")
            return []
    
    def generate_health_report(self, hours: int = 24) -> str:
        """
        Генерирует отчет о здоровье API
        
        Args:
            hours: Количество часов для анализа
            
        Returns:
            Текстовый отчет
        """
        stats = self.get_health_stats(hours)
        incidents = self.get_recent_incidents(hours)
        
        if not stats:
            return "Нет данных для анализа"
        
        report = f"📊 *Отчет о здоровье API за {hours}ч*\n\n"
        
        # Общая статистика
        uptime = stats['uptime_percentage']
        avg_time = stats['avg_response_time']
        total_checks = stats['total_checks']
        
        # Эмодзи для статуса
        if uptime >= 99:
            status_emoji = "🟢"
        elif uptime >= 95:
            status_emoji = "🟡"
        else:
            status_emoji = "🔴"
        
        report += f"{status_emoji} *Общий статус:* {uptime:.1f}% uptime\n"
        report += f"⏱️ *Среднее время ответа:* {avg_time:.0f}мс\n"
        report += f"📈 *Всего проверок:* {total_checks}\n\n"
        
        # Статистика по эндпоинтам
        report += "*Статистика по эндпоинтам:*\n"
        for endpoint, endpoint_stats in stats.get('endpoint_stats', {}).items():
            endpoint_uptime = endpoint_stats['uptime_percentage']
            endpoint_avg_time = endpoint_stats['avg_response_time']
            
            if endpoint_uptime >= 99:
                emoji = "🟢"
            elif endpoint_uptime >= 95:
                emoji = "🟡"
            else:
                emoji = "🔴"
            
            report += f"{emoji} {endpoint}: {endpoint_uptime:.1f}% ({endpoint_avg_time:.0f}мс)\n"
        
        # Недавние инциденты
        if incidents:
            report += f"\n⚠️ *Недавние инциденты:*\n"
            for incident in incidents[:3]:  # Показываем только 3 последних
                duration = incident['duration_minutes']
                endpoint = incident['endpoint']
                status = incident['status']
                
                if status == 'down':
                    emoji = "🔴"
                else:
                    emoji = "🟡"
                
                report += f"{emoji} {endpoint} ({status}) - {duration}мин\n"
        
        return report
    
    def cleanup_old_data(self, days: int = 30):
        """
        Очищает старые данные мониторинга
        
        Args:
            days: Количество дней для хранения данных
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Удаляем старые записи о проверках здоровья
            cursor.execute('DELETE FROM api_health_checks WHERE timestamp < ?', (cutoff_date,))
            deleted_checks = cursor.rowcount
            
            # Удаляем старые инциденты
            cursor.execute('DELETE FROM api_incidents WHERE start_time < ?', (cutoff_date,))
            deleted_incidents = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"Очищено {deleted_checks} записей о проверках и {deleted_incidents} инцидентов старше {days} дней")
            
        except Exception as e:
            logger.error(f"Ошибка при очистке старых данных: {e}")

class APIMonitoringService:
    """Сервис мониторинга API с периодическими проверками"""
    
    def __init__(self, api_client, monitor: APIMonitor, telegram_notifier=None):
        self.api_client = api_client
        self.monitor = monitor
        self.telegram_notifier = telegram_notifier
        self.is_running = False
        self.check_interval = 300  # 5 минут
    
    async def start_monitoring(self):
        """Запускает мониторинг API"""
        self.is_running = True
        logger.info("Запуск мониторинга API")
        
        if self.telegram_notifier:
            await self.telegram_notifier.send_message("🔍 Мониторинг API запущен")
        
        while self.is_running:
            try:
                # Проверяем все эндпоинты
                endpoints = ["products", "stocks", "sales", "analytics"]
                
                for endpoint in endpoints:
                    health_check = self.monitor.check_api_health(self.api_client, endpoint)
                    
                    # Логируем результат
                    logger.info(f"API {endpoint}: {health_check.status.value} ({health_check.response_time:.0f}мс)")
                    
                    # Отправляем уведомление при критических проблемах
                    if health_check.status == APIStatus.DOWN and self.telegram_notifier:
                        message = f"🚨 *Критическая ошибка API*\n\n"
                        message += f"Эндпоинт: {endpoint}\n"
                        message += f"Ошибка: {health_check.error_message}\n"
                        message += f"Время: {health_check.timestamp.strftime('%H:%M:%S')}"
                        
                        await self.telegram_notifier.send_message(message)
                
                # Ждем до следующей проверки
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Ошибка в мониторинге API: {e}")
                await asyncio.sleep(60)  # Ждем минуту при ошибке
    
    def stop_monitoring(self):
        """Останавливает мониторинг API"""
        self.is_running = False
        logger.info("Мониторинг API остановлен")
    
    async def send_health_report(self, hours: int = 24):
        """Отправляет отчет о здоровье API"""
        if not self.telegram_notifier:
            return
        
        report = self.monitor.generate_health_report(hours)
        await self.telegram_notifier.send_message(report) 