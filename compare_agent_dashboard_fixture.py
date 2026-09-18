"""Compare agent dashboard with identical browser data, without business writes."""
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

out = Path('visual-baseline/fixtures/agent-dashboard')
out.mkdir(parents=True, exist_ok=True)
fixture = json.loads(Path('visual-baseline/fixtures/dashboard/data.json').read_text(encoding='utf-8'))
fixture['agent_name'] = '对照主体：中文名称'
(out/'data.json').write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding='utf-8')
base = 'https://ad.leadink.cn/DmvTqXBpfF.php'
with sync_playwright() as p:
    browser = p.chromium.launch()
    ref = browser.new_page(viewport={'width':1690,'height':1030})
    ref.goto(base+'/index/login', wait_until='domcontentloaded')
    ref.fill('[name=username]', '18532306918'); ref.fill('[name=password]', '123456')
    ref.locator('button[type=submit],input[type=submit]').first.click()
    ref.locator('a[href*="agent?ref=addtabs"]').wait_for(state='attached')
    response = ref.request.get(base+'/agent/index', params={'limit':1,'offset':0,'filter':'{}','op':'{}'}, headers={'X-Requested-With':'XMLHttpRequest'})
    agent_id = response.json()['rows'][0]['id']
    ref.goto(base+'/agents/dash/index/agent_id/'+str(agent_id), wait_until='networkidle')
    ref.wait_for_function("typeof require==='function' && document.querySelector('#echart canvas')")
    ref.evaluate("""data=>new Promise(resolve=>require(['echarts'], E=>{
      const chart=E.getInstanceByDom(document.querySelector('#echart'));
      chart.setOption({animation:false,xAxis:{data:data.items.map(x=>x.date)},series:[{data:data.items.map(x=>x.count)}]});
      const cards=document.querySelectorAll('.sm-st-info span');
      cards[0].textContent=data.today_new;cards[1].textContent=data.today_login;
      const name=[...document.querySelectorAll('.alert')].find(e=>e.textContent.includes('代理商名称'));
      if(!name)throw Error('Reference agent name not found');
      name.textContent='代理商名称：'+data.agent_name;
      resolve();
    }))""", fixture)
    ref.evaluate('document.fonts.ready')
    ref.screenshot(path=str(out/'reference.png'))
    local = browser.new_page(viewport={'width':1920,'height':1080})
    local.add_init_script("sessionStorage.setItem('agent-dashboard-id','9000')")
    local.route('**/api/v1/agents/9000/dashboard', lambda route:route.fulfill(json=fixture))
    local.goto('http://127.0.0.1:3000/#agent-dashboard')
    local.fill('[name=username]', '18532306918'); local.fill('[name=password]', '123456')
    local.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    local.wait_for_function("window.echarts && document.querySelector('#agentChart canvas')")
    local.evaluate("echarts.getInstanceByDom(document.querySelector('#agentChart')).setOption({animation:false})")
    local.evaluate('document.fonts.ready')
    local.screenshot(path=str(out/'local.png'), clip={'x':230,'y':50,'width':1690,'height':1030})
    layout = {}
    for name,page,selectors in [('reference',ref,['.alert','.alert + .alert','.alert a','.sm-st','.sm-st-icon','.sm-st-info','#echart']),('local',local,['.agent-dashboard-name','.agent-dashboard-tools','.agent-dashboard-tools a','.agent-dashboard-cards article','#agentChart'])]:
        layout[name]=page.evaluate("sels=>sels.map(s=>{const e=document.querySelector(s);return {selector:s,rect:e?.getBoundingClientRect().toJSON(),style:e?{font:getComputedStyle(e).font,padding:getComputedStyle(e).padding,margin:getComputedStyle(e).margin}:null}})",selectors)
    (out/'layout.json').write_text(json.dumps(layout,indent=2),encoding='utf-8')
    browser.close()
a=Image.open(out/'reference.png').convert('RGB');b=Image.open(out/'local.png').convert('RGB')
d=ImageChops.difference(a,b);d.save(out/'diff.png')
report={'scope':'agent dashboard content with identical 31-day fixture; backend and destination pages not certified','mean_rgb':sum(ImageStat.Stat(d).mean)/3,'changed_pixel_ratio':sum(max(pixel)>10 for pixel in d.getdata())/(a.width*a.height)}
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(report)
