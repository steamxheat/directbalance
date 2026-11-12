#!/usr/bin/env python3
import json
import os
import urllib.request


request = urllib.request.Request(
    "https://api.direct.yandex.ru/v4/json/",
    data=json.dumps({
        "method": "GetStatGoals",
        "token": os.environ["YANDEX_DIRECT_TOKEN"],
        "locale": "ru",
        "param": {"CampaignID": 715995851},
    }).encode(),
    headers={"Content-Type": "application/json; charset=utf-8"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=60) as response:
    payload = json.load(response)
if payload.get("error_code") is not None or payload.get("error_str"):
    raise RuntimeError(payload)
print(json.dumps(payload.get("data", []), ensure_ascii=False))
