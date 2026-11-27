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
    assert service in ALLOWED and method in {'get', 'add', 'update', 'delete', 'suspend', 'archive'}
    assert service != 'businesses' or method == 'get'
    assert method != 'update' or service in {'ads', 'adgroups'}
    assert method not in {'suspend', 'archive'} or service == 'campaigns'
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


OLD_CAMPAIGN = 714161295
CAMPAIGN = 716746993
GROUP = 5832499730
LAVITA_GROUPS = {5795900522, 5832497754}
PHOTO_NAMES = ('pipeline-hero', 'tanks-hero', 'equipment-hero', 'small-hero', 'roof-hero', 'surface-hero')
AD_IDS = {1928111137801195208, 1928112004311784995, 1928112156782184504}
PHOTO_URLS = {f'https://korda.su/assets/industrial/{name}.webp' for name in PHOTO_NAMES}


def guard(service, method, params):
    assert REVISION
    if (service, method) == ('adimages', 'add'):
        items = params['AdImages']
        assert len(items) == 6
        assert {item['ImageData']['$image'] for item in items} == PHOTO_URLS
        assert all(item['Type'] == 'REGULAR' for item in items)
        return
    if (service, method) == ('ads', 'update'):
        rows = params['Ads']
        assert len(rows) == 3 and {row['Id'] for row in rows} == AD_IDS
        for row in rows:
            assert set(row) == {'Id', 'ResponsiveAd'}
            assert set(row['ResponsiveAd']) == {'AdImageHashes'}
            assert len(row['ResponsiveAd']['AdImageHashes']['Items']) == 2
        saved = api('ads', 'get', {'SelectionCriteria': {'CampaignIds': [CAMPAIGN]},
                                  'FieldNames': ['Id', 'AdGroupId', 'CampaignId', 'Type', 'State'],
                                  'ResponsiveAdFieldNames': ['AdImages']})['Ads']
        targets = [row for row in saved if row['AdGroupId'] == GROUP and row['State'] == 'ON']
        assert {row['Id'] for row in targets} == AD_IDS
        assert all(row['CampaignId'] == CAMPAIGN and row['Type'] == 'RESPONSIVE_AD' for row in targets)
        assert all(not row['ResponsiveAd'].get('AdImages', {}).get('Items') for row in targets)
        return
    assert service == 'campaigns' and method in {'suspend', 'archive'}
    assert params == {'SelectionCriteria': {'Ids': [OLD_CAMPAIGN]}}
    campaigns = api('campaigns', 'get', {'SelectionCriteria': {'Ids': [OLD_CAMPAIGN, CAMPAIGN]},
                                         'FieldNames': ['Id', 'Name', 'State']})['Campaigns']
    states = {row['Id']: row['State'] for row in campaigns}
    assert states.get(CAMPAIGN) == 'ON'
    assert states.get(OLD_CAMPAIGN) in ({'ON'} if method == 'suspend' else {'SUSPENDED', 'OFF'})
    if method == 'suspend':
        ads = api('ads', 'get', {'SelectionCriteria': {'CampaignIds': [OLD_CAMPAIGN, CAMPAIGN]},
                                'FieldNames': ['Id', 'AdGroupId', 'CampaignId', 'State']})['Ads']
        assert {row['AdGroupId'] for row in ads
                if row['CampaignId'] == OLD_CAMPAIGN and row['State'] == 'ON'} == {5795900522}
        assert {row['AdGroupId'] for row in ads if row['AdGroupId'] in LAVITA_GROUPS and row['State'] == 'ON'} == LAVITA_GROUPS


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
        assert service in ALLOWED and method in {'get', 'add', 'update', 'delete', 'suspend', 'archive'}
        try:
            if method != 'get':
                assert os.environ.get('CREATE_DRAFT') == 'yes'
                guard(service, method, call['params'] if service == 'adimages' else resolve(call['params']))
            params = resolve(call['params'])
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
        print('OK', name, service, method, {k: len(v) for k, v in result.items() if isinstance(v, list)})


if __name__ == '__main__':
    main()
