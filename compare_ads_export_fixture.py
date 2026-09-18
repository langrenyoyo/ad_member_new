"""Compare six real local downloads with the captured browser-only reference fixture."""
import csv
import io
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

out = Path('visual-baseline/fixtures/ads')
rows = json.loads((out/'data.json').read_text(encoding='utf-8'))['local']
results = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width':1920,'height':1080},timezone_id='Asia/Shanghai')
    page.route('**/api/v1/ads?*',lambda r:r.fulfill(json={'total':len(rows),'items':rows,'summary':{'ecpm':111.5,'coin':11.15}}))
    page.goto('http://127.0.0.1:3000/#ads')
    page.fill('#loginForm [name=username]','18532306918')
    page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('#adsSearchToggle').click()
    for kind in ['json','xml','csv','txt','doc','excel']:
        page.locator('#adsExportToggle').click()
        with page.expect_download() as event:
            page.locator(f'[data-ads-export="{kind}"]').click()
        event.value.save_as(out/f'export-local.{kind}')
        values={side:(out/f'export-{side}.{kind}').read_text(encoding='utf-8-sig') for side in ['reference','local']}
        if kind in ['csv','txt']:
            values={side:list(csv.reader(io.StringIO(value))) for side,value in values.items()}
        elif kind=='json':
            values={side:json.loads(value) for side,value in values.items()}
        elif kind=='xml':
            values={side:ET.tostring(ET.fromstring(value),encoding='unicode') for side,value in values.items()}
        results.append({'format':kind,'equal':values['reference']==values['local'],**values})
    page.locator('#adsViewToggle').click()
    page.mouse.move(0,0)
    card=page.locator('#adsTable table').evaluate("t=>({rect:t.getBoundingClientRect().toJSON(),cells:[...t.querySelectorAll('tr,td,.ads-card-title,.ads-card-value')].filter(e=>e.getClientRects().length).slice(0,12).map(e=>{const c=getComputedStyle(e);return {text:e.innerText,rect:e.getBoundingClientRect().toJSON(),font:c.font,padding:c.padding,margin:c.margin,display:c.display,width:c.width,minWidth:c.minWidth,verticalAlign:c.verticalAlign}})})")
    (out/'card-local.json').write_text(json.dumps(card,ensure_ascii=False,indent=2),encoding='utf-8')
    page.screenshot(path=str(out/'card-local.png'),clip={'x':230,'y':50,'width':1690,'height':1030})
    page.locator('#adsViewToggle').click()
    page.locator('#adsColumnsToggle').click()
    page.screenshot(path=str(out/'columns-local.png'),clip={'x':230,'y':50,'width':1690,'height':1030})
    browser.close()
(out/'export-comparison.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print([{k:v for k,v in r.items() if k in ['format','equal']} for r in results])
assert all(r['equal'] for r in results), 'See export-comparison.json'
visual=[]
for state in ['card','columns']:
    reference=Image.open(out/f'{state}-reference.png').convert('RGB')
    local=Image.open(out/f'{state}-local.png').convert('RGB')
    assert reference.size==local.size
    diff=ImageChops.difference(reference,local)
    diff.save(out/f'{state}-diff.png')
    visual.append({'state':state,'scope':'1690x1030 content area, three fixture records','mean_rgb':sum(ImageStat.Stat(diff).mean)/3,'changed_pixel_ratio':sum(max(pixel)>10 for pixel in diff.get_flattened_data())/(diff.width*diff.height)})
(out/'tools-visual.json').write_text(json.dumps(visual,indent=2),encoding='utf-8')
print(visual)
