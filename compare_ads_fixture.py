"""Compare live ad-list rendering; fixtures are browser-only and writes are blocked."""
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops, ImageStat

out=Path('visual-baseline/fixtures/ads');out.mkdir(parents=True,exist_ok=True)
rows=[dict(id=9200+i,parent_id=8100,parent_payment_name='上级姓名',user_id=8200+i,user_account=f'对照账号{i}',receive_name='测试姓名',game_name='对照游戏',agent_name='对照主体',game_id=7100,agent_id=6100,ecpm=[0,12.5,99][i],coin=[0,1.25,9.9][i],estimate_income=[0,1.25,9.9][i],is_lottery=i%2,is_rw=(i+1)%2,is_type=i%2,is_fu=i%2,fu_type=i+1,is_look=i%2,reward_type=['发放','领取','发放'][i],ad_type=['激励','副广','激励'][i],status=['失败','成功','失败'][i],sub_ad_type=['开屏','Banner','插屏'][i],ad_network_platform_name='测试平台',watched_at='2026-09-16T00:00:00Z',ad_code='code',request_id=f'REQ-{i}',trans_id=f'TRANS-{i}') for i in range(3)]
refs=[{**r,'user':{'parent_id':r['parent_id'],'username':r['user_account']},'game':{'name':r['game_name']},'agent':{'name':r['agent_name']},'receive_name_parent':r['parent_payment_name'],'pre_ecpm':r['ecpm'],'ad_network_rit_id':r['ad_code'],'create_time':1789516800} for r in rows]
payload={'total':3,'rows':refs,'extend':{'money1':111.5,'money2':11.15,'tixian1':0,'tixian2':0}}
(out/'data.json').write_text(json.dumps({'local':rows,'reference':refs},ensure_ascii=False,indent=2),encoding='utf-8')
report={'comparison_valid':False}
(out/'report.json').write_text(json.dumps(report),encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch()
    ref=browser.new_page(viewport={'width':1690,'height':1030},timezone_id='Asia/Shanghai')
    ref.set_default_timeout(15000)
    def reference(route):
        req=route.request;path=urlparse(req.url).path
        if path.endswith('/ad/index') and req.resource_type in ('xhr','fetch'):return route.fulfill(json=payload)
        if req.method not in ('GET','HEAD') and not path.endswith('/index/login'):return route.abort()
        route.continue_()
    ref.route('**/*',reference)
    base='https://ad.leadink.cn/DmvTqXBpfF.php'
    ref.goto(base+'/index/login',wait_until='domcontentloaded')
    ref.fill('[name=username]','18532306918');ref.fill('[name=password]','123456')
    ref.locator('button[type=submit],input[type=submit]').first.click()
    ref.locator('a[href*="ad?ref=addtabs"]').first.wait_for(state='attached')
    ref.goto(base+'/ad',wait_until='networkidle')
    ref.wait_for_function("window.jQuery && jQuery('#table').data('bootstrap.table')")
    ref.locator('button[name=commonSearch]').click()
    ref.locator('input[name=user_id]').wait_for(state='hidden')
    ref.evaluate("data=>{jQuery('#table').bootstrapTable('load',data);jQuery('#table').bootstrapTable('hideLoading');Object.entries(data.extend).forEach(([k,v])=>jQuery('#'+k).text(v));}",payload)
    assert ref.evaluate("jQuery('#table').bootstrapTable('getData').map(r=>r.id)")==[r['id'] for r in rows]
    local=browser.new_page(viewport={'width':1920,'height':1080},timezone_id='Asia/Shanghai')
    local.route('**/api/v1/ads?*',lambda route:route.fulfill(json={'total':3,'items':rows,'summary':{'ecpm':111.5,'coin':11.15,'withdrawn':0,'pending_withdrawal':0}}))
    local.goto('http://127.0.0.1:3000/#ads')
    local.fill('#loginForm [name=username]','18532306918');local.fill('#loginForm [name=password]','123456')
    local.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    local.locator('#adsSearchToggle').click()
    local.locator('#adsFilters').wait_for(state='hidden')
    assert local.locator('#adsTable tbody tr').count()==3
    layout={}
    for name,page,selector in [('reference',ref,'#table'),('local',local,'#adsTable table')]:
        page.mouse.move(0,0)
        page.evaluate('document.fonts.ready')
        layout[name]=page.locator(selector).evaluate("""t=>({rect:t.getBoundingClientRect().toJSON(),styles:[...t.querySelectorAll('th,td')].filter(e=>e.getClientRects().length).map(e=>{const c=getComputedStyle(e);return {text:e.innerText,color:c.color,borderTop:c.borderTop,borderLeft:c.borderLeft,font:c.font,rect:e.getBoundingClientRect().toJSON()}}),headers:[...t.querySelectorAll('th')].filter(e=>e.getClientRects().length).map(e=>e.innerText),rows:[...t.querySelectorAll('tbody tr')].map(r=>({height:r.getBoundingClientRect().height,cells:[...r.cells].filter(c=>c.getClientRects().length).map(c=>c.innerText)}))})""")
        page.screenshot(path=str(out/(name+'.png')),**({} if name=='reference' else {'clip':{'x':230,'y':50,'width':1690,'height':1030}}))
    (out/'layout.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding='utf-8')
    assert [r['cells'] for r in layout['reference']['rows']]==[r['cells'] for r in layout['local']['rows']], 'Displayed field values differ'
    assert layout['reference']['rect']['height']==layout['local']['rect']['height']==183
    assert layout['reference']['rect']['y']==layout['local']['rect']['y']-50
    assert all(r['height']==47 for v in layout.values() for r in v['rows'])
    # Compare the open date picker with an identical explicit range.
    ref.locator('button[name=commonSearch]').click()
    local.locator('#adsSearchToggle').click()
    ref.locator('input[name=create_time]').click(); ref.locator('.daterangepicker:visible').wait_for(); ref.locator('.daterangepicker:visible .ranges li').last.click()
    local.locator('#watchedRange').click(); local.locator('.daterangepicker:visible').wait_for(); local.locator('.daterangepicker:visible .ranges li').last.click()
    for page, selector in [(ref,'input[name=create_time]'),(local,'#watchedRange')]:
        page.evaluate("selector=>{const picker=jQuery(selector).data('daterangepicker');picker.setStartDate('2026-09-03 00:00:00');picker.setEndDate('2026-09-17 23:59:59');picker.updateView();picker.updateCalendars();}",selector)
    def picker_info(page):
        return page.locator('.daterangepicker:visible').evaluate("""box=>{const sels=['.daterangepicker','.ranges','.ranges li','.calendar','.calendar-table','.calendar-table th','.calendar-table td'];return {rect:box.getBoundingClientRect().toJSON(),styles:sels.map(s=>{const e=s==='.daterangepicker'?box:box.querySelector(s);if(!e)return {selector:s};const c=getComputedStyle(e);return {selector:s,rect:e.getBoundingClientRect().toJSON(),font:c.font,padding:c.padding,border:c.border,color:c.color,background:c.backgroundColor}})}}""")
    calendar_layout={'reference':picker_info(ref),'local':picker_info(local)}
    ref.screenshot(path=str(out/'date-picker-reference.png'))
    local.screenshot(path=str(out/'date-picker-local.png'),clip={'x':230,'y':50,'width':1690,'height':1030})
    (out/'date-picker-layout.json').write_text(json.dumps(calendar_layout,ensure_ascii=False,indent=2),encoding='utf-8')
    assert abs(calendar_layout['reference']['rect']['width']-calendar_layout['local']['rect']['width']) <= 4
    assert abs(calendar_layout['reference']['rect']['height']-calendar_layout['local']['rect']['height']) <= 6
    ref.locator('body').press('Escape'); local.locator('body').press('Escape')
    ref.locator('button[name=commonSearch]').click()
    local.locator('#adsSearchToggle').click()
    sort_requests=[]
    for field in ['pre_ecpm','estimate_income','ad_network_platform_name','create_time','request_id']:
        for direction in ['desc','asc']:
            with ref.expect_request(lambda r:'/ad/index?' in r.url) as event:
                ref.locator(f'#table th[data-field="{field}"] .th-inner').click()
            reference_query=parse_qs(urlparse(event.value.url).query)
            with local.expect_request(lambda r:'/api/v1/ads?' in r.url) as event:
                local.locator(f'[data-ads-sort="{field}"]').click()
            local_query=parse_qs(urlparse(event.value.url).query)
            assert reference_query['sort']==local_query['sort']==[field]
            assert reference_query['order']==local_query['order']==[direction], (field,direction,reference_query['order'],local_query['order'])
            assert local_query['offset']==['0']
            sort_requests.append({'field':field,'direction':direction,'reference':reference_query,'local':local_query})
    (out/'sort-requests.json').write_text(json.dumps(sort_requests,ensure_ascii=False,indent=2),encoding='utf-8')
    searches=[]
    ref.evaluate("jQuery('#table').bootstrapTable('showColumn','agent.name')")
    local.locator('#adsColumnsToggle').click()
    local.locator('[data-ads-column="agent_name"]').check()
    local.locator('#adsColumnsToggle').click()
    for field,reference_field in [('parent_id','user.parent_id'),('user_id','user_id'),('game_name','game.name'),('agent_name','agent.name'),('is_fu','is_fu'),('fu_type','fu_type'),('is_look','is_look')]:
        with ref.expect_request(lambda r:'/ad/index?' in r.url) as event:
            ref.locator(f'#table tbody tr[data-index="0"] .searchit[data-field="{reference_field}"]').click()
        reference_query=parse_qs(urlparse(event.value.url).query)
        reference_filter=json.loads(reference_query['filter'][0])
        reference_operate=json.loads(reference_query['op'][0])
        with local.expect_request(lambda r:'/api/v1/ads?' in r.url) as event:
            local.locator(f'#adsTable tbody tr').first.locator(f'[data-ads-search="{field}"]').click()
        local_query=parse_qs(urlparse(event.value.url).query)
        assert str(reference_filter[reference_field])==local_query[field][0]==str(rows[0][field])
        assert reference_operate[reference_field]==('LIKE' if field=='agent_name' else '=')
        assert local_query['offset']==['0']
        if field in ('parent_id','user_id','is_fu','fu_type','is_look'):
            assert local.locator(f'#adsFilters [name="{field}"]').input_value()==str(rows[0][field])
        else:
            select_field='game_id' if field=='game_name' else 'agent_id'
            assert local.locator(f'#adsFilters [data-ads-lookup="{field}"]').input_value()==str(rows[0][field])
            assert local.locator(f'#adsFilters input[type=hidden][name="{field}"]').input_value()==str(rows[0][field])
        searches.append({'field':field,'reference_filter':reference_filter,'reference_operate':reference_operate,'local_query':local_query})
    (out/'searches.json').write_text(json.dumps(searches,ensure_ascii=False,indent=2),encoding='utf-8')
    ref.locator('button[name=commonSearch]').click()
    local.locator('#adsSearchToggle').click()
    assert ref.locator('input[name=create_time]').input_value()==local.locator('#watchedRange').input_value()
    date_checks=[]
    for label in ['昨天','最近7天','本月','上月']:
        for page,selector in [(ref,'input[name=create_time]'),(local,'#watchedRange')]:
            page.locator(selector).click()
            page.locator('.daterangepicker:visible .ranges li').filter(has_text=label).click()
        value=ref.locator('input[name=create_time]').input_value()
        assert value==local.locator('#watchedRange').input_value(), label
        with local.expect_request(lambda r:'/api/v1/ads?' in r.url) as event:
            local.locator('#adsFilters [type=submit]').click()
        query=parse_qs(urlparse(event.value.url).query)
        date_checks.append({'range':label,'reference':value,'local':value,'request':query})
    (out/'date-requests.json').write_text(json.dumps(date_checks,ensure_ascii=False,indent=2),encoding='utf-8')
    browser.close()
a=Image.open(out/'reference.png').convert('RGB');b=Image.open(out/'local.png').convert('RGB');assert a.size==b.size
d=ImageChops.difference(a,b);d.save(out/'diff.png')
report.update(comparison_valid=True,scope='3 same ad records, collapsed filters, content area only',mean_rgb=sum(ImageStat.Stat(d).mean)/3,changed_pixel_ratio=sum(max(px)>10 for px in d.getdata())/(a.width*a.height))
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report)
