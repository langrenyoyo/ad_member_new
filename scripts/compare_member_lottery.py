"""Compare synthetic editor tabs without submitting reference business writes."""
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TAB = os.environ.get('PARITY_MEMBER_TAB', 'lottery')
DATE_PICKER = TAB == 'basic' and os.environ.get('PARITY_DATE_PICKER') == '1'
DATE_PANEL = os.environ.get('PARITY_DATE_PANEL', 'date')
BASIC_BOTTOM = TAB == 'basic' and os.environ.get('PARITY_BASIC_BOTTOM') == '1'
TAB_ID = {'basic': 'tab-1', 'lottery': 'tab-2', 'download': 'tab-3', 'agent': 'tab-4'}[TAB]
OUT = ROOT / 'visual-baseline/fixtures' / ('member-date-picker' if DATE_PICKER else 'member-' + TAB)
if DATE_PICKER and DATE_PANEL != 'date':
    OUT = ROOT / 'visual-baseline/fixtures' / ('member-time-' + DATE_PANEL)
elif BASIC_BOTTOM:
    OUT = ROOT / 'visual-baseline/fixtures/member-basic-bottom'
OUT.mkdir(parents=True, exist_ok=True)
DATA = dict(raffle_open=1, raffle_num='12', star_countdown='3.5', over_countdown='9',
            raffle_num2='7', star_countdown2='1.25', over_countdown2='8.75')
if TAB == 'download':
    DATA = dict(down_load='https://example.test/download/app.apk')
elif TAB == 'agent':
    DATA = dict(ht_status=1, percent_zhi='12.5', percent_jian='3', percent_dai='8.75', percent_dai_two='1.25')
elif TAB == 'basic':
    DATA = dict(image_url='', username='fixture-9200', password='', pay_password='', name='对比会员',
                device_id='fixture-device', sex='2', real_name='模拟姓名', card_no='000000000000000000',
                address='模拟地址', is_true=0, realname_enable=1, exchange_enable=1,
                game_addiction_enable=0, game_addiction_time='', is_white=0, status=1, vip='2',otherlevel='模拟其它信息')
USERNAME = os.environ['PARITY_USERNAME']
PASSWORD = os.environ['PARITY_PASSWORD']
METRICS = {}


