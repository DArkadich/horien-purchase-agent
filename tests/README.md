# Тестирование системы Horiens Purchase Agent

## Обзор

Система тестирования включает в себя unit-тесты, интеграционные тесты и end-to-end тесты для обеспечения надежности и качества кода.

## Структура тестов

```
tests/
├── __init__.py              # Пакет тестов
├── conftest.py              # Конфигурация pytest и фикстуры
├── test_config.py           # Тесты конфигурации
├── test_forecast.py         # Тесты прогнозирования
├── test_cache_manager.py    # Тесты кэширования
├── test_ozon_api.py         # Тесты API
├── test_integration.py      # Интеграционные тесты
└── README.md               # Документация по тестированию
```

## Типы тестов

### 1. Unit-тесты
- **Назначение**: Тестирование отдельных функций и классов
- **Файлы**: `test_config.py`, `test_forecast.py`, `test_cache_manager.py`, `test_ozon_api.py`
- **Маркер**: `@pytest.mark.unit`

### 2. Интеграционные тесты
- **Назначение**: Тестирование взаимодействия между модулями
- **Файл**: `test_integration.py`
- **Маркер**: `@pytest.mark.integration`

### 3. End-to-End тесты
- **Назначение**: Тестирование полного рабочего процесса
- **Файл**: `test_integration.py` (класс `TestEndToEndIntegration`)
- **Маркер**: `@pytest.mark.integration`

## Запуск тестов

### Базовые команды

```bash
# Запуск всех тестов
pytest tests/ -v

# Запуск только unit-тестов
pytest tests/ -m unit -v

# Запуск только интеграционных тестов
pytest tests/ -m integration -v

# Запуск тестов с отчетом о покрытии
pytest tests/ --cov=. --cov-report=html --cov-report=term-missing -v
```

### Использование скрипта run_tests.py

```bash
# Запуск всех тестов
python run_tests.py all

# Запуск unit-тестов
python run_tests.py unit

# Запуск интеграционных тестов
python run_tests.py integration

# Запуск с отчетом о покрытии
python run_tests.py coverage

# Запуск быстрых тестов (исключить медленные)
python run_tests.py fast

# Очистка временных файлов
python run_tests.py clean
```

## Фикстуры

### Основные фикстуры (conftest.py)

- `temp_dir` - Временная директория для тестов
- `test_cache_dir` - Директория для тестового кэша
- `test_data_dir` - Директория для тестовых данных
- `mock_ozon_api` - Мок для OzonAPI
- `sample_sales_data` - Тестовые данные о продажах
- `sample_stocks_data` - Тестовые данные об остатках
- `mock_telegram` - Мок для TelegramNotifier
- `mock_sheets` - Мок для GoogleSheets
- `patch_env_vars` - Патч переменных окружения

## Покрытие кода

### Цели покрытия

- **Unit-тесты**: 90%+ покрытие основных функций
- **Интеграционные тесты**: 80%+ покрытие взаимодействий
- **End-to-End тесты**: 70%+ покрытие рабочих процессов

### Генерация отчета о покрытии

```bash
# Генерация HTML отчета
pytest tests/ --cov=. --cov-report=html

# Отчет будет доступен в htmlcov/index.html
```

## Тестовые данные

### Структура тестовых данных

```python
# Данные о продажах
sample_sales_data = [
    {
        "sku": "SKU_001",
        "date": "2024-01-01",
        "quantity": 10,
        "revenue": 1000
    },
    # ...
]

# Данные об остатках
sample_stocks_data = [
    {
        "sku": "SKU_001",
        "stock": 50,
        "reserved": 10
    },
    # ...
]
```

## Моки и заглушки

### Используемые моки

1. **OzonAPI** - Мокается для избежания реальных API вызовов
2. **TelegramNotifier** - Мокается для избежания отправки сообщений
3. **GoogleSheets** - Мокается для избежания записи в Google Sheets
4. **CacheManager** - Используется с временными директориями

### Пример использования мока

```python
def test_with_mock(mock_ozon_api):
    """Тест с использованием мока"""
    # mock_ozon_api уже настроен в фикстуре
    result = mock_ozon_api.get_products()
    assert result is not None
```

## Асинхронные тесты

### Тестирование async функций

```python
@pytest.mark.asyncio
async def test_async_function():
    """Тест асинхронной функции"""
    result = await some_async_function()
    assert result is not None
```

## Обработка ошибок

### Тестирование исключений

```python
def test_exception_handling():
    """Тест обработки исключений"""
    with pytest.raises(ValueError):
        function_that_raises_error()
```

## Настройка окружения

### Переменные окружения для тестов

Тесты используют фикстуру `patch_env_vars`, которая устанавливает тестовые значения:

```python
@pytest.fixture
def patch_env_vars():
    with patch.dict(os.environ, {
        'OZON_CLIENT_ID': 'test_client_id',
        'OZON_API_KEY': 'test_api_key',
        # ...
    }):
        yield
```

## Добавление новых тестов

### Структура нового теста

```python
class TestNewModule:
    """Тесты для нового модуля"""
    
    def test_basic_functionality(self):
        """Базовый тест функциональности"""
        # Arrange
        # Act
        # Assert
        pass
    
    @pytest.mark.integration
    def test_integration_with_other_module(self):
        """Интеграционный тест"""
        pass
    
    @pytest.mark.asyncio
    async def test_async_functionality(self):
        """Тест асинхронной функциональности"""
        pass
```

### Маркировка тестов

```python
@pytest.mark.unit          # Unit-тест
@pytest.mark.integration   # Интеграционный тест
@pytest.mark.slow          # Медленный тест
@pytest.mark.asyncio       # Асинхронный тест
```

## CI/CD интеграция

### GitHub Actions (пример)

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest tests/ --cov=. --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v1
```

## Отладка тестов

### Полезные опции pytest

```bash
# Подробный вывод
pytest tests/ -v -s

# Остановка на первой ошибке
pytest tests/ -x

# Запуск конкретного теста
pytest tests/test_forecast.py::TestPurchaseForecast::test_calculate_forecast

# Запуск тестов с определенной маркой
pytest tests/ -m "not slow"
```

## Лучшие практики

1. **Изоляция тестов** - Каждый тест должен быть независимым
2. **Использование фикстур** - Переиспользуйте общие настройки
3. **Мокирование внешних зависимостей** - Не делайте реальные API вызовы
4. **Покрытие граничных случаев** - Тестируйте ошибки и исключения
5. **Читаемые имена тестов** - Используйте описательные имена
6. **Документация тестов** - Добавляйте docstrings к тестам 