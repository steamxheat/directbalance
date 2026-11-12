#!/usr/bin/env python3
import csv
import io
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date


API = "https://api.direct.yandex.com/json/v501"
CAMPAIGN_ID = 715995851
START_DATE = "2026-11-09"
HEADERS = {
    "Authorization": f"Bearer {os.environ['YANDEX_DIRECT_TOKEN']}",
    "Client-Login": os.environ["YANDEX_DIRECT_LOGIN"],
    "Accept-Language": "ru",
    "Content-Type": "application/json; charset=utf-8",
}


def post(url, body, headers=HEADERS):
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8-sig")
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read().decode("utf-8-sig")


def call(service, params):
    status, _, text = post(f"{API}/{service}", {"method": "get", "params": params})
    if status != 200:
        raise RuntimeError(f"{service}: HTTP {status}: {text[:1000]}")
    payload = json.loads(text)
    if "error" in payload:
        raise RuntimeError(f"{service}: {payload['error']}")
    return payload["result"]


def report(report_type, fields):
    name = f"korda-{report_type.lower()}-{time.time_ns()}"
    body = {
        "params": {
            "SelectionCriteria": {
                "DateFrom": START_DATE,
                "DateTo": date.today().isoformat(),
                "Filter": [{"Field": "CampaignId", "Operator": "IN", "Values": [str(CAMPAIGN_ID)]}],
            },
            "FieldNames": fields,
            "Page": {"Limit": 1000},
            "ReportName": name,
            "ReportType": report_type,
            "DateRangeType": "CUSTOM_DATE",
            "Format": "TSV",
            "IncludeVAT": "YES",
            "IncludeDiscount": "NO",
        }
    }
    headers = HEADERS | {
        "processingMode": "auto",
        "returnMoneyInMicros": "false",
        "skipReportHeader": "true",
        "skipColumnHeader": "false",
        "skipReportSummary": "true",
    }
    for _ in range(24):
        status, response_headers, text = post(f"{API}/reports", body, headers)
        if status == 200:
            return list(csv.DictReader(io.StringIO(text), delimiter="\t"))
        if status in (201, 202):
            time.sleep(min(max(int(response_headers.get("retryIn", "5")), 1), 15))
            continue
        raise RuntimeError(f"{report_type}: HTTP {status}: {text[:1000]}")
    raise RuntimeError(f"{report_type}: report timeout")


campaigns = call("campaigns", {
    "SelectionCriteria": {"Ids": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "Name", "Type", "Status", "State", "StatusPayment"],
    "UnifiedCampaignFieldNames": ["CounterIds", "PriorityGoals", "BiddingStrategy", "Settings"],
})["Campaigns"]
assert len(campaigns) == 1 and campaigns[0]["Id"] == CAMPAIGN_ID

groups = call("adgroups", {
    "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "Name", "Status", "ServingStatus"],
})["AdGroups"]

keywords = call("keywords", {
    "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "Keyword", "CampaignId", "AdGroupId", "State", "Status", "ServingStatus", "Productivity"],
})["Keywords"]

ads = call("ads", {
    "SelectionCriteria": {"CampaignIds": [CAMPAIGN_ID]},
    "FieldNames": ["Id", "CampaignId", "AdGroupId", "Type", "State", "Status", "StatusClarification"],
})["Ads"]

print(json.dumps({
    "period": [START_DATE, date.today().isoformat()],
    "campaign": campaigns[0],
    "groups": groups,
    "keywords": keywords,
    "ads": ads,
    "campaign_stats": report("CAMPAIGN_PERFORMANCE_REPORT", [
        "CampaignId", "CampaignName", "Impressions", "Clicks", "Cost", "Ctr", "AvgCpc",
    ]),
    "group_stats": report("ADGROUP_PERFORMANCE_REPORT", [
        "CampaignId", "AdGroupId", "AdGroupName", "Impressions", "Clicks", "Cost", "Ctr", "AvgCpc",
    ]),
    "search_queries": report("SEARCH_QUERY_PERFORMANCE_REPORT", [
        "CampaignId", "AdGroupId", "AdGroupName", "Query", "Criterion", "MatchType",
        "Impressions", "Clicks", "Cost", "Ctr", "AvgCpc",
    ]),
}, ensure_ascii=False))
