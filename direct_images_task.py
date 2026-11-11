#!/usr/bin/env python3
import base64
import io
import json
import os
import urllib.error
import urllib.request

from PIL import Image


API = "https://api.direct.yandex.com/json/v501"
CAMPAIGN_ID = 715995851
ADS = {
    1926541080294601959: ("01_Бренд_KORDA", "https://static.tildacdn.com/tila3535-6462-4739-b832-336534303932/fireproof-equip.jpeg"),
    1926541997268228793: ("02_Тканевые_компенсаторы", "https://static.tildacdn.com/tila3636-6331-4633-b233-383861663465/photo.png"),
    1926542285033192900: ("03_Шумоизоляционные_чехлы", "https://static.tildacdn.com/tila3464-3538-4764-b363-616134636131/photo_9_2025-10-24_1.jpg"),
    1926543574597341768: ("04_Шумозащитные_кабины", "https://static.tildacdn.com/tila3133-3365-4661-a136-346637393733/kshz-angar-long.jpg"),
    1926543198787092320: ("05_Шумозащитные_кожухи", "https://static.tildacdn.com/tila3438-6533-4334-a638-356239643533/bunner-main-isomax-t.webp"),
    1926714010708993505: ("06_Керамические_изделия", "https://static.tildacdn.com/tila3135-3065-4933-b439-646663353239/item_photo.jpg"),
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
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Direct API HTTP {error.code}") from error
    if "error" in payload:
        error = payload["error"]
        raise RuntimeError(f"Direct API {error.get('error_code')}: {error.get('error_string')}: {error.get('error_detail')}")
    return payload["result"]


def check_results(result, key):
    errors = [item["Errors"] for item in result[key] if item.get("Errors")]
    if errors:
        raise RuntimeError(f"Ошибки операции: {errors}")
    return result[key]


def campaign():
    items = call(
        "campaigns",
        "get",
        {"SelectionCriteria": {"Ids": [CAMPAIGN_ID]}, "FieldNames": ["Id", "Name", "Status", "State", "StatusPayment"]},
    )["Campaigns"]
    if len(items) != 1:
        raise RuntimeError("Кампания не найдена")
    return items[0]


def ads():
    items = call(
        "ads",
        "get",
        {
            "SelectionCriteria": {"Ids": list(ADS)},
            "FieldNames": ["Id", "CampaignId", "AdGroupId", "Type", "Status", "State"],
            "ResponsiveAdFieldNames": ["Href", "AdImages"],
        },
    ).get("Ads", [])
    if {item["Id"] for item in items} != set(ADS):
        raise RuntimeError("Найдены не все шесть объявлений")
    if any(item["CampaignId"] != CAMPAIGN_ID or item["Type"] != "RESPONSIVE_AD" for item in items):
        raise RuntimeError("Объявление относится не к той кампании или имеет неверный тип")
    return sorted(items, key=lambda item: item["Id"])


def jpeg_data(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        source = response.read()
    if not source or len(source) > 20_000_000:
        raise RuntimeError(f"Некорректный размер исходного изображения: {url}")
    with Image.open(io.BytesIO(source)) as image:
        image = image.convert("RGB")
        width, height = image.size
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        image = image.crop((left, top, left + side, top + side))
        if side < 450:
            image = image.resize((450, 450), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=90, optimize=True)
    data = output.getvalue()
    if not 0 < len(data) <= 10_000_000:
        raise RuntimeError(f"Некорректный размер подготовленного изображения: {url}")
    return base64.b64encode(data).decode()


def upload_images():
    prepared = [(ad_id, name, jpeg_data(url)) for ad_id, (name, url) in ADS.items()]
    hashes = {}
    for offset in range(0, len(prepared), 3):
        batch = prepared[offset:offset + 3]
        result = call(
            "adimages",
            "add",
            {"AdImages": [{"Name": name, "ImageData": data, "Type": "REGULAR"} for _, name, data in batch]},
        )
        uploaded = check_results(result, "AddResults")
        for (ad_id, _, _), item in zip(batch, uploaded, strict=True):
            image_hash = item.get("AdImageHash")
            if not image_hash:
                raise RuntimeError("Директ не вернул хеш загруженного изображения")
            hashes[ad_id] = image_hash
    return hashes


def verify(items):
    result = []
    for item in items:
        images = (item.get("ResponsiveAd") or {}).get("AdImages") or []
        result.append({
            "ad_id": item["Id"],
            "group": ADS[item["Id"]][0],
            "status": item["Status"],
            "state": item["State"],
            "images": len(images),
        })
    return result


def main():
    mode = os.environ.get("DIRECT_IMAGES_MODE", "inspect")
    current = ads()
    if mode == "inspect":
        print(json.dumps({"mode": mode, "campaign": campaign(), "ads": verify(current)}, ensure_ascii=False))
        return
    if mode != "apply":
        raise RuntimeError("Неизвестный режим")
    hashes = upload_images()
    updates = [
        {"Id": ad_id, "ResponsiveAd": {"AdImageHashes": {"Items": [hashes[ad_id]]}}}
        for ad_id in ADS
    ]
    check_results(call("ads", "update", {"Ads": updates}), "UpdateResults")
    final = ads()
    checked = verify(final)
    if any(item["images"] != 1 for item in checked):
        raise RuntimeError("Изображения сохранились не во всех объявлениях")
    print(json.dumps({"updated": True, "campaign": campaign(), "ads": checked}, ensure_ascii=False))


if __name__ == "__main__":
    main()
