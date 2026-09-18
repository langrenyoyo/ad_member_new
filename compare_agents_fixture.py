"""Browser-only identical agent records; no business writes on either site."""
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

out=Path('visual-baseline/fixtures/agents');out.mkdir(parents=True,exist_ok=True)
rows=[dict(id=9000+i,name=name,parent_id=0 if i<2 else 9000,status=i%2,
           create_time=1789516800,update_time=1789516800,created_at='2026-09-16T00:00:00Z')
      for i,name in enumerate(['对照主体甲','测试主体乙：长名称与字符 <>&','下级主体丙'])]
(out/'data.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch()
    ref=browser.new_page(viewport={'width':1690,'height':1030})
    ref.goto('https://ad.leadink.cn/DmvTqXBpfF.php/index/login')
    ref.fill('[name=username]','18532306918');ref.fill('[name=password]','123456')
    ref.locator('button[type=submit],input[type=submit]').first.click();ref.wait_for_timeout(1500)
    ref.route('**/agent/index?*',lambda route:route.fulfill(json={'total':len(rows),'rows':rows}) if route.request.resource_type in ['xhr','fetch'] else route.continue_())
    ref.goto('https://ad.leadink.cn/DmvTqXBpfF.php/agent',wait_until='networkidle')
    ref.wait_for_function("window.jQuery && jQuery('#table').data('bootstrap.table')")
    ref.evaluate("rows=>jQuery('#table').bootstrapTable('load',{total:rows.length,rows})",rows)
    ref.screenshot(path=str(out/'reference.png'))
    local=browser.new_page(viewport={'width':1920,'height':1080})
    local.route('**/api/v1/agents?*',lambda route:route.fulfill(json={'total':len(rows),'items':rows}))
    local.goto('http://127.0.0.1:3000/#agents')
    local.fill('[name=username]','18532306918');local.fill('[name=password]','123456')
    local.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    local.locator('[data-agent-select]').first.wait_for()
    assert local.locator('[data-agent-select]').count()==len(rows)
    local.locator('#agentSelectAll').check()
    assert all(local.locator('[data-agent-select]').evaluate_all('els=>els.map(e=>e.checked)'))
    local.locator('#agentSelectAll').uncheck()
    local.locator('#agentSearchToggle').click()
    assert local.locator('#agentFilters').is_visible()
    local.locator('#agentSearchToggle').click()
    assert local.locator('#agentFilters').is_hidden()
    assert local.locator('[data-agent-enter]').count()==2
    local.screenshot(path=str(out/'local.png'),clip={'x':230,'y':50,'width':1690,'height':1030})
    measurements={}
    for name,page,selectors in [('reference',ref,['#table','tbody tr','.panel','.fixed-table-toolbar']),('local',local,['.agent-panel table','tbody tr','.agent-panel','.ads-toolbar'])]:
        measurements[name]=page.evaluate("sels=>sels.map(s=>({selector:s,rect:document.querySelector(s)?.getBoundingClientRect().toJSON()}))",selectors)
        measurements[name+'Headers']=page.locator(selectors[0]+' thead th').evaluate_all('''els=>els.map(e=>({text:e.textContent,styles:[e,...e.children].map(n=>{const s=getComputedStyle(n);return {tag:n.tagName,height:n.getBoundingClientRect().height,font:s.font,padding:s.padding,borderTop:s.borderTop,borderBottom:s.borderBottom,verticalAlign:s.verticalAlign};})}))''')
    (out/'layout.json').write_text(json.dumps(measurements,indent=2),encoding='utf-8')
    browser.close()
a=Image.open(out/'reference.png').convert('RGB');b=Image.open(out/'local.png').convert('RGB')
d=ImageChops.difference(a,b);d.save(out/'diff.png')
report={'scope':'agent list with identical fixture; backend not certified','mean_rgb':sum(ImageStat.Stat(d).mean)/3,'changed_pixel_ratio':sum(max(p)>10 for p in d.getdata())/(a.width*a.height)}
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report)
