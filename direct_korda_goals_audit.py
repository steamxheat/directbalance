import json
import os
import urllib.request


request = urllib.request.Request(
    "https://api.direct.yandex.com/json/v5/campaigns",
    data=json.dumps(
        {
            "method": "get",
            "params": {
                "SelectionCriteria": {"Ids": [715995851]},
                "FieldNames": ["Id", "Name", "State", "Status", "Type"],
                "TextCampaignFieldNames": ["CounterIds", "PriorityGoals"],
            },
        }
    ).encode(),
    headers={
        "Authorization": f"Bearer {os.environ['YANDEX_DIRECT_TOKEN']}",
        "Client-Login": os.environ.get("YANDEX_DIRECT_LOGIN", "e-20086596"),
        "Accept-Language": "ru",
        "Content-Type": "application/json; charset=utf-8",
    },
)

with urllib.request.urlopen(request, timeout=30) as response:
    payload = json.load(response)

if "error" in payload:
    raise SystemExit(json.dumps(payload["error"], ensure_ascii=False))

print(json.dumps(payload["result"], ensure_ascii=False))
