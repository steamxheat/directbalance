#!/usr/bin/env python3
import json
import os
import urllib.error
import urllib.parse
import urllib.request


API = "https://api.direct.yandex.com/json/v501"
CAMPAIGN_ID = 715995851
AD_IDS = [
    1926541080294601959,
    1926541997268228793,
    1926542285033192900,
    1926543574597341768,
    1926543198787092320,
]
SITELINKS = [
    {"Title": "Продукция", "Href": "https://korda-izol.ru/#production", "Description": "Решения для изоляции промышленного оборудования"},
    {"Title": "Шумоизоляционные чехлы", "Href": "https://korda-izol.ru/shumoizolyacionnye-chehly/", "Description": "Снижение шума от промышленного оборудования"},
    {"Title": "Преимущества", "Href": "https://korda-izol.ru/#benefits", "Description": "Подбор решения под параметры вашего объекта"},
    {"Title": "Контакты", "Href": "https://korda-izol.ru/#footer", "Description": "Телефон и почта для расчёта и консультации"},
]
CALLOUTS = ["Изготовление по ТЗ", "Расчёт под задачу", "Для помещений и улицы", "Работаем по России"]


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
        raise RuntimeError(f"Direct API {error.get('error_code')}: {error.get('error_string')}: {error.get('error_detail')}")
    return payload["result"]


def ads():
    return call(
        "ads",
        "get",
        {
            "SelectionCriteria": {"Ids": AD_IDS},
            "FieldNames": ["Id", "CampaignId", "Type", "Status", "State"],
            "ResponsiveAdFieldNames": ["SitelinkSetId", "AdExtensions", "BusinessId", "Titles", "Texts", "Href"],
        },
    )["Ads"]


def businesses():
    return call(
        "businesses",
        "get",
        {
            "FieldNames": ["Id", "Name", "IsPublished", "Urls", "HasOffice"],
        },
    )["Businesses"]


def matching_business(items):
    for item in items:
        urls = (item.get("Urls") or {}).get("Items", [])
        if item.get("IsPublished") == "YES" and any("korda" in urllib.parse.urlsplit(url).hostname.lower() for url in urls if urllib.parse.urlsplit(url).hostname):
            return item
    return None


def action_ids(result, key):
    errors = [item["Errors"] for item in result[key] if item.get("Errors")]
    if errors:
        raise RuntimeError(f"Ошибки операции: {errors}")
    return [item["Id"] for item in result[key]]


def state():
    current = ads()
    if {ad["Id"] for ad in current} != set(AD_IDS) or any(ad["CampaignId"] != CAMPAIGN_ID for ad in current):
        raise RuntimeError("Набор объявлений кампании не совпал")
    business = matching_business(businesses())
    return current, business


def summary(current, business):
    return {
        "ads": len(current),
        "sitelinks_attached": sum(bool((ad.get("ResponsiveAd") or {}).get("SitelinkSetId")) for ad in current),
        "callouts_per_ad": [len((ad.get("ResponsiveAd") or {}).get("AdExtensions", [])) for ad in current],
        "contacts_attached": sum(bool((ad.get("ResponsiveAd") or {}).get("BusinessId")) for ad in current),
        "published_korda_business_found": bool(business),
        "published_korda_business_name": business.get("Name") if business else None,
        "statuses": sorted({ad["Status"] for ad in current}),
        "states": sorted({ad["State"] for ad in current}),
    }


def main():
    mode = os.environ.get("DIRECT_EXTENSIONS_MODE", "inspect")
    current, business = state()
    print(json.dumps({"mode": mode, "before": summary(current, business)}, ensure_ascii=False))
    if mode == "inspect":
        return
    if mode != "apply":
        raise RuntimeError("Неизвестный режим")

    sitelink_id = action_ids(call("sitelinks", "add", {"SitelinksSets": [{"Sitelinks": SITELINKS}]}), "AddResults")[0]
    callout_ids = action_ids(
        call("adextensions", "add", {"AdExtensions": [{"Callout": {"CalloutText": text}} for text in CALLOUTS]}),
        "AddResults",
    )
    responsive = {
        "SitelinkSetId": sitelink_id,
        "CalloutSetting": {"AdExtensions": [{"AdExtensionId": item_id, "Operation": "SET"} for item_id in callout_ids]},
    }
    if business:
        responsive["BusinessId"] = business["Id"]
    updates = [{"Id": ad_id, "ResponsiveAd": responsive} for ad_id in AD_IDS]
    action_ids(call("ads", "update", {"Ads": updates}), "UpdateResults")

    current, business = state()
    after = summary(current, business)
    if after["sitelinks_attached"] != len(AD_IDS) or after["callouts_per_ad"] != [len(CALLOUTS)] * len(AD_IDS):
        raise RuntimeError("Расширения сохранились не во всех объявлениях")
    if business and after["contacts_attached"] != len(AD_IDS):
        raise RuntimeError("Профиль организации сохранился не во всех объявлениях")
    print(json.dumps({"updated": True, "after": after}, ensure_ascii=False))


if __name__ == "__main__":
    main()
