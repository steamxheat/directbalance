#!/usr/bin/env python3
import json
import os
import urllib.request


API = "https://api.direct.yandex.com/json/v501"
CAMPAIGN_ID = 715995851
GLAV = "https://xn--80aeb4aacrhcscincn.xn--p1ai"
UPDATES = {
    1926541080294601959: {
        "href": "https://korda.su/about.html",
        "sitelinks": [
            {"Title": "Направления", "Href": "https://korda.su/about.html#directions", "Description": "Компетенции и профильные сайты группы"},
            {"Title": "Каталог решений", "Href": "https://korda.su/catalog-solutions.html", "Description": "Электрообогрев для промышленности и быта"},
            {"Title": "Опросные листы", "Href": "https://korda.su/questionnaires.html", "Description": "Исходные данные для инженерного расчёта"},
            {"Title": "Контакты", "Href": "https://korda.su/about.html#contacts", "Description": "Телефон, почта и адрес компании"},
        ],
    },
    1926541997268228793: {
        "href": "https://k-pensator.ru/",
        "sitelinks": [
            {"Title": "Продукция", "Href": "https://k-pensator.ru/products/", "Description": "Типы и исполнения тканевых компенсаторов"},
            {"Title": "Подбор и расчёт", "Href": "https://k-pensator.ru/montage/podbor-i-raschet/", "Description": "Расчёт конструкции под параметры узла"},
            {"Title": "Опросный лист", "Href": "https://k-pensator.ru/questionnaire/", "Description": "Данные для подготовки расчёта и предложения"},
            {"Title": "Контакты", "Href": "https://k-pensator.ru/contacts/", "Description": "Отправить чертёж, фото или техническое задание"},
        ],
    },
    1926542285033192900: {
        "href": "https://isomax.ru/shumoizolyatsionnye-chehly/",
        "sitelinks": [
            {"Title": "Съёмная изоляция", "Href": "https://isomax.ru/production/", "Description": "Решения для промышленного оборудования"},
            {"Title": "Акустические конструкции", "Href": "https://isomax.ru/acoustic-constructions/", "Description": "Кабины, кожухи и экраны для оборудования"},
            {"Title": "Реализованные проекты", "Href": "https://isomax.ru/projects/equipment-projects/", "Description": "Примеры решений для промышленного оборудования"},
            {"Title": "Контакты", "Href": "https://isomax.ru/korda/contacts/", "Description": "Заявка на расчёт и консультацию"},
        ],
    },
    1926543574597341768: {
        "href": f"{GLAV}/shumozashitnye-cabiny-i-kozhuhi/cabins/",
        "sitelinks": [
            {"Title": "Все решения", "Href": f"{GLAV}/shumozashitnye-cabiny-i-kozhuhi/", "Description": "Кабины, кожухи и комплектные системы"},
            {"Title": "Акустические кожухи", "Href": f"{GLAV}/shumozashitnye-cabiny-i-kozhuhi/promyshlennye-akusticheskie-kozhuhi/", "Description": "Кожухи для промышленного оборудования"},
            {"Title": "КШЗ", "Href": f"{GLAV}/shumozashitnye-cabiny-i-kozhuhi/kshz/", "Description": "Комплектные шумозащитные системы"},
            {"Title": "Опросный лист", "Href": f"{GLAV}/oprosny-list/", "Description": "Исходные данные для расчёта конструкции"},
        ],
    },
    1926543198787092320: {
        "href": f"{GLAV}/shumozashitnye-cabiny-i-kozhuhi/promyshlennye-akusticheskie-kozhuhi/",
        "sitelinks": [
            {"Title": "Все решения", "Href": f"{GLAV}/shumozashitnye-cabiny-i-kozhuhi/", "Description": "Кабины, кожухи и комплектные системы"},
            {"Title": "Шумозащитные кабины", "Href": f"{GLAV}/shumozashitnye-cabiny-i-kozhuhi/cabins/", "Description": "Кабины для промышленного оборудования"},
            {"Title": "КШЗ", "Href": f"{GLAV}/shumozashitnye-cabiny-i-kozhuhi/kshz/", "Description": "Комплектные шумозащитные системы"},
            {"Title": "Опросный лист", "Href": f"{GLAV}/oprosny-list/", "Description": "Исходные данные для расчёта конструкции"},
        ],
    },
    1926904124215700659: {
        "href": f"{GLAV}/shumozashitnye-cabiny-i-kozhuhi/kshz/",
        "sitelinks": [
            {"Title": "Все решения", "Href": f"{GLAV}/shumozashitnye-cabiny-i-kozhuhi/", "Description": "Кабины, кожухи и комплектные системы"},
            {"Title": "Шумозащитные кабины", "Href": f"{GLAV}/shumozashitnye-cabiny-i-kozhuhi/cabins/", "Description": "Кабины для промышленного оборудования"},
            {"Title": "Акустические кожухи", "Href": f"{GLAV}/shumozashitnye-cabiny-i-kozhuhi/promyshlennye-akusticheskie-kozhuhi/", "Description": "Кожухи для промышленного оборудования"},
            {"Title": "Опросный лист", "Href": f"{GLAV}/oprosny-list/", "Description": "Исходные данные для расчёта конструкции"},
        ],
    },
}


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


