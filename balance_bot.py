#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo


DIRECT_API_URL = "https://api.direct.yandex.ru/live/v4/json/"
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
            "param": {
                "Action": "Get",
                "SelectionCriteria": {"Logins": [login]},
            },
            "locale": "ru",
            "token": token,
        },
        {
            "Authorization": f"Bearer {token}",
            "Accept-Language": "ru",
        },
    )
    return parse_balance(response, login)


def format_money(amount, currency):
    value = f"{amount.quantize(Decimal('0.01')):,.2f}".replace(",", " ")
    return f"{value} ₽" if currency in {"RUB", "RUR"} else f"{value} {currency}"


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
        checked_at = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y в %H:%M")
        text = (
            f"Баланс Яндекс Директа: {format_money(amount, currency)}\n"
            f"Аккаунт: {login}\n"
            f"Проверено: {checked_at} МСК"
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
