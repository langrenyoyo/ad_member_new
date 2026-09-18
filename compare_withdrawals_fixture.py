"""Read-only reference/local withdrawal comparison using browser fixtures."""
import json
from pathlib import Path
from urllib.parse import parse_qs,urlparse
from PIL import Image,ImageChops,ImageStat
from playwright.sync_api import sync_playwright

out=Path('visual-baseline/fixtures/withdrawals');out.mkdir(parents=True,exist_ok=True)
rows=[dict(id=9100+i,user_id=8100+i,username=f'对照账号{i}',vip=i,parent_name='上级甲',game_id=7100,game_name='对照游戏',agent_id=6100,agent_name='对照主体',name='测试会员',good_name='测试商品',exchange_value=[125,0,1000][i],device_manufacturer='测试机型',receive_name='测试收件人',receive_tel='13800000000',exchange_type=i,status=[0,1,2][i],plan_status=i,sub_msg='原因 <>&' if i==2 else '',check_status_txt='正常',created_at='2026-09-16T00:00:00Z',updated_at='2026-09-16T00:00:00Z') for i in range(3)]
ref_rows=[{**r,'status':4 if r['status']==2 else r['status'],'user':{'id':r['user_id'],'username':r['username'],'vip':r['vip'],'parent_name':r['parent_name'],'name':r['name'],'parent_id':0,'is_true':0},'game':{'name':r['game_name']},'agent':{'name':r['agent_name']},'good':{'name':r['good_name']},'create_time':1789516800,'update_time':1789516800} for r in rows]
(out/'data.json').write_text(json.dumps({'local':rows,'reference':ref_rows},ensure_ascii=False,indent=2),encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch();ref=browser.new_page(viewport={'width':1690,'height':1030})
    base='https://ad.leadink.cn/DmvTqXBpfF.php'
    ref.goto(base+'/index/login',wait_until='domcontentloaded')
    ref.fill('[name=username]','18532306918');ref.fill('[name=password]','123456')
    ref.locator('button[type=submit],input[type=submit]').first.click()
    ref.locator('a[href*="tixian?ref=addtabs"]').wait_for(state='attached')
    ref.route('**/tixian/index?*',lambda route:route.fulfill(json={'total':3,'rows':ref_rows}) if route.request.resource_type in ['xhr','fetch'] else route.continue_())
    ref.goto(base+'/tixian',wait_until='networkidle')
    ref.wait_for_function("window.jQuery && jQuery('#table').data('bootstrap.table')")
    ref.evaluate("rows=>jQuery('#table').bootstrapTable('load',{total:rows.length,rows})",ref_rows)
    ref.locator('button[name=commonSearch]').click()
    ref.locator('input[name=user_id]').wait_for(state='hidden')
    ref.wait_for_load_state('networkidle')
    ref.evaluate("rows=>{jQuery('#table').bootstrapTable('load',{total:rows.length,rows});jQuery('#table').bootstrapTable('hideLoading');}",ref_rows)
    assert ref.locator('#table tbody tr[data-index]').count()==3
    ref.evaluate('document.fonts.ready');ref.mouse.move(0,0);ref.screenshot(path=str(out/'reference.png'))
    local=browser.new_page(viewport={'width':1920,'height':1080})
    local.route('**/api/v1/withdrawals?*',lambda route:route.fulfill(json={'total':3,'items':rows}))
    local.goto('http://127.0.0.1:3000/#withdrawals')
    local.fill('[name=username]','18532306918');local.fill('[name=password]','123456')
    local.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    local.locator('#reviewSearchToggle').click();local.locator('#reviewFilters').wait_for(state='hidden')
    local.evaluate('document.fonts.ready');local.mouse.move(0,0);local.screenshot(path=str(out/'local.png'),clip={'x':230,'y':50,'width':1690,'height':1030})
    layout={}
    for name,page,selectors in [('reference',ref,['.panel','#table','.fixed-table-toolbar','tbody tr']),('local',local,['.withdrawal-panel','.ads-table','.withdrawal-toolbar','tbody tr'])]:
        layout[name+'ActionHTML']=page.locator(selectors[1]+' tbody tr').first.locator('td').evaluate_all('''cells=>cells.map((c,i)=>({index:i,text:c.textContent.trim(),html:c.innerHTML}))''')
        layout[name]=page.evaluate("sels=>sels.map(s=>({selector:s,rect:document.querySelector(s)?.getBoundingClientRect().toJSON()}))",selectors)
        layout[name+'Cells']=page.locator(selectors[1]).evaluate('''e=>[...e.querySelectorAll('thead th,thead th>*,tbody tr:first-child td')].filter(n=>n.getClientRects().length).map(n=>{const s=getComputedStyle(n);return {tag:n.tagName,field:n.dataset.field||n.dataset.reviewCell,text:n.textContent.trim(),rect:n.getBoundingClientRect().toJSON(),font:s.font,padding:s.padding,verticalAlign:s.verticalAlign,borderTop:s.borderTop,borderBottom:s.borderBottom};})''')
    (out/'layout.json').write_text(json.dumps(layout,indent=2),encoding='utf-8')
    for index in (1,2,3):
        a_rect=layout['reference'][index]['rect'];b_rect=layout['local'][index]['rect']
        assert a_rect['height']==b_rect['height'],(index,a_rect,b_rect)
        assert a_rect['x']==b_rect['x']-230 and a_rect['y']==b_rect['y']-50
    ref_cells=[c for c in layout['referenceCells'] if c['tag']=='TD']
    local_cells=[c for c in layout['localCells'] if c['tag']=='TD']
    assert len(ref_cells)==len(local_cells)==20
    for index,(a_cell,b_cell) in enumerate(zip(ref_cells,local_cells)):
        if index not in (6,17):
            assert a_cell['rect']['width']==b_cell['rect']['width'],index
    behavior_requests=[]
    def behavior(route):
        behavior_requests.append(parse_qs(urlparse(route.request.url).query))
        route.fulfill(json={'total':0,'items':[]})
    local.route('**/api/v1/lottery-records?*',behavior)
    local.locator('[data-review-cell=behavior] button').first.click()
    local.locator('.member-behavior-dialog').wait_for()
    local.wait_for_function("document.querySelector('.member-behavior-dialog main').textContent.includes('没有找到')")
    assert behavior_requests[-1]['user_id']==['8100'] and behavior_requests[-1]['game_id']==['7100']
    local.locator('.member-behavior-dialog header button').click()
    with local.expect_request(lambda request:'/api/v1/withdrawals?' in request.url and 'username=' in request.url) as event:
        local.locator('[data-review-search=username]').first.click()
    assert parse_qs(urlparse(event.value.url).query)['username']==['对照账号0']
    browser.close()
a=Image.open(out/'reference.png').convert('RGB');b=Image.open(out/'local.png').convert('RGB');d=ImageChops.difference(a,b);d.save(out/'diff.png')
report={'scope':'withdrawal list, 3 identical records with filters collapsed; backend not certified','mean_rgb':sum(ImageStat.Stat(d).mean)/3,'changed_pixel_ratio':sum(max(pixel)>10 for pixel in d.getdata())/(a.width*a.height)}
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report)
