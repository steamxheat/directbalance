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
            "Client-Login": os.environ.get("YANDEX_DIRECT_LOGIN", "e-20086596"),
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


groups = call(
    "adgroups",
    {
        "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
        "FieldNames": ["Id", "Name", "Status", "ServingStatus"],
    },
)["AdGroups"]

ads = call(
    "ads",
    {
        "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
        "FieldNames": ["Id", "AdGroupId", "Type", "Status", "State", "StatusClarification"],
        "ResponsiveAdFieldNames": ["Href", "SitelinkSetId", "Titles", "Texts", "AdImages", "AdExtensions", "BusinessId"],
    },
)["Ads"]

set_ids = sorted(
    {
        ad["ResponsiveAd"].get("SitelinkSetId")
        for ad in ads
        if ad["Type"] == "RESPONSIVE_AD" and ad["ResponsiveAd"].get("SitelinkSetId")
    }
)
sitelinks = {}
if set_ids:
    for item in call(
        "sitelinks",
        {"SelectionCriteria": {"Ids": set_ids}, "FieldNames": ["Id", "Sitelinks"]},
    )["SitelinksSets"]:
        sitelinks[item["Id"]] = item["Sitelinks"]

group_names = {group["Id"]: group["Name"] for group in groups}
result = []
for ad in ads:
    if ad["Type"] != "RESPONSIVE_AD":
        continue
    responsive = ad["ResponsiveAd"]
    set_id = responsive.get("SitelinkSetId")
    result.append(
        {
            "id": ad["Id"],
            "group_id": ad["AdGroupId"],
            "group": group_names.get(ad["AdGroupId"]),
            "status": ad["Status"],
            "state": ad["State"],
            "href": responsive.get("Href"),
            "sitelink_set_id": set_id,
            "sitelinks": sitelinks.get(set_id, []),
            "titles": len(responsive.get("Titles", [])),
            "texts": len(responsive.get("Texts", [])),
            "images": len((responsive.get("AdImages") or {}).get("Items", [])),
            "callouts": len(responsive.get("AdExtensions", [])),
            "contacts": bool(responsive.get("BusinessId")),
        }
    )

print(json.dumps({"campaign_id": CAMPAIGN_ID, "groups": groups, "ads": result}, ensure_ascii=False))
