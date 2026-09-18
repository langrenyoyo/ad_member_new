"""Capture the same member fixture on both sites; never send business writes."""
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

out=Path('visual-baseline/fixtures/game-members')
out.mkdir(parents=True,exist_ok=True)
base='https://ad.leadink.cn/DmvTqXBpfF.php'
with sync_playwright() as p:
    browser=p.chromium.launch()
    ref=browser.new_page(viewport={'width':1536,'height':822})
    ref.goto(base+'/index/login')
    ref.fill('[name=username]','18532306918')
    ref.fill('[name=password]','123456')
    ref.locator('button[type=submit],input[type=submit]').first.click()
    ref.wait_for_url(lambda url:'/index/login' not in url)
    ref.route('**/*',lambda route:route.abort() if route.request.method not in ['GET','HEAD'] else route.continue_())
    response=ref.request.get(base+'/game/index',params={'limit':1,'offset':0,'filter':'{}','op':'{}'},headers={'X-Requested-With':'XMLHttpRequest'})
    gid=response.json()['rows'][0]['id']
    rows=[dict(id=9001+i,username=f'fixture-{i}',parent_id=100,parent_username='parent-account',parent_name='上级昵称',game_id=gid,
               game_name='对照游戏',name='隐藏昵称',coin_user=1234.5,coin_user_month=234,coin_user_day=12,coin=123.5,freeze_coin=3,
               is_true=i%2,game_addiction_enable=i%2,exchange_enable=1,is_white=i%2,status=1-i%2,
               created_at='2026-09-17T04:00:00Z',create_time=1789617600) for i in range(3)]
    refrows=[dict(row,game={'id':gid,'name':row['game_name']}) for row in rows]
    ref.route('**/games/user/index/**',lambda route:route.fulfill(json={'total':len(rows),'rows':refrows}) if route.request.resource_type in ['xhr','fetch'] else route.continue_())
    ref.goto(base+f'/games/userdata/index/game_id/{gid}',wait_until='networkidle')
    ref.locator('a[href="#four"]').click()
    ref.wait_for_function("window.jQuery && jQuery('#table4').data('bootstrap.table')")
    ref.wait_for_function('jQuery.active===0')
    ref.evaluate("rows=>jQuery('#table4').bootstrapTable('load',{total:rows.length,rows})",refrows)
    ref.locator('#four tbody tr').first.wait_for()
    ref.evaluate('document.fonts.ready')
    ref.screenshot(path=str(out/'reference.png'),animations='disabled')
    local=browser.new_page(viewport={'width':1920,'height':1080})
    local.goto('http://127.0.0.1:3000/#games')
    local.fill('#loginForm [name=username]','18532306918');local.fill('#loginForm [name=password]','123456')
    local.locator('#loginForm').evaluate('form=>form.requestSubmit()')
    local.locator('[data-game-user]').first.wait_for()
    local_gid=int(local.locator('[data-game-user]').first.get_attribute('data-game-user'))
    localrows=[dict(row,game_id=local_gid) for row in rows]
    local.route('**/api/v1/members?*',lambda route:route.fulfill(json={'total':len(rows),'items':localrows}))
    local.locator('[data-game-user]').first.click();local.locator('[data-tab=four]').click()
    local.locator('[data-member-select]').first.wait_for()
    local.evaluate('document.fonts.ready')
    local.locator('.game-user-body').screenshot(path=str(out/'local.png'),animations='disabled')
    evidence={}
    for name,page,selector in [('reference',ref,'#table4'),('local',local,'#game-user-pane-four table')]:
        evidence[name]=page.locator(selector).evaluate('''table=>({
            width:table.getBoundingClientRect().width,
            headers:[...table.querySelectorAll('thead th')].map(el=>({text:el.innerText,width:el.getBoundingClientRect().width})),
            rows:[...table.querySelectorAll('tbody tr')].map(el=>({height:el.getBoundingClientRect().height})),
            cells:[...table.querySelectorAll('tbody tr:first-child td')].map(el=>{const c=getComputedStyle(el);return {text:el.innerText,html:el.innerHTML,font:c.font,padding:c.padding,whiteSpace:c.whiteSpace,wordBreak:c.wordBreak,color:c.color};}),
            buttons:[...table.querySelectorAll('tbody tr:first-child button,tbody tr:first-child a.btn')].map(el=>({text:el.innerText,font:getComputedStyle(el).font,background:getComputedStyle(el).backgroundColor,height:el.getBoundingClientRect().height}))
        })''')
    evidence['referenceLayout']=ref.locator('.panel,.panel-body,.panel-heading,.nav-tabs,.nav-tabs li,.nav-tabs a,.fixed-table-toolbar,.fixed-table-pagination,#toolbar4,#toolbar4 .dropdown').evaluate_all('''els=>els.map(el=>{const s=getComputedStyle(el);return {selector:el.tagName+'.'+el.className,rect:el.getBoundingClientRect().toJSON(),font:s.font,padding:s.padding,margin:s.margin,background:s.backgroundColor,display:s.display,border:s.border};})''')
    evidence['referencePagination']=ref.evaluate('''()=>{const o=jQuery('#table4').bootstrapTable('getOptions');return Object.fromEntries(['pageList','pageSize','showJumpto','paginationLoop','smartDisplay','paginationPreText','paginationNextText'].map(k=>[k,o[k]]));}''')
    ref.evaluate("rows=>jQuery('#table4').bootstrapTable('load',{total:1234,rows})",refrows)
    evidence['referencePaginationHtml']=ref.locator('#four .fixed-table-pagination').inner_html()
    (out/'measurements.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    browser.close()
a=Image.open(out/'reference.png').convert('RGB');b=Image.open(out/'local.png').convert('RGB')
assert a.size==b.size,(a.size,b.size)
diff=ImageChops.difference(a,b);diff.save(out/'diff.png')
report={'scope':'Game member fixture, including controls and default columns; not full feature parity',
        'changed_pixel_ratio':sum(max(pixel)>10 for pixel in diff.get_flattened_data())/(a.width*a.height),
        'mean_rgb':sum(ImageStat.Stat(diff).mean)/3}
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(report)
