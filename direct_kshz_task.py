#!/usr/bin/env python3
import base64
import io
import json
import os
import urllib.request

from PIL import Image


API = "https://api.direct.yandex.com/json/v501"
CAMPAIGN_ID = 715995851
GROUP_NAME = "07_КШЗ_комплектные_кожухи"
LANDING = "https://korda-izol.ru/shumozaschitnye-resheniya/"
IMAGE_URL = "https://static.tildacdn.com/tila3534-3433-4930-a461-373730323037/kshz-remont.png"
TITLES = [
    "КШЗ Корда для промышленного оборудования под ключ",
    "Комплектные шумозащитные кожухи по вашим размерам",
    "КШЗ для компрессоров, генераторов и станков",
    "Проектирование и производство КШЗ по ТЗ",
    "Снижение шума на 20–40 дБ с решениями Корда",
    "КШЗ с вентиляцией и доступом для обслуживания",
    "Закажите расчёт КШЗ для вашего оборудования",
]
TEXTS = [
    "Проектируем и производим КШЗ под размеры, шум и условия вашего оборудования.",
    "Учтём вентиляцию, доступ для ремонта и снижение шума на 20–40 дБ.",
    "От замера и расчёта до производства, монтажа и контрольных измерений.",
]
KEYWORDS = [
    "кшз",
    "кшз для оборудования",
    "изготовление кшз",
    "производство кшз",
    "заказать кшз",
    "кшз для компрессора",
    "кшз для генератора",
    "кшз для станка",
]
SITELINKS = [
    {"Title": "Типы решений", "Href": f"{LANDING}#rec5768942101", "Description": "Кабины, кожухи и встроенные конструкции"},
    {"Title": "Преимущества", "Href": f"{LANDING}#rec5771671001", "Description": "Проектирование, производство и монтаж под ключ"},
    {"Title": "Параметры", "Href": f"{LANDING}#rec5783524601", "Description": "Снижение шума, материалы и условия применения"},
    {"Title": "Контакты", "Href": f"{LANDING}#footer", "Description": "Заявка на расчёт КШЗ по параметрам оборудования"},
]
CALLOUTS = ["Снижение шума до 40 дБ", "Изготовление по ТЗ", "Вентиляция и доступ", "Замеры до и после"]
AUTOTARGET = {"Exact": "YES", "Narrow": "NO", "Alternative": "NO", "Accessory": "NO", "Broader": "NO"}
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


def ids(result, key):
    errors = [item["Errors"] for item in result[key] if item.get("Errors")]
    if errors:
        raise RuntimeError(errors)
    return [item["Id"] for item in result[key]]


def campaign():
    items = call("campaigns", "get", {
        "SelectionCriteria": {"Ids": [CAMPAIGN_ID]},
        "FieldNames": ["Id", "Name", "Type", "Status", "State", "StatusPayment"],
        "UnifiedCampaignFieldNames": ["CounterIds", "PriorityGoals", "BiddingStrategy", "Settings"],
    })["Campaigns"]
    assert len(items) == 1
    return items[0]


def groups():
    return call("adgroups", "get", {
        "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
        "FieldNames": ["Id", "Name", "CampaignId", "Status", "ServingStatus", "Type", "RegionIds"],
    })["AdGroups"]


def target_group():
    found = [item for item in groups() if item["Name"] == GROUP_NAME]
    if len(found) > 1:
        raise RuntimeError("Найдено несколько целевых групп")
    return found[0] if found else None


def group_ads(group_id):
    return call("ads", "get", {
        "SelectionCriteria": {"AdGroupIds": [group_id]},
        "FieldNames": ["Id", "CampaignId", "AdGroupId", "Type", "Status", "State", "StatusClarification"],
        "ResponsiveAdFieldNames": ["Titles", "Texts", "Href", "SitelinkSetId", "AdExtensions", "BusinessId", "AdImages"],
    }).get("Ads", [])


def group_keywords(group_id):
    return call("keywords", "get", {
        "SelectionCriteria": {"AdGroupIds": [group_id]},
        "FieldNames": ["Id", "AdGroupId", "Keyword", "Status", "State", "ServingStatus", "StrategyPriority"],
        "AutotargetingSettingsCategoriesFieldNames": list(AUTOTARGET),
    })["Keywords"]


def business_id():
    ads = group_ads(5822095864)
    assert len(ads) == 1
    value = ads[0]["ResponsiveAd"].get("BusinessId")
    if not value:
        raise RuntimeError("Не найден контактный профиль Корда")
    return value


