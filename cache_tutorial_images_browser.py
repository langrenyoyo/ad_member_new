"""Read tutorial image assets through a browser session; never writes reference data."""
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

SOURCE = Path('public/target-book.json')
OUT = Path('public/assets/tutorial')
BASE = 'https://ad.leadink.cn/DmvTqXBpfF.php'
data = json.loads(SOURCE.read_text(encoding='utf-8-sig'))
rows = data.get('items', data.get('rows', []))
urls = sorted({url for row in rows for url in re.findall(r'src="([^"]+)"', row.get('content', ''))
               if url.startswith('https://api.xmchujian.com/uploads/')})
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    try:
        page.goto(BASE + '/index/login', wait_until='domcontentloaded', timeout=30000)
        page.fill('[name=username]', '18532306918')
        page.fill('[name=password]', '123456')
        page.locator('button[type=submit],input[type=submit]').first.click()
        page.wait_for_timeout(1500)
    except Exception:
        pass
    results = {}
    for url in urls:
        name = url.rsplit('/', 1)[-1]
        try:
            response = context.request.get(url, timeout=30000)
            body = response.body()
            if response.status != 200 or not body.startswith(b'\x89PNG\r\n\x1a\n'):
                raise RuntimeError(f'HTTP {response.status}, {response.headers.get("content-type", "")}, {len(body)} bytes')
            (OUT / name).write_bytes(body)
            results[url] = '/assets/tutorial/' + name
            print(name, 'OK', len(body), flush=True)
        except Exception as error:
            results[url] = None
            print(name, type(error).__name__, str(error), flush=True)
    browser.close()

if any(results.values()):
    for row in rows:
        for original, local in results.items():
            if local:
                row['content'] = row.get('content', '').replace(original, local)
    data['items' if 'items' in data else 'rows'] = rows
    SOURCE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print('Cached', sum(value is not None for value in results.values()), 'of', len(urls), 'images')
