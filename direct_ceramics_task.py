#!/usr/bin/env python3
import json
import os
import urllib.error
import urllib.request


API = "https://api.direct.yandex.com/json/v501"
CAMPAIGN_ID = 715995851
GROUP_NAME = "06_Керамические_изделия"
LANDING = "https://korda-izol.ru/keramicheskie-izdeliya/"
TITLES = [
    "Керамические изделия Корда для высоких температур",
    "Керамическая теплоизоляция для печей и оборудования",
    "Маты, шнуры, ленты, ткани и бумага Корда до 1425 °C",
    "Керамические маты Cerablanket и Cerachem со склада",
    "Керамические шнуры T-TEX для печей и тепловых агрегатов",
    "Ленты, бумага и ткани SUNTHERM для печей и оборудования",
    "Подберём керамический материал под вашу температуру",
]
TEXTS = [
    "Керамические маты, шнуры, ленты, бумага и ткани для печей и оборудования Корда.",
    "Материалы до 1425 °C. Все размеры, характеристики и цены указаны на сайте Корда.",
    "Оставьте заявку: подберём изделие по температуре, размерам и условиям площадки.",
]
KEYWORDS = [
    "керамические изделия",
    "керамическая теплоизоляция",
    "керамическое волокно",
    "керамические маты",
    "керамические шнуры",
    "керамическая лента",
    "керамическая бумага",
    "керамическая ткань",
]
SITELINKS = [
    {"Title": "Каталог изделий", "Href": f"{LANDING}#products", "Description": "Маты, шнуры, ленты, бумага и ткани"},
    {"Title": "Керамические маты", "Href": f"{LANDING}#cerablanket", "Description": "Маты Cerablanket и Cerachem до 1425 °C"},
    {"Title": "Шнуры T-TEX", "Href": f"{LANDING}#keram_shnur", "Description": "Круглые и квадратные керамические шнуры"},
    {"Title": "Контакты", "Href": f"{LANDING}#footer", "Description": "Заявка на подбор материала и консультацию"},
]
CALLOUTS = ["Материалы со склада", "До 1425 °C", "Цены на сайте", "Подбор по температуре"]


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


def result_ids(result, key):
    errors = [item["Errors"] for item in result[key] if item.get("Errors")]
    if errors:
        raise RuntimeError(f"Ошибки операции: {errors}")
    return [item["Id"] for item in result[key]]


def campaign():
    items = call(
        "campaigns",
        "get",
        {"SelectionCriteria": {"Ids": [CAMPAIGN_ID]}, "FieldNames": ["Id", "Name", "Type", "Status", "State", "StatusPayment"]},
    )["Campaigns"]
    if len(items) != 1:
        raise RuntimeError("Кампания не найдена")
    return items[0]


