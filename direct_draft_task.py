"""Run bounded draft-only API requests; credentials stay in Actions secrets."""
import json
import base64
import io
import zlib
import os
import subprocess
from pathlib import Path
import urllib.request
import urllib.error

OUT = Path('draft-output')
OUT.mkdir(exist_ok=True)
RESULTS = {}
REVISION_CAMPAIGN = 716717334
REVISION = bool(os.getenv('DRAFT_REVISION_KEY'))
ALLOWED = {'campaigns', 'adgroups', 'ads', 'keywords', 'sitelinks', 'adextensions', 'adimages', 'businesses'}


def api(service, method, params):
    assert service in ALLOWED and method in {'get', 'add', 'update', 'delete'}
    assert service != 'businesses' or method == 'get'
    assert method != 'update' or service in {'ads', 'adgroups'}
    assert method != 'delete' or (REVISION and service in {'keywords', 'ads', 'adgroups'})
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
    assert not REVISION or set(ids) == {REVISION_CAMPAIGN}
    rows = api('campaigns', 'get', {'SelectionCriteria': {'Ids': sorted(set(ids))},
                                   'FieldNames': ['Id', 'Name', 'State', 'Status']})['Campaigns']
    assert {r['Id'] for r in rows} == set(ids)
    assert all(r['Status'] == 'DRAFT' and r['State'] in {'OFF', 'SUSPENDED'} for r in rows), rows


def guard(service, params):
    if REVISION:
        assert service in {'adgroups', 'ads', 'keywords', 'adextensions', 'sitelinks'}
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


def guard_update(params):
    ids = [a['Id'] for a in params['Ads']]
    for a in params['Ads']:
        assert set(a) == {'Id', 'ResponsiveAd'}
        fields = {'SitelinkSetId', 'CalloutSetting'}
        if REVISION:
            fields |= {'Titles', 'Texts', 'Href', 'DisplayUrlPath', 'AdImageHashes'}
        assert set(a['ResponsiveAd']).issubset(fields)
        if 'CalloutSetting' in a['ResponsiveAd']:
            assert all(x['Operation'] == 'SET' for x in a['ResponsiveAd']['CalloutSetting']['AdExtensions'])
    rows = api('ads', 'get', {'SelectionCriteria': {'Ids': ids},
                              'FieldNames': ['Id', 'AdGroupId', 'State', 'Status']})['Ads']
    assert {a['Id'] for a in rows} == set(ids)
    assert all(a['Status'] == 'DRAFT' and a['State'] == 'OFF' for a in rows)
    gids = sorted({a['AdGroupId'] for a in rows})
    groups = api('adgroups', 'get', {'SelectionCriteria': {'Ids': gids},
                                    'FieldNames': ['Id', 'CampaignId']})['AdGroups']
    draft_campaigns([g['CampaignId'] for g in groups])


def guard_merged_draft_delete(service, params):
    draft_campaigns([REVISION_CAMPAIGN])
    criteria = {'CampaignIds': [REVISION_CAMPAIGN]}
    groups = api('adgroups', 'get', {'SelectionCriteria': criteria,
                                   'FieldNames': ['Id', 'Name', 'Status']})['AdGroups']
    retired = {g['Id'] for g in groups if g['Name'].startswith(('04 | Каркасы ', '05 | Сварная балка'))}
    target, = [g['Id'] for g in groups if g['Name'] == '02 | Крупногабаритные сварные конструкции']
    assert retired and all(g['Status'] == 'DRAFT' for g in groups if g['Id'] in retired | {target})
    ids = set(params['SelectionCriteria']['Ids'])
    assert ids
    ads = api('ads', 'get', {'SelectionCriteria': criteria,
                            'FieldNames': ['Id', 'AdGroupId', 'Status', 'State'],
                            'ResponsiveAdFieldNames': ['Titles', 'Texts', 'Href', 'DisplayUrlPath',
                                                       'AdImages', 'SitelinkSetId', 'AdExtensions', 'BusinessId']})['Ads']
    keywords = api('keywords', 'get', {'SelectionCriteria': criteria,
                                      'FieldNames': ['Id', 'AdGroupId', 'Keyword']})['Keywords']
    active_keys = {k['Keyword'] for k in keywords if k['AdGroupId'] == target}
    assert len(active_keys) == 31
    assert len([a for a in ads if a['AdGroupId'] == target]) == 9
    assert all(a['Status'] == 'DRAFT' and a['State'] == 'OFF' for a in ads)
    if service == 'ads':
        live = [a for a in ads if a['Id'] in ids]
        copies = [a['ResponsiveAd'] for a in ads if a['AdGroupId'] == target]
        assert {a['Id'] for a in live} == ids
        assert all(a['AdGroupId'] in retired and a['ResponsiveAd'] in copies for a in live)
    elif service == 'keywords':
        live = [k for k in keywords if k['Id'] in ids]
        assert {k['Id'] for k in live} == ids
        assert all(k['AdGroupId'] in retired and k['Keyword'] in active_keys for k in live)
    else:
        assert service == 'adgroups' and ids <= retired
        assert not any(row['AdGroupId'] in ids for row in ads + keywords)


