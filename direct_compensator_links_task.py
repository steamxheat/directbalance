#!/usr/bin/env python3
import json
import os
import urllib.request


API = "https://api.direct.yandex.com/json/v501"
CAMPAIGN_ID = 715995851
GROUP_ID = 5822089252
AD_ID = 1926541997268228793
LANDING = "https://korda-izol.ru/tkanevye-kompensatory/"
SITELINKS = [
    {"Title": "Типы компенсаторов", "Href": f"{LANDING}#production", "Description": "Фланцевые, хомутовые и ленточные"},
    {"Title": "Характеристики", "Href": f"{LANDING}#rec5703814401", "Description": "Температура, давление и рабочие смещения"},
    {"Title": "Опросный лист", "Href": f"{LANDING}#rec5711896301", "Description": "Данные для расчёта и подбора конструкции"},
    {"Title": "Контакты", "Href": f"{LANDING}#footer", "Description": "Заявка на расчёт и консультацию"},
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


def one_result(result, key):
    items = result[key]
    if len(items) != 1 or items[0].get("Errors") or not items[0].get("Id"):
        raise RuntimeError(items)
    return items[0]["Id"]


def ad():
    items = call(
        "ads",
        "get",
        {
            "SelectionCriteria": {"Ids": [AD_ID]},
            "FieldNames": ["Id", "CampaignId", "AdGroupId", "Type", "Status", "State"],
            "ResponsiveAdFieldNames": ["Href", "SitelinkSetId", "AdImages", "AdExtensions", "BusinessId", "Titles", "Texts"],
        },
    )["Ads"]
    if len(items) != 1:
        raise RuntimeError("Объявление не найдено")
    item = items[0]
    if item["CampaignId"] != CAMPAIGN_ID or item["AdGroupId"] != GROUP_ID or item["Type"] != "RESPONSIVE_AD":
        raise RuntimeError("Неверная кампания, группа или тип объявления")
    return item


def sitelinks(set_id):
    items = call(
        "sitelinks",
        "get",
        {
            "SelectionCriteria": {"Ids": [set_id]},
            "FieldNames": ["Id", "Sitelinks"],
        },
    )["SitelinksSets"]
    if len(items) != 1:
        raise RuntimeError("Набор быстрых ссылок не найден")
    return items[0]["Sitelinks"]


def summary(item):
    responsive = item["ResponsiveAd"]
    set_id = responsive.get("SitelinkSetId")
    return {
        "ad_id": item["Id"],
        "status": item["Status"],
        "state": item["State"],
        "href": responsive.get("Href"),
        "sitelink_set_id": set_id,
        "sitelinks": sitelinks(set_id) if set_id else [],
        "titles": len(responsive.get("Titles", [])),
        "texts": len(responsive.get("Texts", [])),
        "images": len((responsive.get("AdImages") or {}).get("Items", [])),
        "callouts": len(responsive.get("AdExtensions", [])),
        "contacts": bool(responsive.get("BusinessId")),
    }


def main():
    mode = os.environ.get("DIRECT_COMPENSATOR_MODE", "inspect")
    before = ad()
    if mode == "inspect":
        print(json.dumps({"mode": mode, "ad": summary(before)}, ensure_ascii=False))
        return
    if mode != "apply":
        raise RuntimeError("Неизвестный режим")
    set_id = one_result(call("sitelinks", "add", {"SitelinksSets": [{"Sitelinks": SITELINKS}]}), "AddResults")
    one_result(
        call("ads", "update", {"Ads": [{"Id": AD_ID, "ResponsiveAd": {"Href": LANDING, "SitelinkSetId": set_id}}]}),
        "UpdateResults",
    )
    after = ad()
    checked = summary(after)
    if checked["href"] != LANDING or checked["sitelinks"] != SITELINKS:
        raise RuntimeError("Ссылки не сохранились точно")
    if checked["titles"] != 7 or checked["texts"] != 3 or checked["images"] != 1 or checked["callouts"] != 4 or not checked["contacts"]:
        raise RuntimeError("При смене ссылок потерялись элементы объявления")
    print(json.dumps({"updated": True, "ad": checked}, ensure_ascii=False))


if __name__ == "__main__":
    main()
