#!/usr/bin/env python3
import json
import os
import urllib.request


API = "https://api.direct.yandex.com/json/v501"
CAMPAIGN_ID = 715995851
TARGETS = {
    205822089252: 5822089252,  # Тканевые компенсаторы
    205822091159: 5822091159,  # Шумоизоляционные чехлы
    205822093281: 5822093281,  # Шумозащитные кабины
}
HEADERS = {
    "Authorization": f"Bearer {os.environ['YANDEX_DIRECT_TOKEN']}",
    "Client-Login": os.environ["YANDEX_DIRECT_LOGIN"],
    "Accept-Language": "ru",
    "Content-Type": "application/json; charset=utf-8",
}


def call(service, method, params):
    request = urllib.request.Request(
        f"{API}/{service}",
        data=json.dumps({"method": method, "params": params}).encode(),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload["result"]


def read_targets():
    return call("keywords", "get", {
        "SelectionCriteria": {"Ids": list(TARGETS)},
        "FieldNames": ["Id", "Keyword", "CampaignId", "AdGroupId", "State", "Status"],
    })["Keywords"]


before = read_targets()
assert len(before) == len(TARGETS)
for item in before:
    assert item["CampaignId"] == CAMPAIGN_ID
    assert item["AdGroupId"] == TARGETS[item["Id"]]
    assert item["Keyword"] == "---autotargeting"
    assert item["State"] in ("ON", "SUSPENDED")
    assert item["Status"] == "ACCEPTED"

active_ids = [item["Id"] for item in before if item["State"] == "ON"]
result = call("keywords", "suspend", {"SelectionCriteria": {"Ids": active_ids}}) if active_ids else {"SuspendResults": []}

after = read_targets()
assert len(after) == len(TARGETS)
print(json.dumps({"before": before, "result": result, "after": after}, ensure_ascii=False))
if not all(item["State"] == "SUSPENDED" and item["Status"] == "ACCEPTED" for item in after):
    raise RuntimeError("autotargeting readback did not confirm suspension")

campaign = call("campaigns", "get", {
    "SelectionCriteria": {"Ids": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "Status", "State", "StatusPayment"],
})["Campaigns"][0]
assert campaign == {"Id": CAMPAIGN_ID, "Status": "ACCEPTED", "State": "ON", "StatusPayment": "ALLOWED"}

print(json.dumps({"campaign": campaign}, ensure_ascii=False))
