#!/usr/bin/env python3
"""
Скрипт для запуска тестов с различными опциями
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(command):
    """Выполняет команду и возвращает результат"""
    print(f"Выполняем команду: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.stdout:
        print("STDOUT:")
        print(result.stdout)
    
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    
    return result.returncode == 0

def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python run_tests.py [опция]")
        print("\nОпции:")
        print("  unit        - Запустить только unit-тесты")
        print("  integration - Запустить только интеграционные тесты")
        print("  all         - Запустить все тесты")
        print("  coverage    - Запустить тесты с отчетом о покрытии")
        print("  fast        - Запустить быстрые тесты (исключить медленные)")
        print("  clean       - Очистить кэш и временные файлы")
        return
    
    option = sys.argv[1]
    
    if option == "unit":
        print("🧪 Запуск unit-тестов...")
        success = run_command("pytest tests/ -m unit -v")
        
    elif option == "integration":
        print("🔗 Запуск интеграционных тестов...")
        success = run_command("pytest tests/ -m integration -v")
        
    elif option == "all":
        print("🚀 Запуск всех тестов...")
        success = run_command("pytest tests/ -v")
        
    elif option == "coverage":
        print("📊 Запуск тестов с отчетом о покрытии...")
        success = run_command("pytest tests/ --cov=. --cov-report=html --cov-report=term-missing -v")
        if success:
            print("\n📈 Отчет о покрытии создан в htmlcov/index.html")
        
    elif option == "fast":
        print("⚡ Запуск быстрых тестов...")
        success = run_command("pytest tests/ -m 'not slow' -v")
        
    elif option == "clean":
        print("🧹 Очистка временных файлов...")
        # Удаляем временные файлы
        temp_dirs = ["__pycache__", ".pytest_cache", "htmlcov", ".coverage"]
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)
                print(f"Удален: {temp_dir}")
        
        # Удаляем временные файлы тестов
        test_dirs = ["test_cache", "test_data"]
        for test_dir in test_dirs:
            if os.path.exists(test_dir):
                import shutil
                shutil.rmtree(test_dir)
                print(f"Удален: {test_dir}")
        
        print("✅ Очистка завершена")
        return
        
    else:
        print(f"❌ Неизвестная опция: {option}")
        return
    
    if success:
        print("✅ Тесты прошли успешно!")
    else:
        print("❌ Тесты завершились с ошибками!")
        sys.exit(1)

if __name__ == "__main__":
    main() 