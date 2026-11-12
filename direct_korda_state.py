#!/usr/bin/env python3
import json
import os
import urllib.request


API = "https://api.direct.yandex.com/json/v501"
CAMPAIGN_ID = 715995851


def call(service, params):
    request = urllib.request.Request(
        f"{API}/{service}",
        data=json.dumps({"method": "get", "params": params}).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['YANDEX_DIRECT_TOKEN']}",
            "Client-Login": os.environ["YANDEX_DIRECT_LOGIN"],
            "Accept-Language": "ru",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload["result"]


campaign = call("campaigns", {
    "SelectionCriteria": {"Ids": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "Name", "Type", "Status", "State", "StatusPayment"],
    "UnifiedCampaignFieldNames": ["CounterIds", "PriorityGoals", "BiddingStrategy", "Settings"],
})["Campaigns"][0]

groups = call("adgroups", {
    "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "Name", "Status", "ServingStatus"],
})["AdGroups"]

unified = campaign.get("UnifiedCampaign") or {}
print(json.dumps({
    "campaign": {key: campaign.get(key) for key in ["Id", "Name", "Type", "Status", "State", "StatusPayment"]},
    "counter_ids": (unified.get("CounterIds") or {}).get("Items", []),
    "priority_goals": (unified.get("PriorityGoals") or {}).get("Items", []),
    "bidding_strategy": unified.get("BiddingStrategy"),
    "settings": unified.get("Settings", []),
    "groups": sorted(groups, key=lambda item: item["Id"]),
}, ensure_ascii=False))
