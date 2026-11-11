#!/usr/bin/env python3
import json
import os
import urllib.request


API = "https://api.direct.yandex.com/json/v501"
CAMPAIGN_ID = 715995851
AD_IDS = [
    1926541080294601959,
    1926541997268228793,
    1926542285033192900,
    1926543574597341768,
    1926543198787092320,
    1926714010708993505,
]


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
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload["result"]


ads = call(
    "ads",
    "get",
    {
        "SelectionCriteria": {"Ids": AD_IDS},
        "FieldNames": ["Id", "CampaignId", "AdGroupId", "Status", "State"],
        "ResponsiveAdFieldNames": ["AdImages"],
    },
)["Ads"]
hashes = [
    image_hash
    for ad in ads
    for image_hash in (ad["ResponsiveAd"].get("AdImages") or {}).get("Items", [])
]
images = call(
    "adimages",
    "get",
    {
        "SelectionCriteria": {"AdImageHashes": hashes},
        "FieldNames": ["AdImageHash", "Name", "Associated", "Type", "Subtype", "OriginalUrl", "PreviewUrl"],
    },
)["AdImages"]
by_hash = {image["AdImageHash"]: image for image in images}
result = []
for ad in sorted(ads, key=lambda item: item["Id"]):
    ad_hashes = (ad["ResponsiveAd"].get("AdImages") or {}).get("Items", [])
    result.append({
        "ad_id": ad["Id"],
        "status": ad["Status"],
        "state": ad["State"],
        "images": [by_hash[image_hash] for image_hash in ad_hashes],
    })
if len(result) != 6 or len(hashes) != 6 or len(images) != 6:
    raise RuntimeError("Не найдены шесть объявлений с шестью изображениями")
print(json.dumps({"campaign_id": CAMPAIGN_ID, "ads": result}, ensure_ascii=False))
