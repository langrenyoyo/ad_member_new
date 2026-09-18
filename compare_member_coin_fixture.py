"""Compare current local coin dialog to the separately captured read-only reference."""
import json,shutil
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
from playwright.sync_api import sync_playwright

out=Path('visual-baseline/fixtures/member-coin');out.mkdir(parents=True,exist_ok=True)
reference=Path('visual-baseline/reference-verified/member-coin-dialog')
shutil.copyfile(reference/'reference.png',out/'reference.png')
row={'id':9200,'username':'金币会员','coin':12.5,'freeze_coin':3,'status':1}
(out/'data.json').write_text(json.dumps({'coin':12.5,'freeze_coin':3}),encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080})
    page.route('**/api/v1/members?*',lambda r:r.fulfill(json={'total':1,'items':[row]}))
    page.route('**/api/v1/members/9200',lambda r:r.fulfill(json=row))
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('[data-coin]').click()
    page.wait_for_function("!document.querySelector('#memberCoinDialog [type=submit]').disabled")
    page.evaluate('document.activeElement.blur()');page.evaluate('document.fonts.ready')
    dialog=page.locator('#memberCoinDialog')
    rect=dialog.bounding_box();assert rect['width']==800 and rect['height']==600
    assert dialog.locator('[name=coin]').input_value()=='12.5' and dialog.locator('[name=freeze_coin]').input_value()=='3'
    dialog.screenshot(path=str(out/'local.png'))
    (out/'layout.json').write_text(json.dumps(rect,indent=2),encoding='utf-8')
    dialog.get_by_role('button',name='最小化',exact=True).click()
    page.evaluate('document.activeElement.blur()')
    dialog.screenshot(path=str(out/'local-minimized.png'))
    shutil.copyfile(reference/'minimized.png',out/'reference-minimized.png')
    browser.close()
a=Image.open(out/'reference.png').convert('RGB');b=Image.open(out/'local.png').convert('RGB')
assert a.size==b.size
d=ImageChops.difference(a,b);d.save(out/'diff.png')
report={'scope':'coin dialog only at 800x600, same two synthetic values; reference form read-only; no submission parity certification','mean_rgb':sum(ImageStat.Stat(d).mean)/3,'changed_pixel_ratio':sum(max(pixel)>10 for pixel in d.getdata())/(a.width*a.height)}
mini_a=Image.open(out/'reference-minimized.png').convert('RGB');mini_b=Image.open(out/'local-minimized.png').convert('RGB')
assert mini_a.size==mini_b.size==(180,45)
mini_diff=ImageChops.difference(mini_a,mini_b);mini_diff.save(out/'diff-minimized.png')
report['minimized_changed_pixel_ratio']=sum(max(pixel)>10 for pixel in mini_diff.getdata())/(180*45)
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report)
