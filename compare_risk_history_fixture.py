"""Risk history screenshot/export comparison with synthetic read-only responses."""
import json
import xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from PIL import Image,ImageChops
from playwright.sync_api import sync_playwright

OUT=Path('visual-baseline/fixtures/risk-history')
source=json.loads((OUT/'fixture-rows.json').read_text(encoding='utf-8'))
rows=[{**row,'username':row['user']['username'],'parent_id':row['user']['parent_id'],
       'game_name':row['game']['name'],'agent_name':row['agent']['name'],
       'created_at':datetime.fromtimestamp(row['create_time'],timezone.utc).isoformat()} for row in source]
report={}
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080})
    errors=[];mode={'many':False};page.on('pageerror',lambda error:errors.append(str(error)))
    def fixture(route):
        request=route.request;url=urlparse(request.url);path=url.path.split('/api/')[-1].removeprefix('v1/');q=parse_qs(url.query)
        if path=='auth/login':route.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}});return
        assert request.method=='GET',request.url
        items=[{**rows[i%3],'id':9100+i} for i in range(225)] if mode['many'] else rows
        offset=int(q.get('offset',['0'])[0]);limit=int(q.get('limit',['10'])[0])
        route.fulfill(json={'items':items[offset:offset+limit],'total':len(items)} if path=='risk/history' else {'items':[],'total':0})
    page.route('**/api/**',fixture)
    page.goto('http://127.0.0.1:3000/#risk-history')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture');page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('#riskHistoryTable tbody tr').first.wait_for();page.evaluate('document.fonts.ready')
    assert page.locator('#riskHistoryError').inner_text()==''
    report['geometry']=page.locator('#riskHistoryTable th').evaluate_all('nodes=>nodes.map(n=>({field:n.dataset.field,width:n.getBoundingClientRect().width}))')
    page.locator('.risk-history-panel').screenshot(path=str(OUT/'local.png'))
    page.locator('#riskHistorySearch').click();page.locator('.risk-history-panel').screenshot(path=str(OUT/'collapsed-local.png'))
    exports=[]
    for kind in ['json','xml','csv','txt','doc','excel']:
        page.locator('.game-user-export summary').click()
        with page.expect_download() as download:page.locator('[data-export='+kind+']').click()
        download.value.save_as(str(OUT/('export-local.'+kind)))
        values={side:(OUT/('export-'+side+'.'+kind)).read_text(encoding='utf-8-sig') for side in ['reference','local']};result={'format':kind}
        if kind=='json':values={side:json.loads(value) for side,value in values.items()}
        if kind=='xml':
            for side,value in list(values.items()):
                try:values[side]=ET.tostring(ET.fromstring(value),encoding='unicode')
                except ET.ParseError as error:result[side+'_parse_error']=str(error)
        result['equal']=values['reference']==values['local'];exports.append(result)
    report['exports']=exports
    page.locator('#riskHistorySearch').click();page.locator('[data-action=cards]').click()
    page.locator('.risk-history-panel').screenshot(path=str(OUT/'cards-local.png'))
    page.locator('[data-action=cards]').click();mode['many']=True;page.locator('#riskHistoryRefresh').click()
    page.wait_for_function('document.querySelector("#riskHistoryPagination").textContent.includes("225")')
    page.locator('#riskHistoryPagination').screenshot(path=str(OUT/'pagination-local.png'))
    assert not errors,errors;browser.close()
for mode in ['','collapsed-','cards-','pagination-']:
    reference=Image.open(OUT/(mode+'reference.png')).convert('RGB');local=Image.open(OUT/(mode+'local.png')).convert('RGB')
    size=(max(reference.width,local.width),max(reference.height,local.height))
    a=Image.new('RGB',size,'white');a.paste(reference);b=Image.new('RGB',size,'white');b.paste(local)
    diff=ImageChops.difference(a,b);diff.save(OUT/(mode+'diff.png'))
    report[mode or 'table']={'reference_size':reference.size,'local_size':local.size,
      'changed_pixels_percent':round(sum(max(pixel)>16 for pixel in diff.get_flattened_data())/(size[0]*size[1])*100,4)}
(OUT/'comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({key:value for key,value in report.items() if key!='geometry'}))
