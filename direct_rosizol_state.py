#!/usr/bin/env python3
import json
import os
import urllib.request


API = "https://api.direct.yandex.com/json/v501"
CAMPAIGN_ID = 116349746
HEADERS = {
    "Authorization": f"Bearer {os.environ['YANDEX_DIRECT_TOKEN']}",
    "Client-Login": os.environ["YANDEX_DIRECT_LOGIN"],
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
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload["result"]


base = call("campaigns", {
    "SelectionCriteria": {"Ids": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "Name", "Type", "Status", "State", "StatusPayment"],
})["Campaigns"]
assert len(base) == 1 and base[0]["Id"] == CAMPAIGN_ID

type_fields = (
    {"UnifiedCampaignFieldNames": ["CounterIds", "PriorityGoals", "BiddingStrategy", "Settings"]}
    if base[0]["Type"] == "UNIFIED_CAMPAIGN"
    else {"TextCampaignFieldNames": ["CounterIds", "PriorityGoals", "BiddingStrategy", "Settings"]}
)
campaign = call("campaigns", {
    "SelectionCriteria": {"Ids": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "Name", "Type", "Status", "State", "StatusPayment"],
    **type_fields,
})["Campaigns"][0]

groups = call("adgroups", {
    "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "Name", "Status", "ServingStatus"],
})["AdGroups"]
ads = call("ads", {
    "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "CampaignId", "AdGroupId", "Type", "State", "Status", "StatusClarification"],
})["Ads"]

print(json.dumps({"campaign": campaign, "groups": groups, "ads": ads}, ensure_ascii=False))
