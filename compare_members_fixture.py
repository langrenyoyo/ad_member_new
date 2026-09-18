"""Identical member fixtures on real reference and local pages; no business writes."""
import json
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
from playwright.sync_api import sync_playwright

out=Path('visual-baseline/fixtures/members');out.mkdir(parents=True,exist_ok=True)
rows=[dict(id=9200+i,username=f'对照会员{i}',name='隐藏昵称',real_name='实名认证姓名',receive_name='支付宝姓名',parent_id=0,parent_name='上级甲',game_id=7200,game_name='对照游戏',agent_id=6200,vip=i,coin_user=125.5+i,coin_user_month=10,coin_user_day=0,coin=100,freeze_coin=5,is_white=i%2,status=i%2,ip='192.0.2.1',created_at='2026-09-16T00:00:00Z') for i in range(3)]
reference=[{**r,'game':{'name':r['game_name']},'agent':{'name':'对照主体'},'ip_check':r['ip'],'create_time':1789516800} for r in rows]
(out/'data.json').write_text(json.dumps({'local':rows,'reference':reference},ensure_ascii=False,indent=2),encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch();ref=browser.new_page(viewport={'width':1690,'height':1030})
    base='https://ad.leadink.cn/DmvTqXBpfF.php'
    ref.goto(base+'/index/login',wait_until='domcontentloaded')
    ref.fill('[name=username]','18532306918');ref.fill('[name=password]','123456');ref.locator('button[type=submit],input[type=submit]').first.click()
    ref.locator('a[href*="gameuser?ref=addtabs"]').wait_for(state='attached')
    ref.route('**/gameuser/index?*',lambda route:route.fulfill(json={'total':3,'rows':reference}) if route.request.resource_type in ['xhr','fetch'] else route.continue_())
    ref.goto(base+'/gameuser',wait_until='networkidle')
    ref.wait_for_function("window.jQuery && jQuery('#table').data('bootstrap.table')")
    ref.evaluate("rows=>{jQuery('#table').bootstrapTable('load',{total:rows.length,rows});jQuery('#table').bootstrapTable('hideLoading');}",reference)
    assert ref.locator('#table tbody tr[data-index]').count()==3
    ref.evaluate('document.fonts.ready');ref.screenshot(path=str(out/'reference.png'))
    local=browser.new_page(viewport={'width':1920,'height':1080})
    local.route('**/api/v1/members?*',lambda route:route.fulfill(json={'total':3,'items':rows}))
    local.goto('http://127.0.0.1:3000/#members');local.fill('[name=username]','18532306918');local.fill('[name=password]','123456')
    local.locator('#loginForm').evaluate('f=>f.requestSubmit()');local.locator('tbody tr').first.wait_for()
    local.evaluate('document.fonts.ready');local.screenshot(path=str(out/'local.png'),clip={'x':230,'y':50,'width':1690,'height':1030})
    layout={}
    layout['referenceSwitches']=ref.locator('#table tbody .btn-change i').evaluate_all('''els=>els.map(e=>{const s=getComputedStyle(e);return {cls:e.className,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height,font:s.font,color:s.color,transform:s.transform,verticalAlign:s.verticalAlign,content:getComputedStyle(e,'::before').content};})''')
    for name,page,selector in [('reference',ref,'#table'),('local',local,'.table')]:
        layout[name+'FirstRow']=page.locator(selector+' tbody tr').first.evaluate('''row=>[...row.cells].filter(c=>c.getClientRects().length).map(c=>({text:c.textContent.trim(),html:c.innerHTML,width:c.getBoundingClientRect().width}))''')
        layout[name+'Styles']=page.locator(selector).evaluate('''e=>[e,...e.querySelectorAll('thead tr,thead th,tbody tr,tbody tr:first-child td')].map(n=>{const s=getComputedStyle(n);return {tag:n.tagName,rect:n.getBoundingClientRect().toJSON(),font:s.font,padding:s.padding,border:s.border,boxSizing:s.boxSizing};})''')
        layout[name+'HeaderContents']=page.locator(selector+' thead th').evaluate_all('''nodes=>nodes.filter(n=>n.getClientRects().length).map(n=>({text:n.textContent,children:[n,...n.querySelectorAll('*')].map(c=>{const s=getComputedStyle(c);return {tag:c.tagName,cls:c.className,height:c.getBoundingClientRect().height,display:s.display,lineHeight:s.lineHeight,verticalAlign:s.verticalAlign,margin:s.margin,padding:s.padding,borderTop:s.borderTop,borderBottom:s.borderBottom};})}))''')
        layout[name]=page.locator(selector).evaluate("e=>({rect:e.getBoundingClientRect().toJSON(),headers:[...e.querySelectorAll('thead th')].filter(t=>t.getClientRects().length).map(t=>{const clone=t.cloneNode(true);clone.querySelectorAll('[aria-hidden=true]').forEach(icon=>icon.remove());return clone.textContent.trim();})})")
    (out/'layout.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding='utf-8')
    assert layout['local']['headers']==layout['reference']['headers']
    reference_heights=[r['rect']['height'] for r in layout['referenceStyles'] if r['tag']=='TR'][1:]
    local_heights=[r['rect']['height'] for r in layout['localStyles'] if r['tag']=='TR'][1:]
    assert local_heights==reference_heights,(local_heights,reference_heights)
    assert layout['localStyles'][1]['rect']['height']==layout['referenceStyles'][1]['rect']['height']
    assert layout['local']['rect']['height']==layout['reference']['rect']['height']
    # All default columns follow reference content-driven widths for these fixtures.
    for index,(ref_cell,local_cell) in enumerate(zip(layout['referenceFirstRow'],layout['localFirstRow'])):
        assert ref_cell['width']==local_cell['width'],(index,ref_cell['width'],local_cell['width'])
    assert '实名认证姓名' not in local.locator('tbody').inner_text()
    assert local.locator('tbody .member-card-value').get_by_text('支付宝姓名',exact=True).count()==3
    browser.close()
a=Image.open(out/'reference.png').convert('RGB');b=Image.open(out/'local.png').convert('RGB');d=ImageChops.difference(a,b);d.save(out/'diff.png')
report={'scope':'member list with 3 identical browser fixtures; no backend or permissions certification','mean_rgb':sum(ImageStat.Stat(d).mean)/3,'changed_pixel_ratio':sum(max(pixel)>10 for pixel in d.getdata())/(a.width*a.height)}
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report)
