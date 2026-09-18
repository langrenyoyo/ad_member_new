"""Identical generated lookup options; reference business writes are blocked."""
import json
import os
from pathlib import Path
from urllib.parse import parse_qs,urlparse
from PIL import Image,ImageChops,ImageStat
from playwright.sync_api import sync_playwright

kind=os.environ.get('PARITY_LOOKUP_KIND','game')
assert kind in ('game','agent')
view=os.environ.get('PARITY_LOOKUP_VIEW','members')
assert view in ('members','ads')
reference_route_name='ad' if view=='ads' else 'gameuser'
label='对照游戏' if kind=='game' else '对照代理商'
options=[{'id':(7200 if kind=='game' else 6200)+i,'name':f'{label} {i:02d}'} for i in range(12)]
def result(params,reference=False):
    query=params.get('q_word[]' if reference else 'q',[''])[0]
    items=[r for r in options if query in r['name']]
    offset=(int(params.get('pageNumber',['1'])[0])-1)*10 if reference else int(params.get('offset',['0'])[0])
    return {'list' if reference else 'items':items[offset:offset+10],'total':len(items)}
with sync_playwright() as p:
    browser=p.chromium.launch()
    ref=browser.new_page(viewport={'width':1690,'height':1030})
    base='https://ad.leadink.cn/DmvTqXBpfF.php'
    ref.goto(base+'/index/login');ref.fill('[name=username]','18532306918');ref.fill('[name=password]','123456')
    ref.locator('button[type=submit],input[type=submit]').first.click()
    ref.locator('a[href*="'+reference_route_name+'?ref=addtabs"]').first.wait_for(state='attached')
    def reference_route(route):
        r=route.request
        if '/ajax/'+kind+'List_source/' in r.url:route.fulfill(json=result(parse_qs(r.post_data or ''),True))
        elif '/'+reference_route_name+'/index?' in r.url and r.resource_type in ('xhr','fetch'):route.fulfill(json={'rows':[],'total':0,'extend':{'money1':0,'money2':0,'tixian1':0,'tixian2':0}})
        elif r.method not in ('GET','HEAD','OPTIONS'):route.abort()
        else:route.continue_()
    ref.route('**/*',reference_route)
    ref.goto(base+'/'+reference_route_name,wait_until='networkidle')
    ref.evaluate("jQuery('#table').bootstrapTable('load',{rows:[],total:0,extend:{money1:0,money2:0,tixian1:0,tixian2:0}})")
    local=browser.new_page(viewport={'width':1920,'height':1080})
    local.route('**/api/v1/'+view+'?*',lambda r:r.fulfill(json={'items':[],'total':0,'summary':{}}))
    local.route('**/api/v1/member-filter-options/'+kind+'s?*',lambda r:r.fulfill(json=result(parse_qs(urlparse(r.request.url).query))))
    local.goto('http://127.0.0.1:3000/#'+view);local.fill('[name=username]','18532306918');local.fill('[name=password]','123456')
    local.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    inputs=[ref.locator('[name="'+kind+'.name_text"]'),local.locator('[data-'+('ads' if view=='ads' else 'member')+'-lookup='+kind+'_name]')]
    for input in inputs:input.click()
    for page in (ref,local):page.locator('.sp_result_area:visible .sp_results li').nth(9).wait_for()
    for state in ('first','last','empty'):
        if state=='last':
            for page,input in zip((ref,local),inputs):
                input.press('ArrowRight')
                page.locator('.sp_result_area:visible .sp_results li[pkey="'+str(options[-1]['id'])+'"]').wait_for()
        if state=='empty':
            for page,input in zip((ref,local),inputs):
                input.fill('no-matching-fixture');input.press('x');input.press('Backspace')
                page.locator('.sp_result_area:visible .sp_results li[pkey]').first.wait_for(state='detached')
        out=Path('visual-baseline/fixtures/'+('ads' if view=='ads' else 'member')+'-lookup-'+('agent-' if kind=='agent' else '')+state);out.mkdir(parents=True,exist_ok=True)
        layout={}
        for name,page in [('reference',ref),('local',local)]:
            panel=page.locator('.sp_result_area:visible');panel.wait_for()
            ids=panel.locator('li[pkey]').evaluate_all('els=>els.map(e=>Number(e.getAttribute("pkey")))')
            expected=options[:10] if state=='first' else options[10:] if state=='last' else []
            assert ids==[row['id'] for row in expected],(kind,state,name,ids)
            page.evaluate('document.fonts.ready');page.mouse.move(0,0)
            layout[name]=panel.evaluate('''e=>({rect:e.getBoundingClientRect().toJSON(),text:e.innerText,styles:[e,...e.querySelectorAll('ul,li,a')].map(n=>{const s=getComputedStyle(n);return {tag:n.tagName,cls:n.className,font:s.font,padding:s.padding,height:n.getBoundingClientRect().height,color:s.color};})})''')
            panel.screenshot(path=str(out/(name+'.png')))
        (out/'layout.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding='utf-8')
        assert layout['local']['text']==layout['reference']['text'],state
        for dimension in ('width','height'):
            assert layout['local']['rect'][dimension]==layout['reference']['rect'][dimension],(state,dimension,layout)
        if kind=='agent' or view=='ads':
            assert layout['local']['rect']['x']-230==layout['reference']['rect']['x']
            assert layout['local']['rect']['y']-50==layout['reference']['rect']['y']
        (out/'data.json').write_text(json.dumps(options,ensure_ascii=False,indent=2),encoding='utf-8')
        a=Image.open(out/'reference.png').convert('RGB');b=Image.open(out/'local.png').convert('RGB')
        size=(max(a.width,b.width),max(a.height,b.height))
        canvases=[]
        for im in (a,b):
            canvas=Image.new('RGB',size,'white');canvas.paste(im,(0,0));canvases.append(canvas)
        diff=ImageChops.difference(*canvases);diff.save(out/'diff.png')
        report={'scope':'Lookup panel only, '+state+'; white padding for unequal image sizes; server scope unverified','reference_size':a.size,'local_size':b.size,'mean_rgb':sum(ImageStat.Stat(diff).mean)/3,'changed_pixel_ratio':sum(max(v)>10 for v in diff.getdata())/(size[0]*size[1])}
        (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(state,report)
    browser.close()
