#!/usr/bin/env python3
import json
import os
import urllib.error
import urllib.request


API = "https://api.direct.yandex.com/json/v501"
CAMPAIGN_ID = 715995851


def call(service, method, params):
    request = urllib.request.Request(
        f"{API}/{service}",
        data=json.dumps({"method": method, "params": params}).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['YANDEX_DIRECT_TOKEN']}",
            "Client-Login": os.environ.get("YANDEX_DIRECT_LOGIN", "e-20086596"),
            "Accept-Language": "ru",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Direct API HTTP {error.code}") from error
    if "error" in payload:
        error = payload["error"]
        raise RuntimeError(
            f"Direct API {error.get('error_code')}: {error.get('error_string')}: {error.get('error_detail')}"
        )
    return payload["result"]


def main():
    groups = call(
        "adgroups",
        "get",
        {
            "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
            "FieldNames": ["Id", "Name", "CampaignId", "Status", "Type", "RegionIds", "NegativeKeywords"],
        },
    )["AdGroups"]
    group_ids = [group["Id"] for group in groups]
    ads = call(
        "ads",
        "get",
        {
            "SelectionCriteria": {"AdGroupIds": group_ids},
            "FieldNames": ["Id", "CampaignId", "AdGroupId", "Type", "Status", "State"],
            "ResponsiveAdFieldNames": [
                "Titles", "Texts", "Href", "SitelinkSetId", "AdExtensions", "BusinessId"
            ],
        },
    )["Ads"]
    keywords = call(
        "keywords",
        "get",
        {
            "SelectionCriteria": {"AdGroupIds": group_ids},
            "FieldNames": ["Id", "AdGroupId", "Keyword", "Status", "State", "StrategyPriority"],
        },
    )["Keywords"]
    print(json.dumps({"groups": groups, "ads": ads, "keywords": keywords}, ensure_ascii=False))


if __name__ == "__main__":
    main()
