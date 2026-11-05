import unittest
from io import BytesIO
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch
from urllib.error import HTTPError

from balance_bot import (
    format_forecast,
    format_money,
    get_average_daily_spend,
    open_with_retry,
    parse_balance,
    parse_daily_spend,
)


class BalanceBotTest(unittest.TestCase):
    @patch("balance_bot.time.sleep")
    @patch("balance_bot.urllib.request.urlopen", side_effect=[TimeoutError(), "response"])
    def test_retries_timeout(self, urlopen, sleep):
        self.assertEqual(open_with_retry("request"), "response")
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(5)

    @patch("balance_bot.time.sleep")
    @patch("balance_bot.open_with_retry")
    def test_retries_reports_server_error(self, open_request, sleep):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def read(self):
                return b"2026-11-04\t700.00\n"

        open_request.side_effect = [
            HTTPError("url", 500, "error", {}, BytesIO(b"error")),
            Response(),
        ]

        self.assertEqual(get_average_daily_spend("token", "login"), Decimal("100.00"))
        self.assertEqual(open_request.call_count, 2)
        sleep.assert_called_once_with(5)

    def test_parses_requested_account(self):
        response = {
            "data": {
                "Accounts": [
                    {"Login": "other", "Amount": "10", "Currency": "RUB"},
                    {"Login": "e-20086596", "Amount": "5742.82", "Currency": "RUB"},
                ]
            }
        }

        self.assertEqual(
            parse_balance(response, "e-20086596"),
            (Decimal("5742.82"), "RUB"),
        )

    def test_rejects_api_error(self):
        with self.assertRaisesRegex(RuntimeError, "Direct API 53"):
            parse_balance({"error_code": 53, "error_str": "Authorization error"}, "login")

    def test_formats_rubles(self):
        self.assertEqual(format_money(Decimal("12345.6"), "RUB"), "12 345.60 ₽")

    def test_calculates_average_spend_including_zero_days(self):
        report = "2026-10-18\t700.00\n2026-10-20\t1400.00\n"
        self.assertEqual(parse_daily_spend(report, 7), Decimal("300.00"))

    def test_forecasts_balance_end(self):
        text = format_forecast(
            Decimal("1000"),
            Decimal("250"),
            datetime(2026, 10, 21, 12, 0),
        )
        self.assertIn("на 4.0 дня", text)
        self.assertIn("до 25.10.2026", text)


if __name__ == "__main__":
    unittest.main()
