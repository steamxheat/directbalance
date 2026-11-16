import json
import os
import urllib.request


TOKEN = os.environ["YANDEX_DIRECT_TOKEN"]
LOGIN = os.environ.get("YANDEX_DIRECT_LOGIN", "e-20086596")
CAMPAIGN_ID = 706863240


def call(service, params):
    request = urllib.request.Request(
        f"https://api.direct.yandex.com/json/v5/{service}",
        data=json.dumps({"method": "get", "params": params}).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Client-Login": LOGIN,
            "Accept-Language": "ru",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


queries = {
    "campaign": (
        "campaigns",
        {
            "SelectionCriteria": {"Ids": [CAMPAIGN_ID]},
            "FieldNames": [
                "Id", "Name", "Type", "Status", "State", "StatusPayment",
                "StartDate", "EndDate", "DailyBudget",
            ],
        },
    ),
    "groups": (
        "adgroups",
        {
            "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
            "FieldNames": [
                "Id", "Name", "CampaignId", "RegionIds", "NegativeKeywords",
                "TrackingParams", "Status", "Type", "Subtype", "ServingStatus",
            ],
        },
    ),
    "ads": (
        "ads",
        {
            "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
            "FieldNames": [
                "Id", "CampaignId", "AdGroupId", "Status", "State",
                "StatusClarification", "Type", "Subtype",
            ],
            "TextAdFieldNames": [
                "Title", "Title2", "Text", "Href", "Mobile", "DisplayUrlPath",
                "VCardId", "AdImageHash", "SitelinkSetId", "AdExtensions",
                "VideoExtension", "TurboPageId", "BusinessId",
            ],
        },
    ),
    "keywords": (
        "keywords",
        {
            "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
            "FieldNames": [
                "Id", "Keyword", "AdGroupId", "CampaignId", "Bid", "ContextBid",
                "StrategyPriority", "UserParam1", "UserParam2", "Status", "State",
                "ServingStatus", "Productivity", "StatisticsSearch", "StatisticsNetwork",
            ],
        },
    ),
}

for label, (service, params) in queries.items():
    try:
        result = call(service, params)
    except Exception as error:
        result = {"exception": type(error).__name__, "message": str(error)}
    print(f"=== {label} ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))

campaign = call("campaigns", {
    "SelectionCriteria": {"Ids": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "Name", "Status", "State"],
})["result"]["Campaigns"][0]
groups = call("adgroups", {
    "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "Name", "Status", "ServingStatus"],
})["result"]["AdGroups"]
ads = call("ads", {
    "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "AdGroupId", "Status", "State", "StatusClarification"],
})["result"]["Ads"]
keywords = call("keywords", {
    "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "Keyword", "AdGroupId", "Status", "State", "ServingStatus"],
})["result"]["Keywords"]

summary = {"campaign": campaign, "groups": []}
for group in groups:
    group_ads = [row for row in ads if row["AdGroupId"] == group["Id"]]
    group_keywords = [row for row in keywords if row["AdGroupId"] == group["Id"]]
    summary["groups"].append({
        **group,
        "ads": [{key: row.get(key) for key in ("Id", "Status", "State", "StatusClarification")} for row in group_ads],
        "keyword_states": {state: sum(row["State"] == state for row in group_keywords) for state in {row["State"] for row in group_keywords}},
        "autotarget": [{key: row.get(key) for key in ("Id", "Status", "State", "ServingStatus")} for row in group_keywords if row["Keyword"] == "---autotargeting"],
    })
print("=== summary ===")
print(json.dumps(summary, ensure_ascii=False, indent=2))