def guard_revision(service, method, params, name):
    assert REVISION
    if method == 'delete' and name.startswith('merge-retire-'):
        guard_merged_draft_delete(service, params)
        return
    if (service, method) == ('adgroups', 'update'):
        assert all(set(group) <= {'Id', 'Name', 'NegativeKeywords'} for group in params['AdGroups'])
        ids = {group['Id'] for group in params['AdGroups']}
    else:
        assert (service, method) == ('keywords', 'delete')
        keyword_ids = set(params['SelectionCriteria']['Ids'])
        criteria = {'Ids': sorted(keyword_ids), 'CampaignIds': [REVISION_CAMPAIGN]}
        keywords = api('keywords', 'get', {'SelectionCriteria': criteria,
                                           'FieldNames': ['Id', 'AdGroupId', 'Keyword', 'State']})['Keywords']
        assert {k['Id'] for k in keywords} == keyword_ids
        assert all(k['Keyword'] != '---autotargeting' for k in keywords)
        ids = {k['AdGroupId'] for k in keywords}
    groups = api('adgroups', 'get', {'SelectionCriteria': {'Ids': sorted(ids)},
                                    'FieldNames': ['Id', 'CampaignId', 'Status']})['AdGroups']
    assert ids and {g['Id'] for g in groups} == ids
    assert all(g['Status'] == 'DRAFT' for g in groups)
    draft_campaigns([g['CampaignId'] for g in groups])


def crypt(data, decrypt=False):
    flags = ['-d'] if decrypt else []
    return subprocess.run(
        ['openssl', 'enc', '-aes-256-cbc', '-pbkdf2', '-iter', '100000', '-pass', 'env:DRAFT_REVISION_KEY', *flags],
        input=data, capture_output=True, check=True).stdout


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
    raw = os.environ.get('REQUESTS_JSON') or '[]'
    if REVISION and raw != '[]':
        raw = zlib.decompress(crypt(base64.b64decode(raw), decrypt=True)).decode()
    if raw.startswith('z:'):
        raw = zlib.decompress(base64.b64decode(raw[2:])).decode()
    calls = json.loads(raw)
    assert isinstance(calls, list) and len(calls) <= 25
    for call in calls:
        name, service, method = (call[k] for k in ['name', 'service', 'method'])
        assert name.replace('-', '').replace('_', '').isalnum() and name not in RESULTS
        assert service in ALLOWED and method in {'get', 'add', 'update', 'delete'}
        params = resolve(call['params'])
        try:
            if method in {'add', 'update', 'delete'}:
                assert os.environ.get('CREATE_DRAFT') == 'yes'
                if method == 'add':
                    guard(service, params)
                elif (service, method) == ('ads', 'update'):
                    guard_update(params)
                else:
                    guard_revision(service, method, params, name)
            result = api(service, method, params)
        except RuntimeError as error:
            if not REVISION:
                raise
            (OUT / (name + '.error.enc')).write_bytes(crypt(str(error).encode()))
            raise RuntimeError(f'{name}: API rejected request; see encrypted artifact') from None
        RESULTS[name] = result
        body = json.dumps(result, ensure_ascii=False, indent=2).encode()
        (OUT / (name + ('.json.enc' if REVISION else '.json'))).write_bytes(crypt(body) if REVISION else body)
        errors = [r for k, rows in result.items() if k.endswith('Results')
                  for r in rows if r.get('Errors')]
        assert not errors, f'{name}: {len(errors)} per-item failures; see artifact' if REVISION else errors
        assert 'LimitedBy' not in result, 'Paginated response requires explicit continuation'
        if service == 'campaigns' and method == 'add':
            draft_campaigns([r['Id'] for r in result['AddResults']])
        print('OK', name, service, method, {k: len(v) for k, v in result.items() if isinstance(v, list)})


if __name__ == '__main__':
    main()
