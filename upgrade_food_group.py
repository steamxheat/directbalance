#!/usr/bin/env python3
import base64
import json
import os
import urllib.request


API = "https://api.direct.yandex.com/json/v501"
CAMPAIGN_ID = 706863240
GROUP_ID = 5826331360
LANDING = "https://xn--80aeb4aacrhcscincn.xn--p1ai/pishchchekhly/"
IMAGE_PATH = "assets/food-thermal-covers-ad-square.jpg"
TITLES = [
    "Пищевые термочехлы от производителя",
    "Термочехлы для продуктов и логистики",
    "Чехлы для паллет, тележек и контейнеров",
    "Термочехлы по размерам заказчика",
    "Сохранение температуры при перевозке",
    "Производство пищевых термочехлов",
    "Получите расчёт термочехла под задачу",
]
TEXTS = [
    "Для европаллет, расстойки, шпилек и ролл-контейнеров. Изготовим под заказ.",
    "Собственное производство, гарантия 12 месяцев и доставка по России и СНГ.",
    "Защита температурно-чувствительных продуктов при хранении и перевозке.",
]
CALLOUTS = [
    "Собственное производство",
    "Гарантия 12 месяцев",
    "Доставка по РФ и СНГ",
    "Изготовление по размерам",
]
TRACKING = (
    "?utm_source=yandex&utm_medium=cpc&utm_campaign={campaign_name}_{campaign_id}_{source_type}"
    "&utm_content={gbid}_{ad_id}&utm_term={keyword}&block={position_type}"
    "&position={position}&region={region_name}&type={source_type}&source={source}"
    "&utm_id=yadirect_{campaign_name}_{campaign_id}"
)
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
    if payload.get("error"):
        raise RuntimeError(json.dumps(payload["error"], ensure_ascii=False))
    return payload["result"]


def ids(result, key):
    errors = [item["Errors"] for item in result[key] if item.get("Errors")]
    if errors:
        raise RuntimeError(json.dumps(errors, ensure_ascii=False))
    return [item.get("Id") or item.get("AdImageHash") for item in result[key]]


def campaign():
    return call("campaigns", "get", {
        "SelectionCriteria": {"Ids": [CAMPAIGN_ID]},
        "FieldNames": ["Id", "Name", "Status", "State", "StatusPayment"],
    })["Campaigns"][0]


def group():
    return call("adgroups", "get", {
        "SelectionCriteria": {"Ids": [GROUP_ID]},
        "FieldNames": ["Id", "Name", "CampaignId", "Status", "ServingStatus", "Type"],
    })["AdGroups"][0]


def ads(group_ids=None):
    criteria = {"AdGroupIds": group_ids or [GROUP_ID]}
    return call("ads", "get", {
        "SelectionCriteria": criteria,
        "FieldNames": ["Id", "AdGroupId", "Type", "Status", "State", "StatusClarification"],
        "TextAdFieldNames": ["Title", "Title2", "Text", "Href", "SitelinkSetId", "AdExtensions", "BusinessId", "AdImageHash"],
        "ResponsiveAdFieldNames": ["Titles", "Texts", "Href", "SitelinkSetId", "AdExtensions", "BusinessId", "AdImages"],
    }).get("Ads", [])


def keywords(group_ids=None):
    return call("keywords", "get", {
        "SelectionCriteria": {"AdGroupIds": group_ids or [GROUP_ID]},
        "FieldNames": ["Id", "AdGroupId", "Keyword", "Status", "State", "ServingStatus"],
        "AutotargetingSettingsCategoriesFieldNames": ["Exact", "Narrow", "Alternative", "Accessory", "Broader"],
        "AutotargetingSettingsBrandOptionsFieldNames": ["WithoutBrands", "WithAdvertiserBrand", "WithCompetitorsBrand"],
    })["Keywords"]


def responsive_ads():
    return [item for item in ads() if item["Type"] == "RESPONSIVE_AD"]