def groups():
    return call(
        "adgroups",
        "get",
        {"SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]}, "FieldNames": ["Id", "Name", "CampaignId", "Status", "Type", "RegionIds"]},
    )["AdGroups"]


def ads(group_ids):
    if not group_ids:
        return []
    return call(
        "ads",
        "get",
        {
            "SelectionCriteria": {"AdGroupIds": group_ids},
            "FieldNames": ["Id", "CampaignId", "AdGroupId", "Type", "Status", "State"],
            "ResponsiveAdFieldNames": ["Titles", "Texts", "Href", "SitelinkSetId", "AdExtensions", "BusinessId"],
        },
    ).get("Ads", [])


def keywords(group_ids):
    if not group_ids:
        return []
    return call(
        "keywords",
        "get",
        {
            "SelectionCriteria": {"AdGroupIds": group_ids},
            "FieldNames": ["Id", "AdGroupId", "Keyword", "Status", "State", "StrategyPriority"],
        },
    ).get("Keywords", [])


def one_group():
    found = [group for group in groups() if group["Name"] == GROUP_NAME]
    if len(found) > 1:
        raise RuntimeError("Найдено несколько групп с целевым названием")
    return found[0] if found else None


def verify(group, group_ads, group_keywords):
    if group["CampaignId"] != CAMPAIGN_ID or group["Type"] != "UNIFIED_AD_GROUP":
        raise RuntimeError("Новая группа создана не в той кампании или имеет неверный тип")
    if len(group_ads) != 1:
        raise RuntimeError("В новой группе должно быть ровно одно объявление")
    responsive = group_ads[0].get("ResponsiveAd") or {}
    if [item["Title"] for item in responsive.get("Titles", [])] != TITLES:
        raise RuntimeError("Заголовки объявления не совпали")
    if [item["Text"] for item in responsive.get("Texts", [])] != TEXTS:
        raise RuntimeError("Тексты объявления не совпали")
    if responsive.get("Href") != LANDING:
        raise RuntimeError("Неверная посадочная ссылка")
    if not responsive.get("SitelinkSetId") or len(responsive.get("AdExtensions", [])) != 4:
        raise RuntimeError("Не сохранились быстрые ссылки или уточнения")
    if not responsive.get("BusinessId"):
        raise RuntimeError("Не сохранились контакты организации")
    actual_keywords = {item["Keyword"] for item in group_keywords}
    if not set(KEYWORDS).issubset(actual_keywords):
        raise RuntimeError("Сохранились не все ключевые фразы")
    return {
        "group_id": group["Id"],
        "group_status": group["Status"],
        "ad_id": group_ads[0]["Id"],
        "ad_status": group_ads[0]["Status"],
        "ad_state": group_ads[0]["State"],
        "landing": responsive["Href"],
        "titles": len(responsive["Titles"]),
        "title_lengths": [len(item["Title"]) for item in responsive["Titles"]],
        "texts": len(responsive["Texts"]),
        "text_lengths": [len(item["Text"]) for item in responsive["Texts"]],
        "keywords": len([item for item in group_keywords if item["Keyword"] != "---autotargeting"]),
        "autotargeting": any(item["Keyword"] == "---autotargeting" for item in group_keywords),
        "sitelinks": bool(responsive["SitelinkSetId"]),
        "callouts": len(responsive["AdExtensions"]),
        "contacts": bool(responsive["BusinessId"]),
    }


def main():
    mode = os.environ.get("DIRECT_CERAMICS_MODE", "inspect")
    if len(TITLES) != 7 or len(TEXTS) != 3 or max(map(len, TITLES)) > 56 or max(map(len, TEXTS)) > 81:
        raise RuntimeError("Тексты не соответствуют лимитам")
    current_campaign = campaign()
    group = one_group()
    if mode == "inspect":
        result = {"mode": mode, "campaign": current_campaign, "group_exists": bool(group)}
        if group:
            result["group"] = verify(group, ads([group["Id"]]), keywords([group["Id"]]))
        print(json.dumps(result, ensure_ascii=False))
        return
    if mode != "apply":
        raise RuntimeError("Неизвестный режим")

    if not group:
        group_id = result_ids(
            call("adgroups", "add", {"AdGroups": [{"Name": GROUP_NAME, "CampaignId": CAMPAIGN_ID, "RegionIds": [225, 977]}]}),
            "AddResults",
        )[0]
        group = one_group()
        if not group or group["Id"] != group_id:
            raise RuntimeError("Новая группа не найдена после создания")

    group_id = group["Id"]
    existing_keywords = {item["Keyword"] for item in keywords([group_id])}
    missing_keywords = [keyword for keyword in KEYWORDS if keyword not in existing_keywords]
    if missing_keywords:
        result_ids(
            call("keywords", "add", {"Keywords": [{"Keyword": keyword, "AdGroupId": group_id} for keyword in missing_keywords]}),
            "AddResults",
        )

    group_ads = ads([group_id])
    if not group_ads:
        template = ads([5822082395])[0]["ResponsiveAd"]
        sitelink_id = result_ids(call("sitelinks", "add", {"SitelinksSets": [{"Sitelinks": SITELINKS}]}), "AddResults")[0]
        callout_ids = result_ids(
            call("adextensions", "add", {"AdExtensions": [{"Callout": {"CalloutText": item}} for item in CALLOUTS]}),
            "AddResults",
        )
        ad_id = result_ids(
            call(
                "ads",
                "add",
                {
                    "Ads": [{
                        "AdGroupId": group_id,
                        "ResponsiveAd": {
                            "Titles": TITLES,
                            "Texts": TEXTS,
                            "Href": LANDING,
                            "SitelinkSetId": sitelink_id,
                            "CalloutSetting": {"AdExtensions": [{"AdExtensionId": item_id, "Operation": "SET"} for item_id in callout_ids]},
                            "BusinessId": template["BusinessId"],
                        },
                    }]
                },
            ),
            "AddResults",
        )[0]
        result_ids(call("ads", "moderate", {"SelectionCriteria": {"Ids": [ad_id]}}), "ModerateResults")
    elif len(group_ads) > 1:
        raise RuntimeError("В новой группе уже несколько объявлений")

    group = one_group()
    final = verify(group, ads([group["Id"]]), keywords([group["Id"]]))
    print(json.dumps({"updated": True, "campaign": campaign(), "group": final}, ensure_ascii=False))


if __name__ == "__main__":
    main()
