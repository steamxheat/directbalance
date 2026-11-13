#!/usr/bin/env python3
import json
import os
import urllib.request


API = "https://api.direct.yandex.com/json/v501"
CAMPAIGN_ID = 715995851
OLD_COUNTER_ID = 62985049
NEW_COUNTER_ID = 32011556
OLD_GOAL_ID = 12
NEW_GOAL_ID = 136340635
HEADERS = {
    "Authorization": f"Bearer {os.environ['YANDEX_DIRECT_TOKEN']}",
    "Client-Login": "e-20086596",
    "Accept-Language": "ru",
    "Content-Type": "application/json; charset=utf-8",
}


def call(method, params):
    request = urllib.request.Request(
        f"{API}/campaigns",
        data=json.dumps({"method": method, "params": params}).encode(),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload["result"]


def read_campaign():
    campaigns = call("get", {
        "SelectionCriteria": {"Ids": [CAMPAIGN_ID]},
        "FieldNames": ["Id", "Name", "Type", "Status", "State", "StatusPayment"],
        "UnifiedCampaignFieldNames": ["CounterIds", "PriorityGoals", "BiddingStrategy", "Settings"],
    })["Campaigns"]
    assert len(campaigns) == 1
    return campaigns[0]


before = read_campaign()
unified_before = before["UnifiedCampaign"]
before_counters = (unified_before.get("CounterIds") or {}).get("Items", [])
before_goals = (unified_before.get("PriorityGoals") or {}).get("Items", [])
assert before["Id"] == CAMPAIGN_ID
assert before["Name"] == "Корда — Изомакс — Тильда"
assert before_counters == [OLD_COUNTER_ID]
assert len(before_goals) == 1 and before_goals[0]["GoalId"] == OLD_GOAL_ID

goal_value = before_goals[0]["Value"]
result = call("update", {"Campaigns": [{
    "Id": CAMPAIGN_ID,
    "UnifiedCampaign": {
        "CounterIds": {"Items": [NEW_COUNTER_ID]},
        "PriorityGoals": {"Items": [{
            "GoalId": NEW_GOAL_ID,
            "Value": goal_value,
            "Operation": "SET",
        }]},
    },
}]})
update_result = result["UpdateResults"]
assert len(update_result) == 1
assert update_result[0].get("Id") == CAMPAIGN_ID
assert not update_result[0].get("Errors")

after = read_campaign()
unified_after = after["UnifiedCampaign"]
assert (unified_after.get("CounterIds") or {}).get("Items", []) == [NEW_COUNTER_ID]
after_goals = (unified_after.get("PriorityGoals") or {}).get("Items", [])
assert len(after_goals) == 1
assert after_goals[0]["GoalId"] == NEW_GOAL_ID
assert after_goals[0]["Value"] == goal_value
assert {key: after[key] for key in ["Id", "Name", "Type", "Status", "State", "StatusPayment"]} == {
    key: before[key] for key in ["Id", "Name", "Type", "Status", "State", "StatusPayment"]
}
assert unified_after["BiddingStrategy"] == unified_before["BiddingStrategy"]
assert unified_after["Settings"] == unified_before["Settings"]

print(json.dumps({
    "campaign": CAMPAIGN_ID,
    "before": {"counter_ids": before_counters, "priority_goals": before_goals},
    "update": update_result,
    "after": {
        "counter_ids": unified_after["CounterIds"]["Items"],
        "priority_goals": after_goals,
        "status": after["Status"],
        "state": after["State"],
        "payment": after["StatusPayment"],
    },
}, ensure_ascii=False))
