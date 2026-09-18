"""Capture the same synthetic ledger as inspect_coin_log_parity.py locally."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlparse
from PIL import Image,ImageChops
from playwright.sync_api import sync_playwright

OUT=Path('visual-baseline/fixtures/coin-logs')
source=json.loads((OUT/'fixture-rows.json').read_text(encoding='utf-8'))
rows=[{**row,'username':row['user']['username'],'game_name':row['game']['name'],'agent_name':row['agent']['name'],
       'game_ad_status':row['agent']['game_ad_status'],'created_at':datetime.fromtimestamp(row['create_time'],timezone.utc).isoformat()} for row in source]
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    fixture_state={'many':False}
    def fixture(route):
        path=urlparse(route.request.url).path.split('/api/')[-1].removeprefix('v1/')
        if path=='auth/login':route.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}});return
        if route.request.method!='GET':route.abort();return
        items=[{**rows[i%3],'id':9100+i} for i in range(10)] if fixture_state['many'] else rows
        route.fulfill(json={'items':items,'total':225 if fixture_state['many'] else 3,'summary':{'change':17.5}} if path=='coin-logs' else {'items':[],'total':0})
    page.route('**/api/**',fixture)
    page.goto('http://127.0.0.1:3000/#coin-logs')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('#coinTable tbody tr').first.wait_for();page.evaluate('document.fonts.ready')
    assert page.locator('#coinError').inner_text()=='',page.locator('#coinError').inner_text()
    page.locator('.coin-panel').screenshot(path=str(OUT/'local.png'))
    report=page.locator('.coin-panel').evaluate('''el=>Object.fromEntries(['#coinFilters','.ads-toolbar','#coinTable table','#coinPagination'].map(s=>{const r=el.querySelector(s).getBoundingClientRect(),p=el.getBoundingClientRect();return [s,{x:r.x-p.x,y:r.y-p.y,width:r.width,height:r.height}]}))''')
    report['columns']=page.locator('#coinTable th').evaluate_all('els=>els.map(n=>{const c=getComputedStyle(n.firstElementChild||n);return {field:n.dataset.field,width:n.getBoundingClientRect().width,innerFont:c.font,innerPadding:c.padding}})')
    assert not errors,errors
    exports=[]
    for kind in ['json','xml','csv','txt','doc','excel']:
        page.locator('.game-user-export summary').click()
        with page.expect_download() as download:page.locator('[data-export='+kind+']').click()
        download.value.save_as(str(OUT/('export-local.'+kind)))
        reference=OUT/('export-reference.'+kind)
        if not reference.exists():continue
        values={side:(OUT/('export-'+side+'.'+kind)).read_text(encoding='utf-8-sig') for side in ['reference','local']}
        result={'format':kind}
        if kind=='json':values={side:json.loads(value) for side,value in values.items()}
        if kind=='xml':
            for side,value in list(values.items()):
                try:values[side]=ET.tostring(ET.fromstring(value),encoding='unicode')
                except ET.ParseError as error:result[side+'_parse_error']=str(error)
        result['equal']=values['reference']==values['local'];exports.append(result)
    report['exports']=exports
    page.locator('[data-action=cards]').click()
    page.locator('.coin-panel').screenshot(path=str(OUT/'cards-local.png'))
    page.locator('[data-action=cards]').click()
    fixture_state['many']=True
    with page.expect_response(lambda response:'/coin-logs?' in response.url):page.locator('#coinRefresh').click()
    page.wait_for_function('document.querySelector("#coinTable tbody").rows.length===10')
    page.locator('#coinPagination').screenshot(path=str(OUT/'pagination-local.png'))
    browser.close()
ref=Image.open(OUT/'reference.png').convert('RGB');local=Image.open(OUT/'local.png').convert('RGB')
report['reference_size']=ref.size;report['local_size']=local.size
canvas_size=(max(ref.width,local.width),max(ref.height,local.height))
a=Image.new('RGB',canvas_size,'white');a.paste(ref);b=Image.new('RGB',canvas_size,'white');b.paste(local)
diff=ImageChops.difference(a,b)
report['changed_pixels_percent']=round(sum(max(pixel)>16 for pixel in diff.get_flattened_data())/(canvas_size[0]*canvas_size[1])*100,4)
diff.save(OUT/'diff.png')
for view in ['cards','pagination']:
    a=Image.open(OUT/(view+'-reference.png')).convert('RGB');b=Image.open(OUT/(view+'-local.png')).convert('RGB')
    report[view]={'reference_size':a.size,'local_size':b.size}
    if a.size==b.size:
        diff=ImageChops.difference(a,b);diff.save(OUT/(view+'-diff.png'))
        report[view]['changed_pixels_percent']=round(sum(max(pixel)>16 for pixel in diff.get_flattened_data())/(a.width*a.height)*100,4)
(OUT/'comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({key:report[key] for key in ['changed_pixels_percent','cards','pagination','exports']}))
