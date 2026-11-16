import json
import os
import urllib.request


TOKEN = os.environ["YANDEX_DIRECT_TOKEN"]
LOGIN = os.environ.get("YANDEX_DIRECT_LOGIN", "e-20086596")
APPLY = os.environ.get("APPLY") == "true"
CAMPAIGN_ID = 706863240
GROUP_NAME = "Пищевые / Общая страница"
OLD_GROUP_IDS = [5709693724, 5709693725, 5709693726, 5709693727, 5709693728]
LANDING = "https://xn--80aeb4aacrhcscincn.xn--p1ai/pishchchekhly/"
NEGATIVE_KEYWORDS = [
    "авито", "бесплатно", "бу", "вакансии", "видео", "готовка", "домашний",
    "инструкция", "работа", "ремонт", "рецепт", "самодельный", "скачать",
    "сумка", "форум", "фото", "чертеж",
]
KEYWORDS = [
    "пищевые термочехлы",
    "термочехлы для продуктов",
    "термочехлы для пищевого производства",
    "термочехол для пищевых продуктов",
    "термочехлы для транспортировки продуктов",
    "термочехлы для хранения продуктов",
    "теплоизоляционные чехлы для продуктов",
    "термочехлы для паллет",
    "термочехлы для тележек шпилек",
    "термочехлы для ролл контейнеров",
    "термочехлы для расстойки теста",
    "купить пищевой термочехол",
]
ADS = [
    (
        "Пищевые термочехлы от производителя",
        "Доставка по РФ и СНГ",
        "Для паллет, продуктов, тележек и ролл-контейнеров. Изготовление под заказ.",
    ),
    (
        "Пищевые термочехлы «Корда»",
        "Гарантия 12 месяцев",
        "Сохраняют температуру продуктов при хранении и перевозке. Доставка по РФ и СНГ.",
    ),
    (
        "Термочехлы для пищевых производств",
        "Под размеры заказчика",
        "Для европаллет, расстойки, шпилек и контейнеров. Быстрый монтаж за 2 минуты.",
    ),
]


def call(service, method, params):
    request = urllib.request.Request(
        f"https://api.direct.yandex.com/json/v5/{service}",
        data=json.dumps({"method": method, "params": params}).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Client-Login": LOGIN,
            "Accept-Language": "ru",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)
    if result.get("error"):
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result


def ids(result, key):
    rows = result["result"][key]
    errors = [row for row in rows if row.get("Errors")]
    if errors:
        raise RuntimeError(json.dumps(errors, ensure_ascii=False))
    return [row["Id"] for row in rows]


def get_existing():
    groups = call(
        "adgroups",
        "get",
        {
            "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
            "FieldNames": ["Id", "Name", "Status", "ServingStatus"],
        },
    )["result"]["AdGroups"]
    return next((group for group in groups if group["Name"] == GROUP_NAME), None)


def validate():
    assert len(set(KEYWORDS)) == len(KEYWORDS)
    for title, title2, text in ADS:
        assert len(title) <= 56, (title, len(title))
        assert len(title2) <= 30, (title2, len(title2))
        assert len(text) <= 81, (text, len(text))


validate()
existing = get_existing()
if existing:
    raise RuntimeError(f"Группа уже существует: {existing}")

print(json.dumps({"apply": APPLY, "campaign": CAMPAIGN_ID, "group": GROUP_NAME,
                  "keywords": KEYWORDS, "ads": ADS}, ensure_ascii=False, indent=2))
if not APPLY:
    raise SystemExit(0)

# The old groups are preserved, but their ads and targeting are explicitly stopped
# before the campaign is resumed so only the new group can serve.
old_ads = call(
    "ads", "get",
    {
        "SelectionCriteria": {"AdGroupIds": OLD_GROUP_IDS},
        "FieldNames": ["Id", "AdGroupId", "State", "Status"],
    },
)["result"]["Ads"]
old_keywords = call(
    "keywords", "get",
    {
        "SelectionCriteria": {"AdGroupIds": OLD_GROUP_IDS},
        "FieldNames": ["Id", "AdGroupId", "State", "Status"],
    },
)["result"]["Keywords"]
ids(call("ads", "suspend", {"SelectionCriteria": {"Ids": [row["Id"] for row in old_ads]}}), "SuspendResults")
ids(call("keywords", "suspend", {"SelectionCriteria": {"Ids": [row["Id"] for row in old_keywords]}}), "SuspendResults")

