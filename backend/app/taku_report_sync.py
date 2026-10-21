"""Bounded TAKU OpenAPI reads; credentials and signed URLs never enter logs."""
import csv
import hashlib
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from fastapi import Depends, HTTPException
from . import main_from_txt as m
from . import taku_reports as reports


def headers(key, timestamp):
    md = lambda s: hashlib.md5(s.encode()).hexdigest().upper()
    signature = md('\n'.join(['GET', md(''), 'application/json', 'X-Up-Key:'+key,
                              'X-Up-Timestamp:'+timestamp, '/v3/devicereport']))
    return {'X-Up-Key': key, 'X-Up-Timestamp': timestamp, 'X-Up-Signature': signature, 'Content-Type': 'application/json'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def read_url(url, request_headers=None, limit=5_000_000):
    request = urllib.request.Request(url, headers=request_headers or {})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
        raw = response.read(limit+1)
        if len(raw) > limit:
            raise HTTPException(422, '报表超过大小限制，请使用离线分批处理工具')
        return raw.decode('utf-8-sig')


def download_links(obj):
    # Official responses may expose one link or a collection of report shards.
    if isinstance(obj, str):
        return [obj] if obj.startswith('https://') else []
    if isinstance(obj, list):
        return [url for item in obj for url in download_links(item)]
    if isinstance(obj, dict):
        return [url for value in obj.values() for url in download_links(value)]
    return []


def sync(game_id, day, admin):
    today = datetime.now(reports.CN).date()
    if day >= today or (today-day).days > 30:
        raise HTTPException(422, '仅支持 UTC+8 最近三十天已结束日期')
    with m.SessionLocal() as s:
        game = m.get_or_404(s, m.Game, game_id, '游戏')
        app_id = json.loads(game.settings_json or '{}').get('ad_config', {}).get('app_id')
        config = s.get(m.TakuGlobalConfig, 1)
        if not app_id or not config or not config.publisher_key:
            raise HTTPException(409, '缺少 TAKU 应用 ID 或 Publisher Key')
        key = config.publisher_key
    url = 'https://openapi.toponad.com/v3/devicereport?'+urllib.parse.urlencode(
        {'app_id':app_id, 'day':day.strftime('%Y%m%d'), 'timezone':8})
    try:
        response = read_url(url, headers(key, str(int(time.time()*1000))), 500000)
    except urllib.error.HTTPError as error:
        statuses = {601:'signature_rejected', 602:'permission_rejected', 607:'waiting_report', 429:'rate_limited'}
        return {'status': statuses.get(error.code, 'provider_error'), 'provider_http': error.code, 'day':str(day)}
    except (OSError, UnicodeError):
        raise HTTPException(502, 'TAKU 请求失败，请稍后重试') from None
    try:
        obj = json.loads(response)
    except ValueError:
        obj = response.strip()
    links = list(dict.fromkeys(download_links(obj)))
    if not links or len(links) > 20:
        return {'status':'unsupported_response', 'day':str(day)}
    merged = io.StringIO()
    writer = None
    fields = None
    size = 0
    for link in links:
        parsed = urllib.parse.urlsplit(link)
        host = parsed.hostname or ''
        # Only official report storage. No credential-bearing redirects or arbitrary hosts.
        if parsed.scheme != 'https' or parsed.port not in (None,443) or parsed.username or parsed.password or not (
            host == 'topon-openapi.s3.amazonaws.com' or host.startswith('topon-openapi.s3.') and host.endswith('.amazonaws.com')):
            raise HTTPException(502, '下载域名尚未验证，请核对官方报表地址')
        try:
            text = read_url(link)
        except (OSError, UnicodeError):
            raise HTTPException(502, '报表下载失败，未覆盖原有结果') from None
        size += len(text.encode())
        if size > 5_000_000:
            raise HTTPException(422, '报表总大小超过 5 MB')
        reader = csv.DictReader(io.StringIO(text))
        if fields is None:
            fields = reader.fieldnames
            if not fields:
                raise HTTPException(422, '空下载文件')
            writer = csv.DictWriter(merged, fieldnames=fields)
            writer.writeheader()
        if reader.fieldnames != fields:
            raise HTTPException(422, '报表分片表头不一致，未覆盖原有结果')
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise HTTPException(422, '下载文件包含不完整行')
            writer.writerow(row)
    cutoff = datetime.combine(day+timedelta(days=2), datetime.min.time(), reports.CN)+timedelta(hours=4)
    stage = 'rechecked' if datetime.now(reports.CN) >= cutoff else 'preliminary'
    result = reports.import_report(game_id, reports.ImportInput(day=day, stage=stage, csv_text=merged.getvalue()), admin)
    return {'status':'imported', 'day':str(day), **result}


@m.api.post('/games/{game_id}/taku-reports/sync')
def sync_endpoint(game_id: int, day: date, admin=Depends(m.allow_roles('superadmin'))):
    return sync(game_id, day, admin)


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--game', type=int, required=True)
    parser.add_argument('--day', type=date.fromisoformat)
    args=parser.parse_args()
    today=datetime.now(reports.CN).date()
    days=[args.day] if args.day else [today-timedelta(days=1),today-timedelta(days=2)]
    for day in days:
        try:
            print(json.dumps(sync(args.game,day,SimpleNamespace(id=0))))
        except HTTPException as error:
            print(json.dumps({'day':str(day),'status':'failed','code':error.status_code,'detail':error.detail}))


if __name__ == '__main__':
    main()