def verify():
    current_campaign = campaign()
    current_group = group()
    current_ads = ads()
    current_keywords = keywords()
    responsive = responsive_ads()
    old_group_ids = [5709693724, 5709693725, 5709693726, 5709693727, 5709693728]
    old_ads = ads(old_group_ids)
    old_keywords = keywords(old_group_ids)
    regular_old_keywords = [item for item in old_keywords if item["Keyword"] != "---autotargeting"]
    summary = {
        "campaign": current_campaign,
        "group": current_group,
        "responsive_ads": [],
        "keywords": {
            "regular": sum(item["Keyword"] != "---autotargeting" for item in current_keywords),
            "regular_on": sum(item["Keyword"] != "---autotargeting" and item["State"] == "ON" for item in current_keywords),
            "autotarget": [item for item in current_keywords if item["Keyword"] == "---autotargeting"],
        },
        "old_groups": {
            "ads_total": len(old_ads),
            "ads_suspended": sum(item["State"] == "SUSPENDED" for item in old_ads),
            "keywords_total": len(regular_old_keywords),
            "keywords_suspended": sum(item["State"] == "SUSPENDED" for item in regular_old_keywords),
        },
    }
    for item in responsive:
        ad = item["ResponsiveAd"]
        summary["responsive_ads"].append({
            "id": item["Id"],
            "status": item["Status"],
            "state": item["State"],
            "clarification": item.get("StatusClarification"),
            "titles": [part["Title"] for part in ad.get("Titles", [])],
            "texts": [part["Text"] for part in ad.get("Texts", [])],
            "href": ad.get("Href"),
            "images": (ad.get("AdImages") or {}).get("Items", []),
            "sitelinks": bool(ad.get("SitelinkSetId")),
            "callouts": len(ad.get("AdExtensions") or []),
            "business": bool(ad.get("BusinessId")),
        })
    return summary


def validate():
    assert len(TITLES) == 7 and len(TEXTS) == 3 and len(CALLOUTS) == 4
    assert max(map(len, TITLES)) <= 56
    assert max(map(len, TEXTS)) <= 81
    assert max(map(len, CALLOUTS)) <= 25
    assert os.path.getsize(IMAGE_PATH) < 10 * 1024 * 1024


def main():
    validate()
    mode = os.environ.get("FOOD_UPGRADE_MODE", "inspect")
    before = verify()
    if mode == "inspect":
        print(json.dumps({"mode": mode, "summary": before}, ensure_ascii=False, indent=2))
        return
    if mode != "apply":
        raise RuntimeError("Unknown mode")
    if before["campaign"]["State"] != "ON" or before["group"]["ServingStatus"] != "ELIGIBLE":
        raise RuntimeError("Campaign or target group is not ready")
    if before["old_groups"] != {"ads_total": 30, "ads_suspended": 30, "keywords_total": 102, "keywords_suspended": 102}:
        raise RuntimeError("Old groups are not fully isolated")

    existing = responsive_ads()
    full = [item for item in existing
            if [part["Title"] for part in item["ResponsiveAd"].get("Titles", [])] == TITLES
            and [part["Text"] for part in item["ResponsiveAd"].get("Texts", [])] == TEXTS]
    if not full:
        if len(existing) != 3:
            raise RuntimeError("Expected three existing responsive ads")
        target = min(existing, key=lambda item: item["Id"])
        base = target["ResponsiveAd"]
        sitelink_id = base.get("SitelinkSetId")
        business_id = base.get("BusinessId")
        if not sitelink_id or not business_id:
            raise RuntimeError("Missing sitelinks or business profile")
        callout_ids = ids(call("adextensions", "add", {
            "AdExtensions": [{"Callout": {"CalloutText": text}} for text in CALLOUTS],
        }), "AddResults")
        with open(IMAGE_PATH, "rb") as source:
            image_data = base64.b64encode(source.read()).decode()
        image_hash = ids(call("adimages", "add", {"AdImages": [{
            "Name": "Пищевые термочехлы — производство и логистика",
            "ImageData": image_data,
            "Type": "REGULAR",
        }]}), "AddResults")[0]
        ad_id = target["Id"]
        ids(call("ads", "update", {"Ads": [{
            "Id": ad_id,
            "ResponsiveAd": {
                "Titles": TITLES,
                "Texts": TEXTS,
                "Href": LANDING + TRACKING,
                "SitelinkSetId": sitelink_id,
                "BusinessId": business_id,
                "AdImageHashes": {"Items": [image_hash]},
                "CalloutSetting": {"AdExtensions": [
                    {"AdExtensionId": item, "Operation": "SET"} for item in callout_ids
                ]},
            },
        }]}), "UpdateResults")
        ids(call("ads", "moderate", {"SelectionCriteria": {"Ids": [ad_id]}}), "ModerateResults")

    after = verify()
    if len(after["responsive_ads"]) != 3:
        raise RuntimeError("Unexpected number of responsive ads")
    matching = [item for item in after["responsive_ads"]
                if item["titles"] == TITLES and item["texts"] == TEXTS]
    if len(matching) != 1:
        raise RuntimeError("Full responsive ad was not created")
    responsive = matching[0]
    assert responsive["titles"] == TITLES
    assert responsive["texts"] == TEXTS
    assert len(responsive["images"]) == 1
    assert responsive["sitelinks"] and responsive["callouts"] == 4 and responsive["business"]
    assert after["keywords"]["regular"] == 12 and after["keywords"]["regular_on"] == 12
    assert after["old_groups"] == before["old_groups"]
    print(json.dumps({"mode": mode, "summary": after}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
