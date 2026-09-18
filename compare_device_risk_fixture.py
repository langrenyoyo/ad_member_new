"""Local device risk comparison with sanitized reference fixtures."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlparse
from PIL import Image,ImageChops
from playwright.sync_api import sync_playwright

OUT=Path('visual-baseline/fixtures/device-risk')
source=json.loads((OUT/'fixture-rows.json').read_text(encoding='utf-8'))
rows=[{**row,'game_name':row['game']['name'],'agent_name':row['agent']['name'],
       'created_at':datetime.fromtimestamp(row['create_time'],timezone.utc).isoformat(),
       'last_login_time':datetime.fromtimestamp(row['last_login_time'],timezone.utc).isoformat()} for row in source]
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    def fixture(route):
        request=route.request;path=urlparse(request.url).path.split('/api/')[-1].removeprefix('v1/')
        if path=='auth/login':route.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}});return
        if request.method!='GET':route.abort();return
        route.fulfill(json={'items':rows,'total':3} if path=='risk/devices' else {'items':[],'total':0})
    page.route('**/api/**',fixture)
    page.goto('http://127.0.0.1:3000/#risk-devices')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture');page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('#whitelistTable tbody tr').first.wait_for();page.evaluate('document.fonts.ready')
    assert page.locator('#whitelistError').inner_text()==''
    page.locator('.whitelist-panel').screenshot(path=str(OUT/'local.png'))
    geometry=page.locator('#whitelistTable tr').evaluate_all("nodes=>nodes.map(n=>[...n.children].map(c=>({width:c.getBoundingClientRect().width,height:c.getBoundingClientRect().height})))")
    controls=page.locator('#whitelistTable tbody tr:first-child input,#whitelistTable tbody tr:first-child button,#whitelistTable tbody tr:first-child .white-toggle i').evaluate_all("nodes=>nodes.map(n=>{const c=getComputedStyle(n),r=n.getBoundingClientRect();return {html:n.outerHTML,font:c.font,color:c.color,display:c.display,verticalAlign:c.verticalAlign,margin:c.margin,padding:c.padding,width:r.width,height:r.height}})")
    page.locator('#whitelistSearch').click();page.locator('.whitelist-panel').screenshot(path=str(OUT/'expanded-local.png'))
    page.locator('[data-action=cards]').click();page.locator('.whitelist-panel').screenshot(path=str(OUT/'cards-local.png'))
    (OUT/'local-geometry.json').write_text(json.dumps({'geometry':geometry,'control_styles':controls,'card_geometry':page.locator('#whitelistTable article:first-child>div').evaluate_all("nodes=>nodes.filter(n=>!n.hidden).map(n=>({html:n.innerHTML,height:n.getBoundingClientRect().height,lineHeight:getComputedStyle(n).lineHeight}))")},indent=2),encoding='utf-8')
    page.locator('[data-action=cards]').click()
    for selected in (False,True):
        if selected:page.locator('[data-white-select]').first.check()
        for kind in ['json','xml','csv','txt','doc','excel']:
            page.locator('.game-user-export summary').click()
            with page.expect_download() as download:page.locator('[data-export='+kind+']').click()
            download.value.save_as(str(OUT/('export-'+('selected-' if selected else '')+'local.'+kind)))
    assert not errors,errors
    browser.close()
report={}
exports=[]
for selected in (False,True):
    for kind in ['json','xml','csv','txt','doc','excel']:
        values={side:(OUT/('export-'+('selected-' if selected else '')+side+'.'+kind)).read_text(encoding='utf-8-sig') for side in ['reference','local']}
        result={'format':kind,'selected':selected}
        if kind=='json':values={side:json.loads(value) for side,value in values.items()}
        if kind=='xml':
            for side,value in list(values.items()):
                try:values[side]=ET.tostring(ET.fromstring(value),encoding='unicode')
                except ET.ParseError as error:result[side+'_parse_error']=str(error)
        result['equal']=values['reference']==values['local'];exports.append(result)
report['exports']=exports
for mode in ['','expanded-','cards-']:
    reference=Image.open(OUT/(mode+'reference.png')).convert('RGB');local=Image.open(OUT/(mode+'local.png')).convert('RGB')
    size=(max(reference.width,local.width),max(reference.height,local.height))
    a=Image.new('RGB',size,'white');a.paste(reference);b=Image.new('RGB',size,'white');b.paste(local)
    diff=ImageChops.difference(a,b);diff.save(OUT/(mode+'diff.png'))
    report[mode or 'table']={'reference_size':reference.size,'local_size':local.size,
      'changed_pixels_percent':round(sum(max(pixel)>16 for pixel in diff.get_flattened_data())/(size[0]*size[1])*100,4)}
(OUT/'comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
