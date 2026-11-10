#!/usr/bin/env python3
import json
import os
import urllib.error
import urllib.parse
import urllib.request


API = "https://api.direct.yandex.com/json/v501"


def call(service, method, params):
    request = urllib.request.Request(
        f"{API}/{service}",
        data=json.dumps({"method": method, "params": params}).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['YANDEX_DIRECT_TOKEN']}",
            "Client-Login": os.environ["YANDEX_DIRECT_LOGIN"],
            "Accept-Language": "ru",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Direct API HTTP {error.code}") from error
    if "error" in result:
        error = result["error"]
        raise RuntimeError(f"Direct API {error.get('error_code')}: {error.get('error_string')}")
    return result["result"]


def get_state(task):
    campaign = call(
        "campaigns",
        "get",
        {
            "SelectionCriteria": {"Ids": [task["campaign_id"]]},
            "FieldNames": ["Id", "Name", "Type", "Status", "State", "StatusPayment"],
        },
    )["Campaigns"]
    ads = call(
        "ads",
        "get",
        {
            "SelectionCriteria": {"Ids": task["ad_ids"]},
            "FieldNames": ["Id", "CampaignId", "AdGroupId", "Type", "Status", "State"],
            "ResponsiveAdFieldNames": ["Titles", "Texts", "Href"],
        },
    )["Ads"]
    if len(campaign) != 1 or campaign[0]["Id"] != task["campaign_id"]:
        raise RuntimeError("Кампания не найдена")
    if {ad["Id"] for ad in ads} != set(task["ad_ids"]):
        raise RuntimeError("Набор объявлений не совпал")
    expected_urls = {ad_id: task["home"] for ad_id in task["ad_ids"]}
    expected_urls[task["profile_ad_id"]] = task["profile"]
    mismatches = []
    for index, ad in enumerate(ads, 1):
        responsive = ad.get("ResponsiveAd") or {}
        if ad["CampaignId"] != task["campaign_id"] or ad["Type"] != "RESPONSIVE_AD":
            raise RuntimeError("Неверный тип или кампания объявления")
        if len(responsive.get("Titles", [])) != 7 or len(responsive.get("Texts", [])) != 3:
            raise RuntimeError("Не заполнены 7 заголовков и 3 текста")
        actual = urllib.parse.urlsplit(responsive.get("Href", ""))
        expected = urllib.parse.urlsplit(expected_urls[ad["Id"]])
        if (actual.hostname, actual.path.rstrip("/")) != (expected.hostname, expected.path.rstrip("/")):
            mismatches.append({"ad": index, "actual": f"{actual.hostname}{actual.path}"})
    if mismatches:
        raise RuntimeError(f"Неверные посадочные ссылки: {json.dumps(mismatches, ensure_ascii=False)}")
    return campaign[0], ads


def texts(ad):
    responsive = ad["ResponsiveAd"]
    return [item["Title"] for item in responsive["Titles"]], [item["Text"] for item in responsive["Texts"]]


def action_errors(result, key):
    return [item["Errors"] for item in result[key] if item.get("Errors")]


def main():
    task = json.loads(os.environ["DIRECT_TASK_JSON"])
    campaign, ads = get_state(task)
    uppercase_count = sum(value.count("КОРДА") for ad in ads for value in sum(texts(ad), []))
    print(
        json.dumps(
            {
                "mode": task["mode"],
                "campaign_type": campaign["Type"],
                "campaign_status": campaign["Status"],
                "campaign_state": campaign["State"],
                "payment_status": campaign["StatusPayment"],
                "ads": len(ads),
                "all_ads_complete": True,
                "landing_urls_ok": True,
                "uppercase_brand_occurrences": uppercase_count,
                "name_matches": campaign["Name"] == task["name"],
            },
            ensure_ascii=False,
        )
    )
    if task["mode"] == "inspect":
        return
    if task["mode"] != "apply":
        raise RuntimeError("Неизвестный режим")

    updates = []
    for ad in ads:
        titles, ad_texts = texts(ad)
        updates.append(
            {
                "Id": ad["Id"],
                "ResponsiveAd": {
                    "Titles": [value.replace("КОРДА", "Корда") for value in titles],
                    "Texts": [value.replace("КОРДА", "Корда") for value in ad_texts],
                },
            }
        )
    errors = action_errors(call("ads", "update", {"Ads": updates}), "UpdateResults")
    errors += action_errors(
        call("campaigns", "update", {"Campaigns": [{"Id": task["campaign_id"], "Name": task["name"]}]}),
        "UpdateResults",
    )
    if errors:
        raise RuntimeError(f"Ошибки обновления: {len(errors)}")

    campaign, ads = get_state(task)
    if campaign["Name"] != task["name"] or any("КОРДА" in value for ad in ads for value in sum(texts(ad), [])):
        raise RuntimeError("Проверка после обновления не пройдена")

    draft_ids = [ad["Id"] for ad in ads if ad["Status"] == "DRAFT"]
    if draft_ids:
        moderate = call("ads", "moderate", {"SelectionCriteria": {"Ids": draft_ids}})
        if action_errors(moderate, "ModerateResults"):
            raise RuntimeError("Не удалось отправить объявления на модерацию")
    if campaign["State"] == "SUSPENDED":
        resumed = call("campaigns", "resume", {"SelectionCriteria": {"Ids": [task["campaign_id"]]}})
        if action_errors(resumed, "ResumeResults"):
            raise RuntimeError("Не удалось возобновить кампанию")
    print(json.dumps({"updated": True, "moderation_sent": len(draft_ids), "resumed": campaign["State"] == "SUSPENDED"}))


if __name__ == "__main__":
    main()