def capture(page, scope, window, reference):
    for key, value in DATA.items():
        name = f'row[{key}]' if reference else key
        control = scope.locator(f'[name="{name}"]')
        if TAB == 'basic':
            control.evaluate_all("(els,value)=>els.forEach(el=>{if(el.type==='radio')el.checked=el.value===String(value);else el.value=String(value);})", value)
            continue
        if control.first.get_attribute('type') == 'radio':
            selected = scope.locator(f'[name="{name}"][value="{value}"]')
            if reference:
                selected.locator('xpath=ancestor::label').click()
                assert selected.is_checked()
            else:
                selected.check()
        elif control.evaluate('el=>el.tagName') == 'SELECT':
            control.select_option(str(value))
        else:
            control.fill(str(value))
    if TAB == 'basic':
        if reference:
            scope.locator('[name="row[image_url]"]').evaluate("el=>{el.closest('.form-group').querySelectorAll('.faupload-preview').forEach(preview=>preview.replaceChildren());window.scrollTo(0,0);}")
        else:
            scope.locator('.member-edit-fields').evaluate('el=>el.scrollTop=0')
    scope.locator('body' if reference else '.member-edit-tabs').click(position={'x': 1, 'y': 1})
    page.evaluate('async()=>{await document.fonts.ready}')
    page.wait_for_timeout(600)
    box = window.bounding_box()
    kind = 'reference' if reference else 'local'
    fields = {}
    for key in DATA:
        name = f'row[{key}]' if reference else key
        control = scope.locator(f'[name="{name}"]').first
        if control.get_attribute('type') == 'radio':
            control = control.locator('xpath=ancestor::label')
        rect = control.bounding_box()
        fields[key] = dict(x=rect['x']-box['x'], y=rect['y']-box['y'],
                           width=rect['width'], height=rect['height'])
    METRICS[kind] = fields
    if reference:
        styles = scope.locator(f'.nav-tabs,.nav-tabs a,#{TAB_ID},#{TAB_ID} .form-group,#{TAB_ID} .form-group *').evaluate_all('''els=>els.map(el=>{
          const s=getComputedStyle(el),r=el.getBoundingClientRect();
          return {tag:el.tagName,cls:el.className,name:el.name,
            text:el.children.length?null:el.textContent.trim(),
            rect:{x:r.x,y:r.y,width:r.width,height:r.height},
            font:s.font,color:s.color,background:s.backgroundColor,padding:s.padding,margin:s.margin,
            border:s.border,display:s.display,width:s.width,height:s.height};})''')
        (OUT / 'reference-layout.json').write_text(json.dumps(styles,ensure_ascii=False,indent=2),encoding='utf-8')
    if DATE_PICKER:
        name='row[game_addiction_time]' if reference else 'game_addiction_time'
        control=scope.locator(f'[name="{name}"]')
        control.evaluate("el=>window.jQuery(el).data('DateTimePicker').date('2026-09-17 12:34:56')")
        control.evaluate("el=>el.scrollIntoView({block:'end'})")
        control.click()
        control.evaluate("el=>window.jQuery(el).data('DateTimePicker').show()")
        widget=scope.locator('.bootstrap-datetimepicker-widget')
        widget.wait_for(state='visible')
        if DATE_PANEL != 'date':
            widget.locator('[data-action=togglePicker]').click()
            page.wait_for_timeout(400)
            actions={'hours':'showHours','minutes':'showMinutes','seconds':'showSeconds'}
            if DATE_PANEL in actions:
                widget.locator('[data-action='+actions[DATE_PANEL]+']').click()
        page.wait_for_timeout(300)
        METRICS[kind]['widget']=widget.bounding_box()
        layout=widget.evaluate('''el=>[el,...el.querySelectorAll('ul,li,table,th,td,a,span')].map(n=>{
          const s=getComputedStyle(n);return {tag:n.tagName,cls:n.className,text:n.textContent.trim(),rect:n.getBoundingClientRect().toJSON(),font:s.font,color:s.color,background:s.backgroundColor,border:s.border,padding:s.padding,margin:s.margin,borderSpacing:s.borderSpacing};})''')
        (OUT/f'{kind}-widget-layout.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding='utf-8')
        widget.screenshot(path=str(OUT / f'{kind}.png'))
    else:
        if BASIC_BOTTOM:
            if reference:
                scope.locator('body').evaluate('()=>window.scrollTo(0,document.documentElement.scrollHeight)')
            else:
                scope.locator('.member-edit-fields').evaluate('el=>el.scrollTop=el.scrollHeight')
            page.wait_for_timeout(300)
            key='row[otherlevel]' if reference else 'otherlevel'
            METRICS[kind]['bottom_field']=scope.locator(f'[name="{key}"]').bounding_box()
        window.screenshot(path=str(OUT / f'{kind}.png'))


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    base = 'https://ad.leadink.cn/DmvTqXBpfF.php'
    page.goto(base + '/index/login', wait_until='domcontentloaded')
    page.fill('[name=username]', USERNAME)
    page.fill('[name=password]', PASSWORD)
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.locator('a[href*="gameuser?ref=addtabs"]').wait_for(state='attached')
    page.route('**/*', lambda r: r.continue_() if r.request.method in ('GET', 'HEAD', 'OPTIONS') else r.abort())
    page.goto(base + '/gameuser', wait_until='networkidle')
    page.locator('#table tbody input[type=checkbox]').first.check()
    page.locator('#toolbar .btn-edit').click()
    window = page.locator('.layui-layer-iframe').last
    frame = window.frame_locator('iframe')
    frame.locator('[name="row[username]"]').wait_for()
    frame.locator('body').evaluate('async()=>{await document.fonts.ready;await new Promise(r=>setTimeout(r,1000));}')
    frame.locator(f'.nav-tabs a[href="#{TAB_ID}"]').click()
    frame.locator('body').evaluate("id=>window.jQuery('.nav-tabs a[href=\"#'+id+'\"]').tab('show')", TAB_ID)
    capture(page, frame, window, True)
    if os.environ.get('PARITY_WINDOW_PROBE'):
        states = {'normal': window.bounding_box()}
        window.locator('.layui-layer-max').click()
        page.wait_for_timeout(500)
        states['maximized'] = window.bounding_box()
        window.locator('.layui-layer-max').click()
        page.wait_for_timeout(500)
        states['restored'] = window.bounding_box()
        window.locator('.layui-layer-min').click()
        page.wait_for_timeout(500)
        states['minimized'] = window.bounding_box()
        states['minimized_buttons'] = window.locator('.layui-layer-setwin a').evaluate_all('els=>els.map(e=>({cls:e.className,visible:!!e.getClientRects().length}))')
        window.locator('.layui-layer-max').click()
        page.wait_for_timeout(500)
        states['restored_from_minimized'] = window.bounding_box()
        (OUT / 'reference-window.json').write_text(json.dumps(states,indent=2),encoding='utf-8')
    page.close()

    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    row = dict(id=9200, username='fixture-9200', name='Fixture')
    row.update(DATA)
    page.route('**/api/v1/members?*', lambda r: r.fulfill(json={'total': 1, 'items': [row]}))
    page.route('**/api/v1/members/9200', lambda r: r.fulfill(json=row) if r.request.method == 'GET' else r.abort())
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]', USERNAME)
    page.fill('#loginForm [name=password]', PASSWORD)
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('[data-edit="9200"]').click()
    page.locator(f'[data-member-tab-button="{TAB}"]').click()
    capture(page, page.locator('#modal'), page.locator('#modal>.modal'), False)
    browser.close()

a = np.array(Image.open(OUT / 'reference.png').convert('RGB')).astype(int)
b = np.array(Image.open(OUT / 'local.png').convert('RGB')).astype(int)
assert a.shape == b.shape, (a.shape, b.shape)
delta = np.abs(a-b)
mask = delta.max(axis=2) > 10
diff = np.where(mask[..., None], np.array([255, 0, 80]), (a * .25 + 190)).clip(0, 255).astype('uint8')
Image.fromarray(diff).save(OUT / 'diff.png')
report = dict(changed_pixel_ratio=float(mask.mean()), mean_rgb=float(delta.mean()),
              threshold=10, viewport=[1920, 1080], crop_size=[a.shape[1], a.shape[0]],
              scope=('Date picker crop at 2026-09-17 12:34:56; position within editor not certified' if DATE_PICKER else f'Synthetic {TAB} tab only; no reference save or server-side business validation'),
              geometry=METRICS)
for filename, value in [('data.json', DATA), ('report.json', report)]:
    (OUT / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report))
