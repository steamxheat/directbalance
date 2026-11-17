#!/usr/bin/env python3
import json
import os
import urllib.request


API = "https://api.direct.yandex.com/json/v501"
HEADERS = {
    "Authorization": f"Bearer {os.environ['YANDEX_DIRECT_TOKEN']}",
    "Client-Login": "e-20086596",
    "Accept-Language": "ru",
    "Content-Type": "application/json; charset=utf-8",
}


def call(service, params):
    request = urllib.request.Request(
        f"{API}/{service}",
        data=json.dumps({"method": "get", "params": params}).encode(),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    if payload.get("error"):
        raise RuntimeError(json.dumps(payload["error"], ensure_ascii=False))
    return payload["result"]


campaign = call("campaigns", {
    "SelectionCriteria": {"Ids": [706863240]},
    "FieldNames": ["Id", "Name", "Status", "State", "StatusPayment"],
})["Campaigns"][0]
group = call("adgroups", {
    "SelectionCriteria": {"Ids": [5826331360]},
    "FieldNames": ["Id", "Name", "Status", "ServingStatus"],
})["AdGroups"][0]
ads = call("ads", {
    "SelectionCriteria": {"AdGroupIds": [5826331360]},
    "FieldNames": ["Id", "Status", "State", "StatusClarification"],
})["Ads"]
print(json.dumps({"campaign": campaign, "group": group, "ads": ads}, ensure_ascii=False, indent=2))
