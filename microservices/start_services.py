#!/usr/bin/env python3
"""
Скрипт для запуска всех микросервисов
"""

import os
import sys
import subprocess
import time
import signal
import logging
from typing import List, Dict
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MicroservicesManager:
    """Менеджер микросервисов"""
    
    def __init__(self):
        self.services = {
            'gateway': {
                'port': 8000,
                'path': 'gateway/main.py',
                'description': 'API Gateway'
            },
            'data-service': {
                'port': 8001,
                'path': 'data-service/main.py',
                'description': 'Data Service'
            },
            'forecast-service': {
                'port': 8002,
                'path': 'forecast-service/main.py',
                'description': 'Forecast Service'
            },
            'notification-service': {
                'port': 8003,
                'path': 'notification-service/main.py',
                'description': 'Notification Service'
            },
            'monitoring-service': {
                'port': 8004,
                'path': 'monitoring-service/main.py',
                'description': 'Monitoring Service'
            },
            'storage-service': {
                'port': 8005,
                'path': 'storage-service/main.py',
                'description': 'Storage Service'
            }
        }
        self.processes = {}
    
    def start_service(self, service_name: str) -> bool:
        """Запускает конкретный сервис"""
        if service_name not in self.services:
            logger.error(f"Сервис {service_name} не найден")
            return False
        
        service_config = self.services[service_name]
        service_path = Path(__file__).parent / service_config['path']
        
        if not service_path.exists():
            logger.error(f"Файл {service_path} не найден")
            return False
        
        try:
            # Запускаем сервис
            process = subprocess.Popen([
                sys.executable, str(service_path)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            self.processes[service_name] = process
            logger.info(f"Запущен {service_config['description']} (PID: {process.pid})")
            
            # Ждем немного для инициализации
            time.sleep(2)
            
            # Проверяем, что процесс запустился
            if process.poll() is None:
                logger.info(f"{service_config['description']} успешно запущен на порту {service_config['port']}")
                return True
            else:
                logger.error(f"Ошибка запуска {service_config['description']}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка запуска {service_name}: {e}")
            return False
    
    def stop_service(self, service_name: str) -> bool:
        """Останавливает конкретный сервис"""
        if service_name not in self.processes:
            logger.warning(f"Процесс {service_name} не найден")
            return False
        
        process = self.processes[service_name]
        
        try:
            # Отправляем сигнал завершения
            process.terminate()
            
            # Ждем завершения
            process.wait(timeout=10)
            
            logger.info(f"Сервис {service_name} остановлен")
            del self.processes[service_name]
            return True
            
        except subprocess.TimeoutExpired:
            # Принудительно завершаем
            process.kill()
            logger.warning(f"Сервис {service_name} принудительно остановлен")
            del self.processes[service_name]
            return True
        except Exception as e:
            logger.error(f"Ошибка остановки {service_name}: {e}")
            return False
    
    def start_all_services(self) -> bool:
        """Запускает все сервисы"""
        logger.info("Запуск всех микросервисов...")
        
        success_count = 0
        total_services = len(self.services)
        
        for service_name in self.services:
            logger.info(f"Запуск {service_name}...")
            if self.start_service(service_name):
                success_count += 1
            else:
                logger.error(f"Не удалось запустить {service_name}")
        
        logger.info(f"Запущено {success_count} из {total_services} сервисов")
        return success_count == total_services
    
    def stop_all_services(self) -> bool:
        """Останавливает все сервисы"""
        logger.info("Остановка всех микросервисов...")
        
        success_count = 0
        total_services = len(self.processes)
        
        for service_name in list(self.processes.keys()):
            if self.stop_service(service_name):
                success_count += 1
        
        logger.info(f"Остановлено {success_count} из {total_services} сервисов")
        return success_count == total_services
    
    def check_service_health(self, service_name: str) -> bool:
        """Проверяет здоровье сервиса"""
        if service_name not in self.services:
            return False
        
        process = self.processes.get(service_name)
        if not process:
            return False
        
        return process.poll() is None
    
    def get_status(self) -> Dict[str, Dict]:
        """Получает статус всех сервисов"""
        status = {}
        
        for service_name, service_config in self.services.items():
            is_running = self.check_service_health(service_name)
            process = self.processes.get(service_name)
            
            status[service_name] = {
                'running': is_running,
                'port': service_config['port'],
                'description': service_config['description'],
                'pid': process.pid if process and is_running else None
            }
        
        return status
    
    def print_status(self):
        """Выводит статус всех сервисов"""
        status = self.get_status()
        
        print("\n" + "="*60)
        print("СТАТУС МИКРОСЕРВИСОВ")
        print("="*60)
        
        for service_name, info in status.items():
            status_icon = "🟢" if info['running'] else "🔴"
            print(f"{status_icon} {service_name}")
            print(f"   Описание: {info['description']}")
            print(f"   Порт: {info['port']}")
            print(f"   Статус: {'Запущен' if info['running'] else 'Остановлен'}")
            if info['pid']:
                print(f"   PID: {info['pid']}")
            print()
    
    def wait_for_services(self, timeout: int = 60) -> bool:
        """Ждет готовности всех сервисов"""
        logger.info(f"Ожидание готовности сервисов (таймаут: {timeout}с)...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            all_ready = True
            
            for service_name in self.services:
                if not self.check_service_health(service_name):
                    all_ready = False
                    break
            
            if all_ready:
                logger.info("Все сервисы готовы!")
                return True
            
            time.sleep(1)
        
        logger.error("Таймаут ожидания готовности сервисов")
        return False

def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info("Получен сигнал завершения, останавливаем сервисы...")
    manager.stop_all_services()
    sys.exit(0)

def main():
    """Основная функция"""
    global manager
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Создаем менеджер
    manager = MicroservicesManager()
    
    # Парсим аргументы командной строки
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python start_services.py start    - запустить все сервисы")
        print("  python start_services.py stop     - остановить все сервисы")
        print("  python start_services.py status   - показать статус")
        print("  python start_services.py restart  - перезапустить все сервисы")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "start":
        print("Запуск микросервисов...")
        if manager.start_all_services():
            print("✅ Все сервисы запущены успешно!")
            
            # Ждем готовности сервисов
            if manager.wait_for_services():
                print("🎉 Система готова к работе!")
                print("\nДоступные эндпоинты:")
                print("  API Gateway: http://localhost:8000")
                print("  Data Service: http://localhost:8001")
                print("  Forecast Service: http://localhost:8002")
                print("  Notification Service: http://localhost:8003")
                print("  Monitoring Service: http://localhost:8004")
                print("  Storage Service: http://localhost:8005")
                
                # Держим процесс активным
                try:
                    while True:
                        time.sleep(1)
                        # Проверяем, что все сервисы еще работают
                        for service_name in manager.services:
                            if not manager.check_service_health(service_name):
                                logger.error(f"Сервис {service_name} остановился")
                                break
                except KeyboardInterrupt:
                    print("\nПолучен сигнал завершения...")
            else:
                print("❌ Не все сервисы готовы к работе")
        else:
            print("❌ Ошибка запуска сервисов")
            sys.exit(1)
    
    elif command == "stop":
        print("Остановка микросервисов...")
        if manager.stop_all_services():
            print("✅ Все сервисы остановлены")
        else:
            print("❌ Ошибка остановки сервисов")
            sys.exit(1)
    
    elif command == "status":
        manager.print_status()
    
    elif command == "restart":
        print("Перезапуск микросервисов...")
        manager.stop_all_services()
        time.sleep(2)
        if manager.start_all_services():
            print("✅ Все сервисы перезапущены успешно!")
        else:
            print("❌ Ошибка перезапуска сервисов")
            sys.exit(1)
    
    else:
        print(f"Неизвестная команда: {command}")
        sys.exit(1)

if __name__ == "__main__":
    manager = None
    main() 