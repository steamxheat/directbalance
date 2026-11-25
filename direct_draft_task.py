"""Run bounded draft-only API requests; credentials stay in Actions secrets."""
import json
import base64
import io
import os
from pathlib import Path
import urllib.request
import urllib.error

OUT = Path('draft-output')
OUT.mkdir(exist_ok=True)
RESULTS = {}
ALLOWED = {'campaigns', 'adgroups', 'ads', 'keywords', 'sitelinks', 'adextensions', 'adimages', 'businesses'}


def api(service, method, params):
    assert service in ALLOWED and method in {'get', 'add'}
    assert service != 'businesses' or method == 'get'
    req = urllib.request.Request(
        'https://api.direct.yandex.com/json/v501/' + service,
        data=json.dumps({'method': method, 'params': params}).encode(),
        headers={'Authorization': 'Bearer ' + os.environ['YANDEX_DIRECT_TOKEN'],
                 'Client-Login': os.environ['CLIENT_LOGIN'], 'Accept-Language': 'ru',
                 'Content-Type': 'application/json; charset=utf-8'})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            value = json.load(response)
    except urllib.error.HTTPError as e:
        raise RuntimeError(e.read().decode()[:2000]) from None
    if 'error' in value:
        raise RuntimeError(value['error'])
    return value['result']


def draft_campaigns(ids):
    rows = api('campaigns', 'get', {'SelectionCriteria': {'Ids': sorted(set(ids))},
                                   'FieldNames': ['Id', 'Name', 'State', 'Status']})['Campaigns']
    assert {r['Id'] for r in rows} == set(ids)
    assert all(r['Status'] == 'DRAFT' and r['State'] in {'OFF', 'SUSPENDED'} for r in rows), rows


def guard(service, params):
    if service == 'campaigns':
        assert len(params['Campaigns']) == 1
        c = params['Campaigns'][0]
        assert 'ЧЕРНОВИК' in c['Name']
        existing = api('campaigns', 'get', {'SelectionCriteria': {}, 'FieldNames': ['Id', 'Name']})
        assert 'LimitedBy' not in existing
        assert not any(x['Name'] == c['Name'] for x in existing['Campaigns']), 'Draft already exists; read back before continuing'
        u = c['UnifiedCampaign']['BiddingStrategy']
        assert u['Network']['BiddingStrategyType'] == 'SERVING_OFF'
        assert u['Search']['BiddingStrategyType'] == 'WB_MAXIMUM_CLICKS'
        assert u['Search']['WbMaximumClicks']['WeeklySpendLimit'] == 10_000_000_000
    elif service == 'adgroups':
        draft_campaigns([g['CampaignId'] for g in params['AdGroups']])
    elif service in {'ads', 'keywords'}:
        key = 'Ads' if service == 'ads' else 'Keywords'
        ids = sorted({a['AdGroupId'] for a in params[key]})
        groups = api('adgroups', 'get', {'SelectionCriteria': {'Ids': ids},
                                       'FieldNames': ['Id', 'CampaignId']})['AdGroups']
        assert {g['Id'] for g in groups} == set(ids)
        draft_campaigns([g['CampaignId'] for g in groups])


def resolve(obj):
    if isinstance(obj, dict):
        if set(obj) == {'$image'}:
            from PIL import Image
            assert obj['$image'].startswith('https://')
            with urllib.request.urlopen(obj['$image'], timeout=30) as response:
                data = response.read(10_000_001)
            assert len(data) <= 10_000_000
            with Image.open(io.BytesIO(data)) as source:
                assert source.width >= 450 and source.height >= 450
                buf = io.BytesIO()
                source.convert('RGB').save(buf, 'JPEG', quality=94)
            return base64.b64encode(buf.getvalue()).decode()
        if set(obj) == {'$ref'}:
            parts = obj['$ref'].split('.')
            value = RESULTS[parts.pop(0)]
            for p in parts:
                value = value[int(p)] if isinstance(value, list) else value[p]
            return value
        return {k: resolve(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve(v) for v in obj]
    return obj


def main():
    calls = json.loads(os.environ.get('REQUESTS_JSON') or '[]')
    assert isinstance(calls, list) and len(calls) <= 25
    for call in calls:
        name, service, method = (call[k] for k in ['name', 'service', 'method'])
        assert name.replace('-', '').replace('_', '').isalnum() and name not in RESULTS
        assert service in ALLOWED and method in {'get', 'add'}
        params = resolve(call['params'])
        if method == 'add':
            assert os.environ.get('CREATE_DRAFT') == 'yes'
            guard(service, params)
        result = api(service, method, params)
        RESULTS[name] = result
        (OUT / (name + '.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2))
        errors = [r for k, rows in result.items() if k.endswith('Results')
                  for r in rows if r.get('Errors')]
        assert not errors, errors
        assert 'LimitedBy' not in result, 'Paginated response requires explicit continuation'
        if service == 'campaigns' and method == 'add':
            draft_campaigns([r['Id'] for r in result['AddResults']])
        print('OK', name, service, method, {k: len(v) for k, v in result.items() if isinstance(v, list)})


if __name__ == '__main__':
    main()
