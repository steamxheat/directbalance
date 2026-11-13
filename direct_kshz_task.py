#!/usr/bin/env python3
import json
import os
import urllib.request


API = "https://api.direct.yandex.com/json/v501"
CAMPAIGN_ID = 715995851
HEADERS = {
    "Authorization": f"Bearer {os.environ['YANDEX_DIRECT_TOKEN']}",
    "Client-Login": "e-20086596",
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


campaigns = call("campaigns", "get", {
    "SelectionCriteria": {"Ids": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "Name", "Type", "Status", "State", "StatusPayment"],
    "UnifiedCampaignFieldNames": ["CounterIds", "PriorityGoals", "BiddingStrategy", "Settings"],
})["Campaigns"]
assert len(campaigns) == 1

groups = call("adgroups", "get", {
    "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "Name", "CampaignId", "Status", "State", "ServingStatus", "Type", "RegionIds"],
})["AdGroups"]
target_groups = [group for group in groups if any(word in group["Name"].lower() for word in ("шум", "кожух", "кабин", "кшз"))]
target_ids = [group["Id"] for group in target_groups]

ads = call("ads", "get", {
    "SelectionCriteria": {"AdGroupIds": target_ids},
    "FieldNames": ["Id", "CampaignId", "AdGroupId", "Type", "Status", "State", "StatusClarification"],
    "ResponsiveAdFieldNames": ["Titles", "Texts", "Href", "SitelinkSetId", "AdExtensions", "BusinessId", "AdImages"],
})["Ads"]

keywords = call("keywords", "get", {
    "SelectionCriteria": {"AdGroupIds": target_ids},
    "FieldNames": ["Id", "AdGroupId", "Keyword", "Status", "State", "ServingStatus", "StrategyPriority"],
})["Keywords"]

image_hashes = sorted({
    image["ImageHash"]
    for ad in ads
    for image in ((ad.get("ResponsiveAd") or {}).get("AdImages") or {}).get("Items", [])
})
images = call("adimages", "get", {
    "SelectionCriteria": {"AdImageHashes": image_hashes},
    "FieldNames": ["AdImageHash", "Name", "Associated", "Type", "Subtype", "OriginalUrl", "PreviewUrl"],
})["AdImages"] if image_hashes else []

print(json.dumps({
    "campaign": campaigns[0],
    "all_groups": [{"Id": item["Id"], "Name": item["Name"], "Status": item["Status"], "State": item["State"]} for item in groups],
    "target_groups": target_groups,
    "ads": ads,
    "keywords": keywords,
    "images": images,
}, ensure_ascii=False))