group_id = ids(
    call(
        "adgroups", "add",
        {
            "AdGroups": [{
                "Name": GROUP_NAME,
                "CampaignId": CAMPAIGN_ID,
                "RegionIds": [225, 977],
                "NegativeKeywords": {"Items": NEGATIVE_KEYWORDS},
            }]
        },
    ),
    "AddResults",
)[0]

auto_target = next(
    row for row in call(
        "keywords", "get",
        {
            "SelectionCriteria": {"AdGroupIds": [group_id]},
            "FieldNames": ["Id", "Keyword", "State", "Status"],
        },
    )["result"]["Keywords"]
    if row["Keyword"] == "---autotargeting"
)
ids(
    call(
        "keywords", "update",
        {"Keywords": [{
            "Id": auto_target["Id"],
            "AutotargetingSettings": {
                "Categories": {
                    "Exact": "YES", "Narrow": "YES", "Alternative": "NO",
                    "Accessory": "NO", "Broader": "NO",
                },
                "BrandOptions": {
                    "WithoutBrands": "YES", "WithAdvertiserBrand": "YES",
                    "WithCompetitorsBrand": "NO",
                },
            },
        }]},
    ),
    "UpdateResults",
)

keyword_ids = ids(
    call(
        "keywords", "add",
        {"Keywords": [{"Keyword": keyword, "AdGroupId": group_id} for keyword in KEYWORDS]},
    ),
    "AddResults",
)

sitelink_id = ids(
    call(
        "sitelinks", "add",
        {"SitelinksSets": [{"Sitelinks": [
            {"Title": "Виды термочехлов", "Href": LANDING + "?utm_content=sitelink_types", "Description": "Решения для хранения и перевозки продуктов"},
            {"Title": "Наши преимущества", "Href": LANDING + "?utm_content=sitelink_benefits", "Description": "Собственное производство и гарантия 12 месяцев"},
            {"Title": "Доставка по РФ и СНГ", "Href": LANDING + "?utm_content=sitelink_delivery", "Description": "Изготавливаем и доставляем под вашу задачу"},
            {"Title": "Получить расчёт", "Href": LANDING + "?utm_content=sitelink_quote#zakaz", "Description": "Оставьте заявку на индивидуальный расчёт"},
        ]}]},
    ),
    "AddResults",
)[0]

callout_ids = ids(
    call(
        "adextensions", "add",
        {"AdExtensions": [
            {"Callout": {"CalloutText": "От производителя"}},
            {"Callout": {"CalloutText": "Гарантия 12 месяцев"}},
            {"Callout": {"CalloutText": "Доставка по РФ и СНГ"}},
            {"Callout": {"CalloutText": "Под размеры заказчика"}},
        ]},
    ),
    "AddResults",
)

tracking = (
    "?utm_source=yandex&utm_medium=cpc&utm_campaign={campaign_name}_{campaign_id}_{source_type}"
    "&utm_content={gbid}_{ad_id}&utm_term={keyword}&block={position_type}"
    "&position={position}&region={region_name}&type={source_type}&source={source}"
    "&utm_id=yadirect_{campaign_name}_{campaign_id}"
)
ad_ids = ids(
    call(
        "ads", "add",
        {"Ads": [{
            "AdGroupId": group_id,
            "TextAd": {
                "Title": title,
                "Title2": title2,
                "Text": text,
                "Href": LANDING + tracking,
                "Mobile": "NO",
                "DisplayUrlPath": "pishchevye-chekhly",
                "SitelinkSetId": sitelink_id,
                "AdExtensionIds": callout_ids,
                "BusinessId": 1334573358,
            },
        } for title, title2, text in ADS]},
    ),
    "AddResults",
)

ids(call("ads", "moderate", {"SelectionCriteria": {"Ids": ad_ids}}), "ModerateResults")
ids(call("campaigns", "resume", {"SelectionCriteria": {"Ids": [CAMPAIGN_ID]}}), "ResumeResults")

print(json.dumps({
    "created": {"group_id": group_id, "keyword_ids": keyword_ids,
                "autotarget_id": auto_target["Id"], "sitelink_id": sitelink_id,
                "callout_ids": callout_ids, "ad_ids": ad_ids},
    "stopped_old": {"ads": len(old_ads), "keywords": len(old_keywords)},
}, ensure_ascii=False, indent=2))
