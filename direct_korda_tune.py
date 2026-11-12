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
        "AutotargetingSettingsCategoriesFieldNames": ["Exact", "Narrow", "Alternative", "Accessory", "Broader"],
    })["Keywords"]


before = read_targets()
assert len(before) == len(TARGETS)
for item in before:
    assert item["CampaignId"] == CAMPAIGN_ID
    assert item["AdGroupId"] == TARGETS[item["Id"]]
    assert item["Keyword"] == "---autotargeting"
    assert item["State"] == "ON"
    assert item["Status"] == "ACCEPTED"

categories = {"Exact": "YES", "Narrow": "NO", "Alternative": "NO", "Accessory": "NO", "Broader": "NO"}
result = call("keywords", "update", {"Keywords": [
    {"Id": item["Id"], "AutotargetingSettings": {"Categories": categories}}
    for item in before
]})
assert all(item.get("Id") in TARGETS and not item.get("Errors") for item in result["UpdateResults"])

after = read_targets()
assert len(after) == len(TARGETS)
print(json.dumps({"before": before, "result": result, "after": after}, ensure_ascii=False))
if not all(item["AutotargetingSettings"]["Categories"] == categories for item in after):
    raise RuntimeError("autotargeting readback did not confirm target-only categories")

campaign = call("campaigns", "get", {
    "SelectionCriteria": {"Ids": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "Status", "State", "StatusPayment"],
})["Campaigns"][0]
assert campaign == {"Id": CAMPAIGN_ID, "Status": "ACCEPTED", "State": "ON", "StatusPayment": "ALLOWED"}

print(json.dumps({"campaign": campaign}, ensure_ascii=False))
