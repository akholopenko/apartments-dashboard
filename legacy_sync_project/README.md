# iCal Sync Monitor

Скрипт объединяет события из Airbnb/Booking iCal, формирует единый `synced_calendar.ics` и отдает его по HTTP.

## Файлы проекта

- `monitor_calendar.py` - загрузка источников, парсинг, merge, детект конфликтов, генерация `synced_calendar.ics`
- `server.py` - HTTP-сервер для выдачи `GET /synced_calendar.ics`
- `config.json` - ссылки iCal и параметры
- `events.json` - локальное состояние бронирований
- `monitor.log`, `server.log` - логи
- `run_monitor.bat`, `run_server.bat` - быстрый запуск

## Быстрый старт

1. Установить зависимости:
```bash
python -m pip install -r requirements.txt
```

2. Проверить `config.json`:
- `ical_urls` - актуальные private iCal URL
- `max_stay_days` - `0` = без лимита длины блока
- `request_timeout_seconds` - таймаут HTTP

3. Запустить монитор:
```bat
run_monitor.bat
```

4. Запустить сервер (во втором окне):
```bat
run_server.bat
```

5. Локальная проверка:
- открыть `http://127.0.0.1:8000/synced_calendar.ics`
- убедиться, что файл отдается и обновляется

## Порядок тестирования перед реальным объектом

1. Очистить старое состояние (опционально, если нужен чистый старт):
- остановить монитор
- удалить `events.json`
- запустить `run_monitor.bat`

2. Проверить загрузку источников:
- в `monitor.log` должны быть `Calendar loaded: ...`
- не должно быть постоянных `HTTPError 400/401/403/410`

3. Проверить генерацию файла:
- в логе должно быть `ICS file updated`
- в `synced_calendar.ics` должны появляться актуальные диапазоны

4. Проверить выдачу по HTTP:
- открыть `http://127.0.0.1:8000/synced_calendar.ics`
- в `server.log` должны быть `Calendar requested`

5. Тест на стороне OTA:
- добавить URL `http(s)://.../synced_calendar.ics` в тестовый календарь OTA
- дождаться первого импорта и сверить 2-3 контрольных диапазона дат

6. Наблюдение 24-48 часов:
- следить за `monitor.log` и `server.log`
- убедиться, что нет регулярных ошибок и ложных отмен

## Как открыть календарь в интернет

Нужен публичный URL вида `https://<host>/synced_calendar.ics`.

### Вариант 1: Cloudflare Tunnel (рекомендуется)

Плюсы: не нужен белый IP, проще и безопаснее, HTTPS из коробки.  
Схема:
1. Поднять локально `server.py` на `8000`.
2. Поднять Cloudflare Tunnel на локальный порт `8000`.
3. Получить публичный домен `https://.../synced_calendar.ics`.
4. Вставить URL в OTA.

### Вариант 2: ngrok

Плюсы: очень быстро для теста.  
Минусы: бесплатные URL могут меняться.

1. Запустить `server.py` (порт 8000).
2. Поднять туннель на `8000`.
3. Использовать выданный `https://.../synced_calendar.ics`.

### Вариант 3: Проброс порта на роутере (Port Forwarding)

Плюсы: без стороннего туннеля.  
Минусы: нужен белый IP, выше риски безопасности.

1. Открыть внешний порт -> `localhost:8000`.
2. Настроить firewall.
3. Желательно поставить reverse proxy с HTTPS (Nginx/Caddy).

## Минимальные требования безопасности

1. Использовать HTTPS-ссылку для OTA.
2. Не публиковать `config.json` и private iCal URL.
3. Ограничить доступ к серверу (firewall / allowlist, если возможно).
4. Регулярно проверять логи на неожиданные запросы.

## Типовые проблемы

1. `No module named requests`:
```bash
python -m pip install -r requirements.txt
```

2. Booking `400 Bad Request`:
- обычно ссылка истекла/отозвана
- сгенерировать новый private iCal URL и обновить `config.json`

3. Длинные блокировки не попадают:
- проверить `max_stay_days`
- если нужен полный горизонт, поставить `0`

## Auto Refresh Bot (PoC)

Файлы:
- `refresh_bot.py` - Playwright-бот для клика `Refresh connection`
- `refresh_bot_config.json` - URL и селекторы
- `run_refresh_bot.bat` - быстрый запуск

Подготовка:
1. Установить зависимости:
```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```
2. Задать переменные окружения:
```powershell
$env:BOOKING_USERNAME="your_login"
$env:BOOKING_PASSWORD="your_password"
```

Запуск:
```bat
run_refresh_bot.bat
```

Что делает бот:
1. Открывает страницу Booking с подключениями.
2. Если не залогинен - пытается войти.
3. Ждет ручное прохождение 2FA (`manual_2fa_timeout_seconds`).
4. Нажимает `Refresh connection`.
5. Сохраняет сессию в `booking_storage_state.json`.
6. Пишет лог в `refresh_bot.log` и скриншот в `refresh_bot_last.png`.

Важно:
- Это временный RPA-подход, он может ломаться при изменении интерфейса Booking.
- Проверьте правила платформы и используйте отдельного техпользователя.
