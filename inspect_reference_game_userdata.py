"""Read-only HTML structure capture. Never execute reference scripts or save row values."""
import json
import re
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

BASE = 'https://ad.leadink.cn/DmvTqXBpfF.php'
session = requests.Session()
response = session.get(BASE + '/index/login', timeout=20)
response.encoding = 'utf-8'
token = re.search(r'name="__token__" value="([^"]+)"', response.text).group(1)
response = session.post(BASE + '/index/login', data={
    'username': '18532306918', 'password': '123456', '__token__': token,
}, headers={'X-Requested-With': 'XMLHttpRequest'}, timeout=20)
if response.json().get('code') != 1:
    raise RuntimeError('Reference login failed')
response = session.get(BASE + '/game/index', params={'limit': 1, 'offset': 0, 'filter': '{}', 'op': '{}'},
                       headers={'X-Requested-With': 'XMLHttpRequest'}, timeout=20)
rows = response.json().get('rows', [])
if not rows:
    raise RuntimeError('No reference game available')
game_id = rows[0]['id']
response = session.get(BASE + f'/games/userdata/index/game_id/{game_id}', timeout=20)
response.encoding = 'utf-8'
page_html = response.text
config_match = re.search(r'\bvar\s+Config\s*=\s*', page_html)
if not config_match:
    config_match = re.search(r'\bvar\s+require\s*=\s*\{\s*config\s*:\s*', page_html)
if config_match:
    config, _ = json.JSONDecoder().raw_decode(page_html[config_match.end():])
    config = config.get('config', config)
    statistics = {'keys': sorted(config)}
    for field in ['column', 'column1', 'userdata', 'data1', 'data2', 'data3', 'data4', 'mapdata', 'mapdata1', 'mapdata2']:
        values = config.get(field, [])
        statistics[field] = {'type': type(values).__name__, 'length': len(values) if isinstance(values, (list, dict, str)) else None}
        if field in ['column', 'column1'] and isinstance(values, list):
            statistics[field]['dates'] = values
        elif isinstance(values, list):
            statistics[field]['item_keys'] = sorted(values[0]) if values and isinstance(values[0], dict) else []
            statistics[field]['nonzero_count'] = sum(isinstance(value, (int, float)) and value != 0 for value in values)
    Path('visual-baseline/reference-verified/game-statistics-data-shape.json').write_text(
        json.dumps(statistics, ensure_ascii=False, indent=2), encoding='utf-8')
endpoint_shapes = {}
for resource in ['lottery', 'risk', 'exchange', 'user', 'loginlog', 'live']:
    result = session.get(BASE + f'/games/{resource}/index/game_id/{game_id}',
                         params={'limit': 1, 'offset': 0, 'filter': '{}', 'op': '{}'},
                         headers={'X-Requested-With': 'XMLHttpRequest'}, timeout=20)
    data = result.json()
    sample = data.get('rows', [])
    endpoint_shapes[resource] = {'status': result.status_code, 'total': data.get('total'),
                                 'fields': list(sample[0]) if sample else []}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(java_script_enabled=False)
    page.route('**/*', lambda route: route.abort())
    page.set_content(page_html)
    structure = page.locator('body').evaluate('''body => ({
        tabs: Array.from(body.querySelectorAll('.nav-tabs a')).map(e=>({text:e.textContent.trim(),href:e.getAttribute('href'),active:e.parentElement.classList.contains('active')})),
        panels: Array.from(body.querySelectorAll('.tab-pane')).map(e=>({id:e.id,text:e.innerText.trim(),tables:Array.from(e.querySelectorAll('table')).map(t=>t.id)}))
    })''')
    browser.close()
structure['endpoints'] = endpoint_shapes
Path('visual-baseline/reference-verified/game-userdata-structure.json').write_text(
    json.dumps(structure, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(structure, ensure_ascii=True))
