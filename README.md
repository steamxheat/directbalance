# Direct Balance Bot

Личный Telegram-бот сообщает баланс аккаунта Яндекс Директа `e-20086596` каждые 6 часов. Также он считает средний расход за последние 7 полных дней и прогнозирует примерную дату исчерпания баланса.

## Что нужно один раз настроить

1. Создать бота через `@BotFather`, отправить ему `/start` и сохранить токен.
2. Получить свой Telegram chat ID через `https://api.telegram.org/bot<ТОКЕН>/getUpdates`.
3. Получить OAuth-токен Яндекс Директа с доступом к аккаунту `e-20086596`.
4. В GitHub открыть `Settings → Secrets and variables → Actions` и добавить:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `YANDEX_DIRECT_TOKEN`
5. Открыть `Actions → Direct balance → Run workflow` и проверить первое сообщение.

Токены нельзя добавлять в файлы репозитория или отправлять в чат.

## Проверка кода

```bash
python -m unittest -v
```

Расписание находится в `.github/workflows/balance.yml`. GitHub запускает его в `00:17`, `06:17`, `12:17` и `18:17` UTC; возможна небольшая задержка запуска со стороны GitHub.