def result_ids(result, key):
    items = result[key]
    errors = [item.get("Errors") for item in items if item.get("Errors")]
    if errors or len(items) != len(UPDATES):
        raise RuntimeError(errors or items)
    return [item["Id"] for item in items]


def ads():
    return call(
        "ads",
        "get",
        {
            "SelectionCriteria": {"Ids": list(UPDATES)},
            "FieldNames": ["Id", "CampaignId", "AdGroupId", "Type", "Status", "State", "StatusClarification"],
            "ResponsiveAdFieldNames": ["Href", "SitelinkSetId", "Titles", "Texts", "AdImages", "AdExtensions", "BusinessId"],
        },
    )["Ads"]


def structure(ad):
    responsive = ad["ResponsiveAd"]
    return {
        "titles": len(responsive.get("Titles", [])),
        "texts": len(responsive.get("Texts", [])),
        "images": len((responsive.get("AdImages") or {}).get("Items", [])),
        "callouts": len(responsive.get("AdExtensions", [])),
        "contacts": bool(responsive.get("BusinessId")),
    }


before = {ad["Id"]: ad for ad in ads()}
if set(before) != set(UPDATES) or any(ad["CampaignId"] != CAMPAIGN_ID for ad in before.values()):
    raise RuntimeError("Найдены не все объявления или неверная кампания")

set_ids = result_ids(
    call("sitelinks", "add", {"SitelinksSets": [{"Sitelinks": item["sitelinks"]} for item in UPDATES.values()]}),
    "AddResults",
)
result_ids(
    call(
        "ads",
        "update",
        {
            "Ads": [
                {"Id": ad_id, "ResponsiveAd": {"Href": update["href"], "SitelinkSetId": set_id}}
                for (ad_id, update), set_id in zip(UPDATES.items(), set_ids)
            ]
        },
    ),
    "UpdateResults",
)

after = {ad["Id"]: ad for ad in ads()}
for ad_id, update in UPDATES.items():
    if after[ad_id]["ResponsiveAd"]["Href"] != update["href"]:
        raise RuntimeError(f"Не сохранилась посадочная {ad_id}")
    if structure(after[ad_id]) != structure(before[ad_id]):
        raise RuntimeError(f"Изменилось наполнение объявления {ad_id}")

print(
    json.dumps(
        {
            "updated": len(UPDATES),
            "ads": [
                {
                    "id": ad_id,
                    "href": after[ad_id]["ResponsiveAd"]["Href"],
                    "status": after[ad_id]["Status"],
                    "state": after[ad_id]["State"],
                    **structure(after[ad_id]),
                }
                for ad_id in UPDATES
            ],
        },
        ensure_ascii=False,
    )
)
