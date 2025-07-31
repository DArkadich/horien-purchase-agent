"""
Модуль для расчета оборачиваемости и потребности в закупках
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
import json
import csv
from pathlib import Path
from config import (
    DAYS_FORECAST_SHORT, DAYS_FORECAST_LONG, SALES_HISTORY_DAYS,
    DAYS_TO_ANALYZE, get_moq_for_sku, logger
)

# Импортируем ML интеграцию
try:
    from ml_integration import MLForecastIntegration
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("ML интеграция недоступна")

class DataValidator:
    """Класс для валидации входных данных"""
    
    @staticmethod
    def validate_sales_data(sales_data: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Валидирует данные о продажах
        Возвращает (is_valid, error_messages)
        """
        errors = []
        
        if not sales_data:
            errors.append("Данные о продажах пусты")
            return False, errors
        
        required_fields = ['sku', 'date', 'quantity']
        for i, record in enumerate(sales_data):
            # Проверяем наличие обязательных полей
            for field in required_fields:
                if field not in record:
                    errors.append(f"Запись {i}: отсутствует поле '{field}'")
            
            # Проверяем типы данных
            if 'sku' in record and not isinstance(record['sku'], str):
                errors.append(f"Запись {i}: SKU должен быть строкой")
            
            if 'quantity' in record:
                try:
                    quantity = float(record['quantity'])
                    if quantity < 0:
                        errors.append(f"Запись {i}: количество не может быть отрицательным")
                except (ValueError, TypeError):
                    errors.append(f"Запись {i}: некорректное количество")
            
            if 'date' in record:
                try:
                    pd.to_datetime(record['date'])
                except:
                    errors.append(f"Запись {i}: некорректная дата")
            
            # Проверяем выбросы в количестве
            if 'quantity' in record:
                try:
                    quantity = float(record['quantity'])
                    if quantity > 1000:  # Подозрительно большое количество
                        errors.append(f"Запись {i}: подозрительно большое количество ({quantity})")
                except:
                    pass
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_stocks_data(stocks_data: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Валидирует данные об остатках
        """
        errors = []
        
        if not stocks_data:
            errors.append("Данные об остатках пусты")
            return False, errors
        
        required_fields = ['sku', 'stock', 'reserved']
        for i, record in enumerate(stocks_data):
            # Проверяем наличие обязательных полей
            for field in required_fields:
                if field not in record:
                    errors.append(f"Запись {i}: отсутствует поле '{field}'")
            
            # Проверяем типы данных
            if 'sku' in record and not isinstance(record['sku'], str):
                errors.append(f"Запись {i}: SKU должен быть строкой")
            
            for field in ['stock', 'reserved']:
                if field in record:
                    try:
                        value = float(record[field])
                        if value < 0:
                            errors.append(f"Запись {i}: {field} не может быть отрицательным")
                    except (ValueError, TypeError):
                        errors.append(f"Запись {i}: некорректное значение {field}")
            
            # Проверяем логику: зарезервировано не может быть больше общего остатка
            if 'stock' in record and 'reserved' in record:
                try:
                    stock = float(record['stock'])
                    reserved = float(record['reserved'])
                    if reserved > stock:
                        errors.append(f"Запись {i}: зарезервировано ({reserved}) больше общего остатка ({stock})")
                except:
                    pass
        
        return len(errors) == 0, errors
    
    @staticmethod
    def clean_sales_data(sales_df: pd.DataFrame) -> pd.DataFrame:
        """
        Очищает данные о продажах от выбросов и некорректных значений
        """
        if sales_df.empty:
            return sales_df
        
        original_count = len(sales_df)
        
        # Удаляем записи с отрицательными количествами
        sales_df = sales_df[sales_df['quantity'] >= 0]
        
        # Удаляем записи с некорректными датами
        sales_df = sales_df.dropna(subset=['date'])
        
        # Удаляем записи с пустыми SKU
        sales_df = sales_df[sales_df['sku'].notna() & (sales_df['sku'] != '')]
        
        # Удаляем выбросы (количество > 3 стандартных отклонения от среднего)
        if len(sales_df) > 10:
            q1 = sales_df['quantity'].quantile(0.25)
            q3 = sales_df['quantity'].quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            sales_df = sales_df[
                (sales_df['quantity'] >= lower_bound) & 
                (sales_df['quantity'] <= upper_bound)
            ]
        
        cleaned_count = len(sales_df)
        if original_count != cleaned_count:
            logger.warning(f"Очищено {original_count - cleaned_count} некорректных записей о продажах")
        
        return sales_df
    
    @staticmethod
    def clean_stocks_data(stocks_df: pd.DataFrame) -> pd.DataFrame:
        """
        Очищает данные об остатках
        """
        if stocks_df.empty:
            return stocks_df
        
        original_count = len(stocks_df)
        
        # Удаляем записи с отрицательными значениями
        stocks_df = stocks_df[
            (stocks_df['stock'] >= 0) & 
            (stocks_df['reserved'] >= 0)
        ]
        
        # Исправляем логические ошибки: зарезервировано не может быть больше общего остатка
        stocks_df['reserved'] = stocks_df['reserved'].clip(upper=stocks_df['stock'])
        
        # Удаляем записи с пустыми SKU
        stocks_df = stocks_df[stocks_df['sku'].notna() & (stocks_df['sku'] != '')]
        
        cleaned_count = len(stocks_df)
        if original_count != cleaned_count:
            logger.warning(f"Очищено {original_count - cleaned_count} некорректных записей об остатках")
        
        return stocks_df

class PurchaseForecast:
    """Класс для расчета прогнозов закупок"""
    
    def __init__(self):
        self.days_forecast_short = DAYS_FORECAST_SHORT
        self.days_forecast_long = DAYS_FORECAST_LONG
        self.sales_history_days = SALES_HISTORY_DAYS
    
    def prepare_sales_data(self, sales_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Подготавливает данные о продажах для анализа с валидацией
        """
        logger.info("Подготовка данных о продажах...")
        
        # Валидируем входные данные
        is_valid, errors = DataValidator.validate_sales_data(sales_data)
        if not is_valid:
            logger.error("Ошибки валидации данных о продажах:")
            for error in errors[:10]:  # Показываем первые 10 ошибок
                logger.error(f"  - {error}")
            if len(errors) > 10:
                logger.error(f"  ... и еще {len(errors) - 10} ошибок")
            return pd.DataFrame()
        
        # Преобразуем в DataFrame
        df = pd.DataFrame(sales_data)
        
        if df.empty:
            logger.warning("Нет данных о продажах")
            return pd.DataFrame()
        
        # Очищаем данные от выбросов и некорректных значений
        df = DataValidator.clean_sales_data(df)
        
        if df.empty:
            logger.warning("После очистки данных о продажах не осталось записей")
            return pd.DataFrame()
        
        # Обрабатываем даты
        df['date'] = pd.to_datetime(df['date'])
        
        # Проверяем диапазон дат
        min_date = df['date'].min()
        max_date = df['date'].max()
        date_range = (max_date - min_date).days
        
        logger.info(f"Диапазон дат: {min_date.date()} - {max_date.date()} ({date_range} дней)")
        
        if date_range < DAYS_TO_ANALYZE:
            logger.warning(f"Мало исторических данных для анализа (менее {DAYS_TO_ANALYZE} дней)")
        
        # Группируем по SKU и дате
        sales_by_sku = df.groupby(['sku', 'date']).agg({
            'quantity': 'sum',
            'revenue': 'sum'
        }).reset_index()
        
        logger.info(f"Подготовлено {len(sales_by_sku)} записей о продажах для {sales_by_sku['sku'].nunique()} SKU")
        return sales_by_sku
    
    def prepare_stocks_data(self, stocks_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Подготавливает данные об остатках с валидацией
        """
        logger.info("Подготовка данных об остатках...")
        
        # Валидируем входные данные
        is_valid, errors = DataValidator.validate_stocks_data(stocks_data)
        if not is_valid:
            logger.error("Ошибки валидации данных об остатках:")
            for error in errors[:10]:  # Показываем первые 10 ошибок
                logger.error(f"  - {error}")
            if len(errors) > 10:
                logger.error(f"  ... и еще {len(errors) - 10} ошибок")
            return pd.DataFrame()
        
        # Преобразуем в DataFrame
        df = pd.DataFrame(stocks_data)
        
        if df.empty:
            logger.warning("Нет данных об остатках")
            return pd.DataFrame()
        
        # Очищаем данные от некорректных значений
        df = DataValidator.clean_stocks_data(df)
        
        if df.empty:
            logger.warning("После очистки данных об остатках не осталось записей")
            return pd.DataFrame()
        
        # Группируем по SKU
        stocks_by_sku = df.groupby('sku').agg({
            'stock': 'sum',
            'reserved': 'sum'
        }).reset_index()
        
        # Рассчитываем доступный остаток
        stocks_by_sku['available_stock'] = stocks_by_sku['stock'] - stocks_by_sku['reserved']
        
        # Проверяем на отрицательные доступные остатки
        negative_stocks = stocks_by_sku[stocks_by_sku['available_stock'] < 0]
        if not negative_stocks.empty:
            logger.warning(f"Найдено {len(negative_stocks)} SKU с отрицательными доступными остатками")
            for _, row in negative_stocks.head(3).iterrows():
                logger.warning(f"  SKU {row['sku']}: stock={row['stock']}, reserved={row['reserved']}, available={row['available_stock']}")
        
        # Исправляем отрицательные доступные остатки
        stocks_by_sku['available_stock'] = stocks_by_sku['available_stock'].clip(lower=0)
        
        logger.info(f"Подготовлено {len(stocks_by_sku)} записей об остатках для {stocks_by_sku['sku'].nunique()} SKU")
        return stocks_by_sku
    
    def calculate_daily_sales(self, sales_df: pd.DataFrame, stocks_df: pd.DataFrame = None) -> pd.DataFrame:
        """
        Рассчитывает среднюю дневную продажу для каждого SKU, исключая дни OOS и поставок
        """
        logger.info("Расчет средней дневной продажи (исключая дни OOS и поставок)...")
        
        if sales_df.empty:
            return pd.DataFrame()
        
        # Если есть данные об остатках, используем их для точного определения OOS
        if stocks_df is not None and not stocks_df.empty:
            # Объединяем продажи с остатками по SKU
            sales_with_stocks = sales_df.merge(stocks_df[['sku', 'available_stock']], on='sku', how='left')
            
            # Определяем дни OOS: когда остаток = 0 или отсутствует
            sales_with_stocks['is_oos'] = (sales_with_stocks['available_stock'].isna() | 
                                         (sales_with_stocks['available_stock'] == 0))
            
            # Фильтруем только дни когда товар был в наличии (исключаем дни OOS)
            # Включаем все дни с наличием товара, даже если продаж не было
            days_with_stock = sales_with_stocks[~sales_with_stocks['is_oos']].copy()
            
            logger.info(f"Используем данные об остатках для определения OOS дней")
        else:
            # Если нет данных об остатках, используем старую логику
            days_with_stock = sales_df.copy()
            logger.info(f"Данные об остатках недоступны, используем все дни")
        
        if days_with_stock.empty:
            logger.warning("Нет данных о днях с наличием товара")
            return pd.DataFrame()
        
        # Фильтруем дни поставок (когда продажи = 0 и это может быть поставка)
        # Для этого нужно анализировать изменения остатков, но пока используем простую логику
        # Дни с нулевыми продажами, но с наличием товара - это нормальные дни без продаж
        # Дни поставок будут отфильтрованы на уровне stock_tracker
        
        # Группируем по SKU и рассчитываем среднюю дневную продажу за дни с наличием товара
        daily_sales = days_with_stock.groupby('sku').agg({
            'quantity': 'sum',
            'date': 'nunique'
        }).reset_index()
        
        daily_sales['avg_daily_sales'] = daily_sales['quantity'] / daily_sales['date']
        daily_sales['total_sales_days'] = daily_sales['date']
        
        # Убираем колонку с количеством уникальных дат
        daily_sales = daily_sales.drop('date', axis=1)
        
        logger.info(f"Рассчитана средняя дневная продажа для {len(daily_sales)} SKU (за дни с наличием товара)")
        
        # Логируем примеры для отладки
        for _, row in daily_sales.head(3).iterrows():
            logger.info(f"SKU {row['sku']}: {row['avg_daily_sales']:.2f} шт/день за {row['total_sales_days']} дней с наличием товара")
        
        return daily_sales
    
    def identify_oos_days(self, sales_df: pd.DataFrame, stocks_df: pd.DataFrame) -> pd.DataFrame:
        """
        Идентифицирует дни, когда товары были в OOS (out of stock) для информационных целей
        """
        logger.info("Идентификация дней OOS для анализа...")
        
        if sales_df.empty or stocks_df.empty:
            return pd.DataFrame()
        
        # Создаем полный диапазон дат для каждого SKU
        date_range = pd.date_range(
            start=sales_df['date'].min(),
            end=sales_df['date'].max(),
            freq='D'
        )
        
        # Создаем все комбинации SKU и дат
        all_combinations = []
        for sku in sales_df['sku'].unique():
            for date in date_range:
                all_combinations.append({'sku': sku, 'date': date})
        
        combinations_df = pd.DataFrame(all_combinations)
        
        # Объединяем с реальными продажами
        merged_df = combinations_df.merge(
            sales_df, on=['sku', 'date'], how='left'
        ).fillna(0)
        
        # Определяем дни OOS (когда продажи = 0)
        merged_df['is_oos'] = merged_df['quantity'] == 0
        
        # Подсчитываем статистику OOS для каждого SKU
        oos_stats = merged_df.groupby('sku').agg({
            'is_oos': 'sum',
            'date': 'count'
        }).reset_index()
        
        oos_stats['oos_percentage'] = (oos_stats['is_oos'] / oos_stats['date'] * 100).round(1)
        
        # Логируем статистику OOS
        for _, row in oos_stats.head(5).iterrows():
            logger.info(f"SKU {row['sku']}: {row['oos_percentage']}% дней OOS ({row['is_oos']} из {row['date']} дней)")
        
        logger.info(f"Идентифицировано {merged_df['is_oos'].sum()} дней OOS из {len(merged_df)} общих дней")
        return merged_df
    
    def calculate_forecast(self, sales_df: pd.DataFrame, stocks_df: pd.DataFrame) -> pd.DataFrame:
        """
        Рассчитывает прогноз закупок для каждого SKU с валидацией
        """
        logger.info("Расчет прогноза закупок...")
        
        # Валидируем входные данные
        if stocks_df.empty:
            logger.error("Нет данных об остатках для расчета прогноза")
            return pd.DataFrame()
        
        # Проверяем качество данных об остатках
        total_stocks = stocks_df['available_stock'].sum()
        if total_stocks == 0:
            logger.warning("Все товары имеют нулевые остатки")
        
        # Проверяем покрытие SKU
        if not sales_df.empty:
            sales_skus = set(sales_df['sku'].unique())
            stocks_skus = set(stocks_df['sku'].unique())
            common_skus = sales_skus.intersection(stocks_skus)
            
            logger.info(f"SKU с данными о продажах: {len(sales_skus)}")
            logger.info(f"SKU с данными об остатках: {len(stocks_skus)}")
            logger.info(f"SKU с полными данными: {len(common_skus)}")
            
            if len(common_skus) == 0:
                logger.warning("Нет пересечения между SKU в продажах и остатках")
        
        # Если есть данные о продажах, используем их для расчета средней продажи
        if not sales_df.empty:
            # Рассчитываем среднюю дневную продажу из данных о продажах
            daily_sales = self.calculate_daily_sales(sales_df, stocks_df)
            
            if not daily_sales.empty:
                # Объединяем с остатками
                forecast_df = daily_sales.merge(stocks_df, on='sku', how='left')
                logger.info("Используем данные о продажах для расчета средней продажи")
                
                # Проверяем качество прогноза
                forecast_df['forecast_quality'] = 'GOOD'
                
                # SKU с малым количеством дней продаж
                low_data_skus = forecast_df[forecast_df['total_sales_days'] < DAYS_TO_ANALYZE]
                if not low_data_skus.empty:
                    forecast_df.loc[low_data_skus.index, 'forecast_quality'] = 'LOW_DATA'
                    logger.warning(f"{len(low_data_skus)} SKU имеют мало данных о продажах (< {DAYS_TO_ANALYZE} дней)")
                
                # SKU с нулевой средней продажей
                zero_sales_skus = forecast_df[forecast_df['avg_daily_sales'] == 0]
                if not zero_sales_skus.empty:
                    forecast_df.loc[zero_sales_skus.index, 'forecast_quality'] = 'NO_SALES'
                    logger.warning(f"{len(zero_sales_skus)} SKU имеют нулевую среднюю продажу")
                
            else:
                # Если нет данных о продажах, используем базовую логику
                forecast_df = stocks_df.copy()
                forecast_df['avg_daily_sales'] = 1.0  # 1 шт в день по умолчанию
                forecast_df['total_sales_days'] = 0
                forecast_df['forecast_quality'] = 'NO_SALES_DATA'
                logger.info("Нет данных о продажах, используем базовую продажу 1 шт/день")
        else:
            # Если нет данных о продажах, используем базовую логику
            forecast_df = stocks_df.copy()
            forecast_df['avg_daily_sales'] = 1.0  # 1 шт в день по умолчанию
            forecast_df['total_sales_days'] = 0
            forecast_df['forecast_quality'] = 'NO_SALES_DATA'
            logger.info("Нет данных о продажах, используем базовую продажу 1 шт/день")
        
        # Рассчитываем, на сколько дней хватит текущего запаса
        forecast_df['days_until_stockout'] = np.where(
            forecast_df['avg_daily_sales'] > 0,
            forecast_df['available_stock'] / forecast_df['avg_daily_sales'],
            float('inf')
        )
        
        # Определяем необходимость закупки
        forecast_df['needs_purchase_short'] = forecast_df['days_until_stockout'] < self.days_forecast_short
        forecast_df['needs_purchase_long'] = forecast_df['days_until_stockout'] < self.days_forecast_long
        
        # Рассчитываем рекомендуемое количество для закупки
        forecast_df['recommended_quantity'] = np.where(
            forecast_df['needs_purchase_short'],
            np.maximum(
                (self.days_forecast_long - forecast_df['days_until_stockout']) * forecast_df['avg_daily_sales'],
                forecast_df['avg_daily_sales'] * self.days_forecast_short
            ),
            0
        )
        
        # Применяем минимальные партии
        forecast_df['moq'] = forecast_df['sku'].apply(get_moq_for_sku)
        forecast_df['final_order_quantity'] = np.where(
            forecast_df['recommended_quantity'] > 0,
            np.maximum(forecast_df['recommended_quantity'], forecast_df['moq']),
            0
        )
        
        # Округляем до целых чисел
        forecast_df['final_order_quantity'] = forecast_df['final_order_quantity'].round().astype(int)
        
        # Логируем статистику качества прогноза
        quality_stats = forecast_df['forecast_quality'].value_counts()
        logger.info("Качество прогноза по SKU:")
        for quality, count in quality_stats.items():
            logger.info(f"  {quality}: {count} SKU")
        
        logger.info(f"Рассчитан прогноз для {len(forecast_df)} SKU")
        return forecast_df
    
    def generate_purchase_report(self, forecast_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Генерирует отчет о закупках с учетом качества прогноза
        """
        logger.info("Генерация отчета о закупках...")
        
        if forecast_df.empty:
            return []
        
        # Фильтруем SKU, которые требуют закупки
        purchase_items = forecast_df[forecast_df['needs_purchase_short']].copy()
        
        if purchase_items.empty:
            logger.info("Нет товаров, требующих закупки")
            return []
        
        # Сортируем по приоритету (по убыванию срочности)
        purchase_items = purchase_items.sort_values('days_until_stockout', ascending=True)
        
        # Формируем отчет
        report = []
        for _, row in purchase_items.iterrows():
            # Определяем уровень уверенности в прогнозе
            confidence = self._get_forecast_confidence(row['forecast_quality'], row['total_sales_days'])
            
            report_item = {
                'sku': row['sku'],
                'avg_daily_sales': round(row['avg_daily_sales'], 2),
                'current_stock': int(row['available_stock']),
                'days_until_stockout': round(row['days_until_stockout'], 1),
                'recommended_quantity': int(row['final_order_quantity']),
                'moq': int(row['moq']),
                'forecast_quality': row['forecast_quality'],
                'confidence': confidence,
                'urgency': 'HIGH' if row['days_until_stockout'] < 10 else 'MEDIUM' if row['days_until_stockout'] < 20 else 'LOW'
            }
            report.append(report_item)
        
        # Логируем статистику по качеству прогноза
        quality_stats = purchase_items['forecast_quality'].value_counts()
        logger.info("Качество прогноза для товаров, требующих закупки:")
        for quality, count in quality_stats.items():
            logger.info(f"  {quality}: {count} SKU")
        
        logger.info(f"Сгенерирован отчет для {len(report)} SKU")
        return report
    
    def _get_forecast_confidence(self, quality: str, sales_days: int) -> str:
        """
        Определяет уровень уверенности в прогнозе на основе качества данных
        """
        if quality == 'GOOD':
            if sales_days >= 30:
                return 'HIGH'
            elif sales_days >= 14:
                return 'MEDIUM'
            else:
                return 'LOW'
        elif quality == 'LOW_DATA':
            return 'LOW'
        elif quality == 'NO_SALES':
            return 'VERY_LOW'
        elif quality == 'NO_SALES_DATA':
            return 'VERY_LOW'
        else:
            return 'UNKNOWN'
    
    def generate_telegram_message(self, report: List[Dict[str, Any]]) -> str:
        """
        Генерирует сообщение для Telegram с информацией о качестве прогноза
        """
        if not report:
            return "Нет товаров, требующих закупки."
        
        message = "🛒 *Отчет о закупках*\n\n"
        
        # Группируем по уровню уверенности
        high_confidence = [item for item in report if item['confidence'] == 'HIGH']
        medium_confidence = [item for item in report if item['confidence'] == 'MEDIUM']
        low_confidence = [item for item in report if item['confidence'] in ['LOW', 'VERY_LOW']]
        
        # Показываем товары с высокой уверенностью
        if high_confidence:
            message += "🟢 *Высокая уверенность:*\n"
            for item in high_confidence[:5]:
                sku = item['sku']
                days_left = item['days_until_stockout']
                quantity = item['recommended_quantity']
                urgency_emoji = "🔴" if item['urgency'] == 'HIGH' else "🟡" if item['urgency'] == 'MEDIUM' else "🟢"
                message += f"{urgency_emoji} {sku} → {days_left} дней. Заказать {quantity} шт\n"
        
        # Показываем товары со средней уверенностью
        if medium_confidence:
            message += "\n🟡 *Средняя уверенность:*\n"
            for item in medium_confidence[:3]:
                sku = item['sku']
                days_left = item['days_until_stockout']
                quantity = item['recommended_quantity']
                urgency_emoji = "🔴" if item['urgency'] == 'HIGH' else "🟡" if item['urgency'] == 'MEDIUM' else "🟢"
                message += f"{urgency_emoji} {sku} → {days_left} дней. Заказать {quantity} шт\n"
        
        # Показываем товары с низкой уверенностью
        if low_confidence:
            message += "\n🔴 *Низкая уверенность (требует проверки):*\n"
            for item in low_confidence[:3]:
                sku = item['sku']
                days_left = item['days_until_stockout']
                quantity = item['recommended_quantity']
                quality = item['forecast_quality']
                urgency_emoji = "🔴" if item['urgency'] == 'HIGH' else "🟡" if item['urgency'] == 'MEDIUM' else "🟢"
                message += f"{urgency_emoji} {sku} → {days_left} дней. Заказать {quantity} шт ({quality})\n"
        
        # Статистика
        total_items = len(report)
        high_count = len(high_confidence)
        medium_count = len(medium_confidence)
        low_count = len(low_confidence)
        
        message += f"\n📊 *Статистика:*\n"
        message += f"Всего позиций: {total_items}\n"
        message += f"Высокая уверенность: {high_count}\n"
        message += f"Средняя уверенность: {medium_count}\n"
        message += f"Низкая уверенность: {low_count}\n"
        
        if len(report) > 10:
            message += f"\n... и еще {len(report) - 10} позиций"
        
        return message
    
    def analyze_seasonality(self, sales_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Анализирует сезонность продаж для улучшения прогнозирования
        """
        logger.info("Анализ сезонности продаж...")
        
        if sales_df.empty:
            return {}
        
        # Добавляем день недели и месяц
        sales_df['day_of_week'] = sales_df['date'].dt.dayofweek
        sales_df['month'] = sales_df['date'].dt.month
        sales_df['week'] = sales_df['date'].dt.isocalendar().week
        
        # Анализ по дням недели
        daily_pattern = sales_df.groupby('day_of_week')['quantity'].agg(['mean', 'std', 'count']).reset_index()
        daily_pattern['day_name'] = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        
        # Анализ по месяцам
        monthly_pattern = sales_df.groupby('month')['quantity'].agg(['mean', 'std', 'count']).reset_index()
        
        # Создаем словарь для названий месяцев
        month_names = {
            1: 'Янв', 2: 'Фев', 3: 'Мар', 4: 'Апр', 5: 'Май', 6: 'Июн',
            7: 'Июл', 8: 'Авг', 9: 'Сен', 10: 'Окт', 11: 'Ноя', 12: 'Дек'
        }
        
        # Добавляем названия месяцев только для существующих месяцев
        monthly_pattern['month_name'] = monthly_pattern['month'].map(month_names)
        
        # Находим пиковые дни и месяцы
        peak_day = daily_pattern.loc[daily_pattern['mean'].idxmax()]
        peak_month = monthly_pattern.loc[monthly_pattern['mean'].idxmax()]
        
        seasonality_data = {
            'daily_pattern': daily_pattern.to_dict('records'),
            'monthly_pattern': monthly_pattern.to_dict('records'),
            'peak_day': {
                'day': peak_day['day_name'],
                'avg_sales': round(peak_day['mean'], 2)
            },
            'peak_month': {
                'month': peak_month['month_name'],
                'avg_sales': round(peak_month['mean'], 2)
            }
        }
        
        logger.info(f"Пиковый день недели: {peak_day['day_name']} ({peak_day['mean']:.2f} шт)")
        logger.info(f"Пиковый месяц: {peak_month['month_name']} ({peak_month['mean']:.2f} шт)")
        
        return seasonality_data
    
    def export_report_to_csv(self, report: List[Dict[str, Any]], filename: str = None) -> str:
        """
        Экспортирует отчет в CSV файл
        """
        if not report:
            logger.warning("Нет данных для экспорта")
            return ""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"purchase_forecast_{timestamp}.csv"
        
        # Создаем директорию для отчетов если её нет
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        filepath = reports_dir / filename
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'sku', 'avg_daily_sales', 'current_stock', 'days_until_stockout',
                    'recommended_quantity', 'moq', 'forecast_quality', 'confidence', 'urgency'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(report)
            
            logger.info(f"Отчет экспортирован в {filepath}")
            return str(filepath)
        
        except Exception as e:
            logger.error(f"Ошибка при экспорте отчета: {e}")
            return ""
    
    def export_report_to_json(self, report: List[Dict[str, Any]], filename: str = None) -> str:
        """
        Экспортирует отчет в JSON файл с дополнительной метаинформацией
        """
        if not report:
            logger.warning("Нет данных для экспорта")
            return ""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"purchase_forecast_{timestamp}.json"
        
        # Создаем директорию для отчетов если её нет
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        filepath = reports_dir / filename
        
        # Добавляем метаинформацию
        export_data = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_items': len(report),
                'forecast_period_short': self.days_forecast_short,
                'forecast_period_long': self.days_forecast_long,
                'version': '1.0'
            },
            'summary': {
                'high_confidence': len([item for item in report if item['confidence'] == 'HIGH']),
                'medium_confidence': len([item for item in report if item['confidence'] == 'MEDIUM']),
                'low_confidence': len([item for item in report if item['confidence'] in ['LOW', 'VERY_LOW']]),
                'high_urgency': len([item for item in report if item['urgency'] == 'HIGH']),
                'medium_urgency': len([item for item in report if item['urgency'] == 'MEDIUM']),
                'low_urgency': len([item for item in report if item['urgency'] == 'LOW'])
            },
            'items': report
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump(export_data, jsonfile, ensure_ascii=False, indent=2)
            
            logger.info(f"Отчет экспортирован в {filepath}")
            return str(filepath)
        
        except Exception as e:
            logger.error(f"Ошибка при экспорте отчета: {e}")
            return ""
    
    def get_forecast_analytics(self, forecast_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Генерирует аналитику по прогнозу
        """
        if forecast_df.empty:
            return {}
        
        analytics = {
            'total_skus': len(forecast_df),
            'skus_needing_purchase': len(forecast_df[forecast_df['needs_purchase_short']]),
            'skus_critical': len(forecast_df[forecast_df['days_until_stockout'] < DAYS_TO_ANALYZE]),
            'skus_urgent': len(forecast_df[forecast_df['days_until_stockout'] < 14]),
            'total_recommended_quantity': int(forecast_df['final_order_quantity'].sum()),
            'avg_days_until_stockout': round(forecast_df['days_until_stockout'].mean(), 1),
            'quality_distribution': forecast_df['forecast_quality'].value_counts().to_dict(),
            'stock_levels': {
                'low_stock': len(forecast_df[forecast_df['available_stock'] < 10]),
                'medium_stock': len(forecast_df[(forecast_df['available_stock'] >= 10) & (forecast_df['available_stock'] < 50)]),
                'high_stock': len(forecast_df[forecast_df['available_stock'] >= 50])
            }
        }
        
        # Анализ по качеству прогноза
        quality_analytics = {}
        for quality in forecast_df['forecast_quality'].unique():
            quality_df = forecast_df[forecast_df['forecast_quality'] == quality]
            quality_analytics[quality] = {
                'count': len(quality_df),
                'avg_days_until_stockout': round(quality_df['days_until_stockout'].mean(), 1),
                'total_recommended_quantity': int(quality_df['final_order_quantity'].sum())
            }
        
        analytics['quality_analytics'] = quality_analytics
        
        logger.info(f"Аналитика прогноза: {analytics['skus_needing_purchase']} SKU требуют закупки")
        logger.info(f"Критических позиций: {analytics['skus_critical']}")
        logger.info(f"Общее рекомендуемое количество: {analytics['total_recommended_quantity']} шт")
        
        return analytics
    
    def validate_forecast_data(self, forecast_df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Валидирует результаты прогноза
        """
        errors = []
        
        if forecast_df.empty:
            errors.append("Результат прогноза пуст")
            return False, errors
        
        # Проверяем обязательные колонки
        required_columns = [
            'sku', 'avg_daily_sales', 'available_stock', 'days_until_stockout',
            'needs_purchase_short', 'final_order_quantity'
        ]
        
        missing_columns = [col for col in required_columns if col not in forecast_df.columns]
        if missing_columns:
            errors.append(f"Отсутствуют обязательные колонки: {missing_columns}")
        
        # Проверяем логические ошибки
        if 'days_until_stockout' in forecast_df.columns:
            negative_days = forecast_df[forecast_df['days_until_stockout'] < 0]
            if not negative_days.empty:
                errors.append(f"Найдено {len(negative_days)} SKU с отрицательными днями до исчерпания")
        
        if 'final_order_quantity' in forecast_df.columns:
            negative_quantity = forecast_df[forecast_df['final_order_quantity'] < 0]
            if not negative_quantity.empty:
                errors.append(f"Найдено {len(negative_quantity)} SKU с отрицательным рекомендуемым количеством")
        
        # Проверяем выбросы
        if 'avg_daily_sales' in forecast_df.columns:
            q3 = forecast_df['avg_daily_sales'].quantile(0.75)
            iqr = forecast_df['avg_daily_sales'].quantile(0.75) - forecast_df['avg_daily_sales'].quantile(0.25)
            upper_bound = q3 + 1.5 * iqr
            outliers = forecast_df[forecast_df['avg_daily_sales'] > upper_bound]
            if not outliers.empty:
                errors.append(f"Найдено {len(outliers)} SKU с подозрительно высокой средней продажей")
        
        return len(errors) == 0, errors 
    
    def compare_with_historical_forecast(self, current_forecast: pd.DataFrame, 
                                       historical_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Сравнивает текущий прогноз с историческими данными для оценки точности
        """
        logger.info("Сравнение с историческими данными...")
        
        if current_forecast.empty or historical_data.empty:
            return {}
        
        comparison = {
            'total_skus': len(current_forecast),
            'accuracy_metrics': {},
            'trends': {}
        }
        
        # Анализируем точность прогнозов по качеству данных
        for quality in current_forecast['forecast_quality'].unique():
            quality_df = current_forecast[current_forecast['forecast_quality'] == quality]
            
            # Здесь можно добавить логику сравнения с историческими прогнозами
            # Пока возвращаем базовую статистику
            comparison['accuracy_metrics'][quality] = {
                'count': len(quality_df),
                'avg_days_until_stockout': round(quality_df['days_until_stockout'].mean(), 1),
                'avg_recommended_quantity': round(quality_df['final_order_quantity'].mean(), 1)
            }
        
        logger.info("Сравнение с историческими данными завершено")
        return comparison
    
    def generate_dashboard_data(self, forecast_df: pd.DataFrame, 
                               sales_df: pd.DataFrame = None) -> Dict[str, Any]:
        """
        Генерирует данные для дашборда
        """
        logger.info("Генерация данных для дашборда...")
        
        dashboard_data = {
            'summary': {},
            'charts': {},
            'alerts': []
        }
        
        if not forecast_df.empty:
            # Основная статистика
            dashboard_data['summary'] = {
                'total_skus': len(forecast_df),
                'skus_needing_purchase': len(forecast_df[forecast_df['needs_purchase_short']]),
                'critical_skus': len(forecast_df[forecast_df['days_until_stockout'] < DAYS_TO_ANALYZE]),
                'total_recommended_quantity': int(forecast_df['final_order_quantity'].sum()),
                'avg_days_until_stockout': round(forecast_df['days_until_stockout'].mean(), 1)
            }
            
            # Данные для графиков
            dashboard_data['charts'] = {
                'quality_distribution': forecast_df['forecast_quality'].value_counts().to_dict(),
                'urgency_distribution': {
                    'HIGH': len(forecast_df[forecast_df['days_until_stockout'] < 10]),
                    'MEDIUM': len(forecast_df[(forecast_df['days_until_stockout'] >= 10) & 
                                            (forecast_df['days_until_stockout'] < 20)]),
                    'LOW': len(forecast_df[forecast_df['days_until_stockout'] >= 20])
                },
                'stock_levels': {
                    'low': len(forecast_df[forecast_df['available_stock'] < 10]),
                    'medium': len(forecast_df[(forecast_df['available_stock'] >= 10) & 
                                            (forecast_df['available_stock'] < 50)]),
                    'high': len(forecast_df[forecast_df['available_stock'] >= 50])
                }
            }
            
            # Алерты
            critical_items = forecast_df[forecast_df['days_until_stockout'] < 3]
            if not critical_items.empty:
                dashboard_data['alerts'].append({
                    'type': 'CRITICAL',
                    'message': f"{len(critical_items)} товаров с критически низким остатком (< 3 дней)",
                    'count': len(critical_items)
                })
            
            low_confidence_items = forecast_df[forecast_df['forecast_quality'].isin(['LOW_DATA', 'NO_SALES'])]
            if not low_confidence_items.empty:
                dashboard_data['alerts'].append({
                    'type': 'WARNING',
                    'message': f"{len(low_confidence_items)} товаров с низким качеством прогноза",
                    'count': len(low_confidence_items)
                })
        
        # Анализ сезонности если есть данные о продажах
        if sales_df is not None and not sales_df.empty:
            seasonality = self.analyze_seasonality(sales_df)
            dashboard_data['seasonality'] = seasonality
        
        logger.info("Данные для дашборда сгенерированы")
        return dashboard_data
    
    def get_forecast_recommendations(self, forecast_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Генерирует рекомендации по улучшению прогнозирования
        """
        recommendations = []
        
        if forecast_df.empty:
            return recommendations
        
        # Анализируем качество данных
        low_data_skus = forecast_df[forecast_df['forecast_quality'] == 'LOW_DATA']
        if not low_data_skus.empty:
            recommendations.append({
                'type': 'DATA_QUALITY',
                'priority': 'HIGH',
                'message': f"Улучшить качество данных для {len(low_data_skus)} SKU",
                'action': 'Собрать больше исторических данных о продажах',
                'affected_skus': len(low_data_skus)
            })
        
        # Анализируем критические позиции
        critical_skus = forecast_df[forecast_df['days_until_stockout'] < DAYS_TO_ANALYZE]
        if not critical_skus.empty:
            recommendations.append({
                'type': 'URGENT_PURCHASE',
                'priority': 'CRITICAL',
                'message': f"Срочно закупить {len(critical_skus)} позиций",
                'action': 'Немедленно оформить заказы',
                'affected_skus': len(critical_skus)
            })
        
        # Анализируем выбросы в продажах
        if 'avg_daily_sales' in forecast_df.columns:
            q3 = forecast_df['avg_daily_sales'].quantile(0.75)
            iqr = forecast_df['avg_daily_sales'].quantile(0.75) - forecast_df['avg_daily_sales'].quantile(0.25)
            upper_bound = q3 + 1.5 * iqr
            outliers = forecast_df[forecast_df['avg_daily_sales'] > upper_bound]
            
            if not outliers.empty:
                recommendations.append({
                    'type': 'SALES_OUTLIERS',
                    'priority': 'MEDIUM',
                    'message': f"Проверить {len(outliers)} SKU с аномально высокой продажей",
                    'action': 'Проверить корректность данных о продажах',
                    'affected_skus': len(outliers)
                })
        
        # Анализируем товары с нулевой продажей
        zero_sales = forecast_df[forecast_df['avg_daily_sales'] == 0]
        if not zero_sales.empty:
            recommendations.append({
                'type': 'ZERO_SALES',
                'priority': 'MEDIUM',
                'message': f"Проанализировать {len(zero_sales)} SKU с нулевой продажей",
                'action': 'Проверить актуальность товаров',
                'affected_skus': len(zero_sales)
            })
        
        logger.info(f"Сгенерировано {len(recommendations)} рекомендаций")
        return recommendations
    
    def create_forecast_summary_report(self, forecast_df: pd.DataFrame, 
                                     analytics: Dict[str, Any] = None,
                                     recommendations: List[Dict[str, Any]] = None) -> str:
        """
        Создает текстовый отчет-резюме по прогнозу
        """
        if forecast_df.empty:
            return "Нет данных для создания отчета"
        
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("ОТЧЕТ ПО ПРОГНОЗУ ЗАКУПОК")
        report_lines.append("=" * 60)
        report_lines.append(f"Дата генерации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Основная статистика
        total_skus = len(forecast_df)
        skus_needing_purchase = len(forecast_df[forecast_df['needs_purchase_short']])
        critical_skus = len(forecast_df[forecast_df['days_until_stockout'] < DAYS_TO_ANALYZE])
        total_quantity = int(forecast_df['final_order_quantity'].sum())
        
        report_lines.append("ОСНОВНАЯ СТАТИСТИКА:")
        report_lines.append(f"  • Всего SKU: {total_skus}")
        report_lines.append(f"  • Требуют закупки: {skus_needing_purchase}")
        report_lines.append(f"  • Критических позиций: {critical_skus}")
        report_lines.append(f"  • Общее рекомендуемое количество: {total_quantity} шт")
        report_lines.append("")
        
        # Качество прогноза
        quality_stats = forecast_df['forecast_quality'].value_counts()
        report_lines.append("КАЧЕСТВО ПРОГНОЗА:")
        for quality, count in quality_stats.items():
            percentage = (count / total_skus) * 100
            report_lines.append(f"  • {quality}: {count} SKU ({percentage:.1f}%)")
        report_lines.append("")
        
        # Аналитика если есть
        if analytics:
            report_lines.append("ДОПОЛНИТЕЛЬНАЯ АНАЛИТИКА:")
            if 'stock_levels' in analytics:
                levels = analytics['stock_levels']
                report_lines.append(f"  • Низкий остаток (< 10): {levels.get('low', 0)} SKU")
                report_lines.append(f"  • Средний остаток (10-50): {levels.get('medium', 0)} SKU")
                report_lines.append(f"  • Высокий остаток (> 50): {levels.get('high', 0)} SKU")
            report_lines.append("")
        
        # Рекомендации если есть
        if recommendations:
            report_lines.append("РЕКОМЕНДАЦИИ:")
            for i, rec in enumerate(recommendations[:5], 1):
                priority_emoji = "🔴" if rec['priority'] == 'CRITICAL' else "🟡" if rec['priority'] == 'HIGH' else "🟢"
                report_lines.append(f"  {i}. {priority_emoji} {rec['message']}")
                report_lines.append(f"     Действие: {rec['action']}")
            report_lines.append("")
        
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)
    
    def calculate_ml_enhanced_forecast(self, sales_data: List[Dict[str, Any]], 
                                     stocks_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Рассчитывает прогноз с улучшением от ML-моделей
        """
        logger.info("Расчет ML-улучшенного прогноза...")
        
        if not ML_AVAILABLE:
            logger.warning("ML интеграция недоступна, используем базовый прогноз")
            return self.calculate_forecast(
                self.prepare_sales_data(sales_data),
                self.prepare_stocks_data(stocks_data)
            )
        
        try:
            # Создаем ML интеграцию
            ml_integration = MLForecastIntegration()
            
            # Получаем базовый прогноз
            sales_df = self.prepare_sales_data(sales_data)
            stocks_df = self.prepare_stocks_data(stocks_data)
            base_forecast = self.calculate_forecast(sales_df, stocks_df)
            
            # Улучшаем прогноз с помощью ML
            enhanced_forecast = ml_integration.enhance_forecast_with_ml(
                base_forecast, sales_data
            )
            
            # Генерируем ML-отчет
            ml_report = ml_integration.generate_ml_forecast_report(sales_data, stocks_data)
            
            if 'error' not in ml_report:
                logger.info("ML-отчет сгенерирован успешно")
                # Можно сохранить отчет в файл или базу данных
            
            logger.info(f"ML-улучшенный прогноз рассчитан для {len(enhanced_forecast)} SKU")
            return enhanced_forecast
            
        except Exception as e:
            logger.error(f"Ошибка расчета ML-улучшенного прогноза: {e}")
            # Возвращаем базовый прогноз в случае ошибки
            return self.calculate_forecast(
                self.prepare_sales_data(sales_data),
                self.prepare_stocks_data(stocks_data)
            )
    
    def generate_ml_forecast_report(self, sales_data: List[Dict[str, Any]], 
                                  stocks_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Генерирует отчет с ML-прогнозом
        """
        if not ML_AVAILABLE:
            return {'error': 'ML интеграция недоступна'}
        
        try:
            ml_integration = MLForecastIntegration()
            return ml_integration.generate_ml_forecast_report(sales_data, stocks_data)
        except Exception as e:
            logger.error(f"Ошибка генерации ML-отчета: {e}")
            return {'error': str(e)} 