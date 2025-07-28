# Настройка реальных данных для агента закупок Horiens

## 🎯 Цель
Переход от тестовых данных к реальным данным Ozon API

## 📋 Что нужно настроить

### 1. Ozon API Credentials

#### Получение API ключей:
1. Войдите в [Ozon Seller](https://seller.ozon.ru/)
2. Перейдите в **Настройки** → **API**
3. Создайте новый API ключ
4. Скопируйте **Client ID** и **API Key**

#### Настройка в .env файле:
```bash
# Создайте файл .env на основе env.example
cp env.example .env
```

Заполните в файле `.env`:
```env
# Ozon API credentials
OZON_API_KEY=ваш_реальный_api_ключ
OZON_CLIENT_ID=ваш_реальный_client_id

# Google Sheets API
GOOGLE_SERVICE_ACCOUNT_JSON={"type": "service_account", "project_id": "your_project", ...}
GOOGLE_SPREADSHEET_ID=ваш_id_таблицы

# Telegram Bot
TELEGRAM_TOKEN=ваш_токен_бота
TELEGRAM_CHAT_ID=ваш_chat_id
```

### 2. Google Sheets Setup

#### Создание Service Account:
1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Включите Google Sheets API
4. Создайте Service Account:
   - **IAM & Admin** → **Service Accounts**
   - **Create Service Account**
   - Скачайте JSON файл с ключами

#### Настройка Google Sheets:
1. Создайте новую Google таблицу
2. Скопируйте ID из URL: `https://docs.google.com/spreadsheets/d/ID_ТАБЛИЦЫ/edit`
3. Предоставьте доступ Service Account email'у

### 3. Telegram Bot Setup

#### Создание бота:
1. Напишите [@BotFather](https://t.me/botfather) в Telegram
2. Создайте нового бота: `/newbot`
3. Получите токен бота

#### Получение Chat ID:
1. Добавьте бота в нужный чат
2. Отправьте сообщение боту
3. Перейдите по ссылке: `https://api.telegram.org/botВАШ_ТОКЕН/getUpdates`
4. Найдите `chat_id` в ответе

## 🔧 Проверка настроек

### Тест Ozon API:
```bash
python3 test_ozon_api.py
```

### Тест Google Sheets:
```bash
python3 test_sheets.py
```

### Тест Telegram:
```bash
python3 test_telegram.py
```

## 📊 Ожидаемые результаты

### При правильной настройке:
- ✅ Реальные данные о продажах из Ozon API
- ✅ Реальные остатки товаров
- ✅ Корректная запись в Google Sheets
- ✅ Уведомления в Telegram

### Логи будут показывать:
```
Успешно получены товары: 150 шт
Получено 500 записей о продажах
Получено 25 записей об остатках
```

## 🚨 Возможные проблемы

### Ozon API 404 ошибки:
- Проверьте правильность API ключей
- Убедитесь, что у вас есть доступ к API
- Проверьте версию API (возможно, нужно обновить эндпоинты)

### Google Sheets ошибки:
- Проверьте права доступа Service Account
- Убедитесь, что ID таблицы правильный
- Проверьте формат JSON ключей

### Telegram ошибки:
- Проверьте токен бота
- Убедитесь, что бот добавлен в чат
- Проверьте Chat ID

## 🎯 Следующие шаги

1. **Настройте .env файл** с реальными данными
2. **Протестируйте каждый компонент** отдельно
3. **Запустите полную систему** с реальными данными
4. **Настройте автоматизацию** (cron, Docker, etc.)

## 📞 Поддержка

Если возникнут проблемы:
1. Проверьте логи на наличие ошибок
2. Убедитесь, что все переменные окружения настроены
3. Протестируйте каждый компонент отдельно
4. Обратитесь к документации Ozon API 