def image_data():
    request = urllib.request.Request(IMAGE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        source = response.read()
    with Image.open(io.BytesIO(source)) as image:
        image = image.convert("RGBA")
        background = Image.new("RGBA", image.size, "white")
        image = Image.alpha_composite(background, image).convert("RGB")
        width, height = image.size
        side = min(width, height)
        left, top = (width - side) // 2, (height - side) // 2
        image = image.crop((left, top, left + side, top + side))
        output = io.BytesIO()
        image.save(output, "JPEG", quality=90, optimize=True)
    return base64.b64encode(output.getvalue()).decode()


def verify(group):
    ads = group_ads(group["Id"])
    keywords = group_keywords(group["Id"])
    if group["CampaignId"] != CAMPAIGN_ID or group["Type"] != "UNIFIED_AD_GROUP":
        raise RuntimeError("Группа создана не в той кампании")
    if len(ads) != 1:
        raise RuntimeError("В группе должно быть одно объявление")
    ad = ads[0]
    responsive = ad["ResponsiveAd"]
    assert [item["Title"] for item in responsive["Titles"]] == TITLES
    assert [item["Text"] for item in responsive["Texts"]] == TEXTS
    assert responsive["Href"] == LANDING
    assert responsive.get("SitelinkSetId")
    assert len(responsive.get("AdExtensions", [])) == len(CALLOUTS)
    assert responsive.get("BusinessId")
    images = (responsive.get("AdImages") or {}).get("Items", [])
    assert len(images) == 1
    actual = {item["Keyword"] for item in keywords if item["Keyword"] != "---autotargeting"}
    assert actual == set(KEYWORDS)
    autotarget = [item for item in keywords if item["Keyword"] == "---autotargeting"]
    assert len(autotarget) == 1 and autotarget[0]["AutotargetingSettings"]["Categories"] == AUTOTARGET
    return {
        "group_id": group["Id"],
        "group_status": group["Status"],
        "serving": group.get("ServingStatus"),
        "ad_id": ad["Id"],
        "ad_status": ad["Status"],
        "ad_state": ad["State"],
        "landing": responsive["Href"],
        "titles": len(TITLES),
        "title_lengths": list(map(len, TITLES)),
        "texts": len(TEXTS),
        "text_lengths": list(map(len, TEXTS)),
        "keywords": len(actual),
        "autotarget": AUTOTARGET,
        "images": len(images),
        "image_status": images[0].get("Status"),
        "sitelinks": 4,
        "callouts": len(responsive["AdExtensions"]),
        "contacts": bool(responsive.get("BusinessId")),
    }


def main():
    mode = os.environ.get("DIRECT_KSHZ_MODE", "inspect")
    if len(TITLES) != 7 or len(TEXTS) != 3 or max(map(len, TITLES)) > 56 or max(map(len, TEXTS)) > 81:
        raise RuntimeError("Тексты не соответствуют лимитам")
    if max(map(len, CALLOUTS)) > 25:
        raise RuntimeError("Уточнение длиннее 25 символов")
    before = campaign()
    assert before["Name"] == "Корда — Изомакс — Тильда"
    assert before["Status"] == "ACCEPTED" and before["State"] == "ON" and before["StatusPayment"] == "ALLOWED"
    group = target_group()
    if mode == "inspect":
        print(json.dumps({"mode": mode, "campaign": before, "group_exists": bool(group), "group": verify(group) if group else None}, ensure_ascii=False))
        return
    if mode != "apply":
        raise RuntimeError("Неизвестный режим")

    if not group:
        group_id = ids(call("adgroups", "add", {"AdGroups": [{
            "Name": GROUP_NAME,
            "CampaignId": CAMPAIGN_ID,
            "RegionIds": [225, 977],
        }]}), "AddResults")[0]
        group = target_group()
        assert group and group["Id"] == group_id

    existing = {item["Keyword"] for item in group_keywords(group["Id"])}
    missing = [item for item in KEYWORDS if item not in existing]
    if missing:
        ids(call("keywords", "add", {"Keywords": [{"Keyword": item, "AdGroupId": group["Id"]} for item in missing]}), "AddResults")

    keywords = group_keywords(group["Id"])
    autotarget = [item for item in keywords if item["Keyword"] == "---autotargeting"]
    assert len(autotarget) == 1
    result = call("keywords", "update", {"Keywords": [{
        "Id": autotarget[0]["Id"],
        "AutotargetingSettings": {"Categories": AUTOTARGET},
    }]})["UpdateResults"]
    assert len(result) == 1 and result[0].get("Id") == autotarget[0]["Id"] and not result[0].get("Errors")

    ads = group_ads(group["Id"])
    if not ads:
        sitelink_id = ids(call("sitelinks", "add", {"SitelinksSets": [{"Sitelinks": SITELINKS}]}), "AddResults")[0]
        callout_ids = ids(call("adextensions", "add", {"AdExtensions": [{"Callout": {"CalloutText": item}} for item in CALLOUTS]}), "AddResults")
        image_result = call("adimages", "add", {"AdImages": [{
            "Name": GROUP_NAME,
            "ImageData": image_data(),
            "Type": "REGULAR",
        }]})["AddResults"]
        if len(image_result) != 1 or image_result[0].get("Errors") or not image_result[0].get("AdImageHash"):
            raise RuntimeError(image_result)
        image_hash = image_result[0]["AdImageHash"]
        ad_id = ids(call("ads", "add", {"Ads": [{
            "AdGroupId": group["Id"],
            "ResponsiveAd": {
                "Titles": TITLES,
                "Texts": TEXTS,
                "Href": LANDING,
                "SitelinkSetId": sitelink_id,
                "BusinessId": business_id(),
            },
        }]}), "AddResults")[0]
        ids(call("ads", "update", {"Ads": [{"Id": ad_id, "ResponsiveAd": {
            "AdImageHashes": {"Items": [image_hash]},
            "CalloutSetting": {"AdExtensions": [{"AdExtensionId": item, "Operation": "SET"} for item in callout_ids]},
        }}]}), "UpdateResults")
        ids(call("ads", "moderate", {"SelectionCriteria": {"Ids": [ad_id]}}), "ModerateResults")
    elif len(ads) != 1:
        raise RuntimeError("В целевой группе уже несколько объявлений")

    final_group = target_group()
    checked = verify(final_group)
    after = campaign()
    assert after == before
    print(json.dumps({"updated": True, "campaign": after, "group": checked}, ensure_ascii=False))


if __name__ == "__main__":
    main()
