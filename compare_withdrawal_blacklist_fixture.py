"""Compare a local synthetic blacklist with the stored sanitized reference."""
import json
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

OUT = Path('visual-baseline/verified')
rows = [{'id':9000+i, 'receive_name':'fixture '+str(i), 'receive_tel':'001234'+str(i),
         'status':1-i, 'created_at':'2026-09-18T00:00:00Z',
         'updated_at':'2026-09-18T00:00:00Z'} for i in range(2)]
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width':1920,'height':1080})
    def fixture(route):
        path = urlparse(route.request.url).path.split('/api/')[-1].removeprefix('v1/')
        if path == 'auth/login':
            route.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}})
        elif route.request.method != 'GET':
            route.abort()
        else:
            route.fulfill(json={'items':rows,'total':2} if path == 'withdrawal-blacklist' else {'items':[],'total':0})
    page.route('**/api/**',fixture)
    page.goto('http://127.0.0.1:3000/#withdrawals')
    page.fill('#loginForm [name=username]','fixture')
    page.fill('#loginForm [name=password]','fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('#withdrawalBlacklist').click()
    dialog = page.locator('.withdrawal-blacklist-dialog')
    dialog.locator('tbody tr').first.wait_for()
    page.evaluate('document.fonts.ready')
    dialog.screenshot(path=str(OUT/'withdrawal-blacklist-fixture.png'))
    report = dialog.evaluate('''el=>Object.fromEntries(['header','main','.ads-filters','.ads-toolbar','.ads-table','.game-user-pagination','[data-action=cards]','.game-user-columns summary','.game-user-export summary','.blacklist-toggle .shell-icon'].map(s=>{
      const n=el.querySelector(s),r=n.getBoundingClientRect(),d=el.getBoundingClientRect();
      return [s,{x:r.x-d.x,y:r.y-d.y,width:r.width,height:r.height}];}))''')
    browser.close()
reference = Image.open('visual-baseline/reference-verified/withdrawal-blacklist-fixture.png').convert('RGB')
local = Image.open(OUT/'withdrawal-blacklist-fixture.png').convert('RGB')
assert reference.size == local.size == (800,600)
diff = ImageChops.difference(reference,local)
report['changed_pixels_percent'] = round(sum(max(pixel)>16 for pixel in diff.get_flattened_data())/(800*600)*100,4)
diff.save(OUT/'withdrawal-blacklist-diff.png')
(OUT/'withdrawal-blacklist-comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
