import unittest
from decimal import Decimal

from balance_bot import format_money, parse_balance


class BalanceBotTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
