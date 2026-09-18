"""Inspect the reference recipient blacklist without performing business mutations."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE='https://ad.leadink.cn/DmvTqXBpfF.php'
OUT=Path('visual-baseline/reference-verified')
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1920,'height':1080})
    page.goto(BASE+'/index/login')
    page.fill('[name=username]','18532306918');page.fill('[name=password]','123456')
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.wait_for_url(lambda url:'/index/login' not in url)
    def readonly(route):
        if route.request.method not in ('GET','HEAD') or any(part in route.request.url for part in ('/lahei','/multi','/del','/agree','/refuse','/alipay')):route.abort()
        else:route.continue_()
    page.route('**/*',readonly)
    data=page.request.get(BASE+'/exchangehei/index',params={'limit':1,'offset':0,'filter':'{}','op':'{}'},headers={'X-Requested-With':'XMLHttpRequest'}).json()
    report={'total':data.get('total'),'fields':list(data.get('rows',[{}])[0]) if data.get('rows') else []}
    page.goto(BASE+'/tixian',wait_until='networkidle')
    page.locator('a[href="exchangehei/index"]').click()
    window=page.locator('.layui-layer-iframe').last
    window.wait_for()
    frame=window.locator('iframe').element_handle().content_frame()
    frame.wait_for_function("window.jQuery&&jQuery('#table').data('bootstrap.table')")
    frame.wait_for_function('jQuery.active===0')
    report['dialog']=window.bounding_box()
    report['window_controls']=window.locator('.layui-layer-setwin a').evaluate_all('els=>els.map(el=>({classes:el.className,title:el.title}))')
    report['table']=frame.evaluate("()=>{const o=jQuery('#table').bootstrapTable('getOptions');return {sortName:o.sortName,sortOrder:o.sortOrder,pageSize:o.pageSize,pageList:o.pageList,columns:o.columns.map(cols=>cols.map(c=>({field:c.field,title:c.title,visible:c.visible,sortable:c.sortable,operate:c.operate,searchList:c.searchList})))}}")
    report['permissions']=frame.locator('#table').evaluate('el=>el.dataset')
    report['toolbar']=frame.locator('#toolbar').evaluate("el=>[...el.querySelectorAll('a,button')].map(n=>({text:n.textContent.trim(),classes:n.className,title:n.title,icons:[...n.querySelectorAll('i')].map(icon=>icon.className)}))")
    report['filters']=frame.locator('.form-commonsearch input:not([type=hidden]),.form-commonsearch select').evaluate_all("els=>els.map(el=>({name:el.name,placeholder:el.placeholder,value:el.value,options:el.options?[...el.options].map(o=>({value:o.value,text:o.text})):undefined}))")
    rows=[{'id':9000+i,'receive_name':'fixture '+str(i),'receive_tel':'001234'+str(i),'status':1-i,'create_time':1789689600,'update_time':1789689600} for i in range(2)]
    frame.evaluate("rows=>jQuery('#table').bootstrapTable('load',{total:rows.length,rows})",rows)
    report['cells']=frame.locator('#table tbody tr').first.locator('td').evaluate_all('els=>els.map(el=>({text:el.textContent,html:el.innerHTML}))')
    frame.evaluate('document.fonts.ready')
    report['styles']=frame.evaluate("""()=>Object.fromEntries(['body','.form-commonsearch label','.form-commonsearch select','.form-commonsearch button','.fixed-table-toolbar button','.fixed-table-toolbar .btn-group','#table th','#table td','#table .fa-toggle-on','.pagination-info'].map(s=>{
        const n=document.querySelector(s);if(!n)return [s,null];const c=getComputedStyle(n),r=n.getBoundingClientRect();
        return [s,{x:r.x,y:r.y,width:r.width,height:r.height,font:c.font,color:c.color,padding:c.padding,border:c.border,html:n.outerHTML.slice(0,600)}];}))""")
    page.add_style_tag(content='.layui-layer{animation:none!important}')
    window.screenshot(path=str(OUT/'withdrawal-blacklist-fixture.png'))
    (OUT/'withdrawal-blacklist.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
    browser.close()
