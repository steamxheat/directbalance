#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo


DIRECT_API_URL = "https://api.direct.yandex.ru/live/v4/json/"
DIRECT_REPORTS_URL = "https://api.direct.yandex.com/json/v501/reports"
TELEGRAM_API_URL = "https://api.telegram.org"


def post_json(url, payload, headers=None):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            detail = {"error": f"HTTP {error.code}"}
        raise RuntimeError(str(detail)) from error


def parse_balance(response, login):
    if "error_code" in response:
        raise RuntimeError(
            f"Direct API {response['error_code']}: {response.get('error_str', 'unknown error')}"
        )

    accounts = response.get("data", {}).get("Accounts", [])
    account = next(
        (item for item in accounts if item.get("Login", "").lower() == login.lower()),
        accounts[0] if len(accounts) == 1 else None,
    )
    if not account or "Amount" not in account:
        raise RuntimeError(f"Баланс аккаунта {login} не найден в ответе Direct API")

    try:
        amount = Decimal(str(account["Amount"]))
    except InvalidOperation as error:
        raise RuntimeError("Direct API вернул некорректную сумму баланса") from error
    return amount, account.get("Currency", "RUB")


def get_balance(token, login):
    response = post_json(
        DIRECT_API_URL,
        {
            "method": "AccountManagement",
            # eLama accounts return their own shared balance only without SelectionCriteria.
            "param": {"Action": "Get"},
            "locale": "ru",
            "token": token,
        },
        {
            "Authorization": f"Bearer {token}",
            "Accept-Language": "ru",
        },
    )
    return parse_balance(response, login)


def parse_daily_spend(report, days):
    total = Decimal("0")
    for line in report.splitlines():
        columns = line.split("\t")
        if len(columns) != 2 or columns[1] in {"", "--"}:
            continue
        try:
            total += Decimal(columns[1])
        except InvalidOperation as error:
            raise RuntimeError("Direct API вернул некорректный расход") from error
    return total / days


def get_average_daily_spend(token, login, days=7):
    today = datetime.now(ZoneInfo("Europe/Moscow")).date()
    date_to = today - timedelta(days=1)
    date_from = date_to - timedelta(days=days - 1)
    payload = {
        "params": {
            "SelectionCriteria": {
                "DateFrom": date_from.isoformat(),
                "DateTo": date_to.isoformat(),
            },
            "FieldNames": ["Date", "Cost"],
            "ReportName": "Direct balance forecast",
            "ReportType": "ACCOUNT_PERFORMANCE_REPORT",
            "DateRangeType": "CUSTOM_DATE",
            "Format": "TSV",
            "IncludeVAT": "YES",
            "IncludeDiscount": "YES",
        }
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept-Language": "ru",
        "Client-Login": login,
        "returnMoneyInMicros": "false",
        "skipReportHeader": "true",
        "skipColumnHeader": "true",
        "skipReportSummary": "true",
        "processingMode": "online",
    }

    request = urllib.request.Request(
        DIRECT_REPORTS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8", **headers},
        method="POST",
    )
    for _ in range(6):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return parse_daily_spend(response.read().decode("utf-8"), days)
        except urllib.error.HTTPError as error:
            if error.code not in {201, 202}:
                detail = error.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Direct Reports HTTP {error.code}: {detail}") from error
            time.sleep(min(int(error.headers.get("retryIn", "5")), 30))
    raise RuntimeError("Direct Reports не успел сформировать отчёт")


def format_money(amount, currency):
    value = f"{amount.quantize(Decimal('0.01')):,.2f}".replace(",", " ")
    return f"{value} ₽" if currency in {"RUB", "RUR"} else f"{value} {currency}"


def format_forecast(amount, daily_spend, now):
    if amount <= 0:
        return "Баланс уже исчерпан."
    if daily_spend <= 0:
        return "За последние 7 полных дней расхода не было — прогноз пока невозможен."

    days_left = amount / daily_spend
    end_at = now + timedelta(days=float(days_left))
    return (
        f"Средний расход: {format_money(daily_spend, 'RUB')} в сутки (7 дней)\n"
        f"Прогноз: примерно на {days_left:.1f} дня, до {end_at:%d.%m.%Y}"
    )


def send_telegram(bot_token, chat_id, text):
    response = post_json(
        f"{TELEGRAM_API_URL}/bot{bot_token}/sendMessage",
        {"chat_id": chat_id, "text": text},
    )
    if not response.get("ok"):
        raise RuntimeError(f"Telegram API: {response.get('description', 'unknown error')}")


def required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Не задан секрет {name}")
    return value


def main():
    direct_token = required_env("YANDEX_DIRECT_TOKEN")
    bot_token = required_env("TELEGRAM_BOT_TOKEN")
    chat_id = required_env("TELEGRAM_CHAT_ID")
    login = os.environ.get("YANDEX_DIRECT_LOGIN", "e-20086596")

    try:
        amount, currency = get_balance(direct_token, login)
        daily_spend = get_average_daily_spend(direct_token, login)
        now = datetime.now(ZoneInfo("Europe/Moscow"))
        text = (
            f"Баланс Яндекс Директа: {format_money(amount, currency)}\n"
            f"{format_forecast(amount, daily_spend, now)}\n"
            f"Аккаунт: {login}\n"
            f"Проверено: {now:%d.%m.%Y в %H:%M} МСК"
        )
    except Exception as error:
        text = f"Не удалось проверить баланс Яндекс Директа ({login}): {error}"
        send_telegram(bot_token, chat_id, text)
        raise

    send_telegram(bot_token, chat_id, text)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(error, file=sys.stderr)
        sys.exit(1)
