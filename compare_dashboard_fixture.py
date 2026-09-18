"""Compare live reference and local dashboard using identical browser-only fixtures."""
import json
from datetime import date, timedelta
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

OUT = Path('visual-baseline/fixtures/dashboard')
OUT.mkdir(parents=True, exist_ok=True)
fixture = {'today_new': 4, 'today_login': 12, 'items': [
    {'date': (date(2026, 8, 18)+timedelta(days=i)).isoformat(), 'count': [0,1,0,4,4,0,2][i%7]}
    for i in range(31)]}
(OUT/'data.json').write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding='utf-8')
with sync_playwright() as p:
    browser = p.chromium.launch()
    ref = browser.new_page(viewport={'width':1690,'height':1030})
    ref.goto('https://ad.leadink.cn/DmvTqXBpfF.php/index/login')
    ref.fill('[name=username]', '18532306918')
    ref.fill('[name=password]', '123456')
    ref.locator('button[type=submit],input[type=submit]').first.click()
    ref.wait_for_timeout(1500)
    ref.goto('https://ad.leadink.cn/DmvTqXBpfF.php/dash', wait_until='networkidle')
    ref.wait_for_function("typeof require==='function' && document.querySelector('#echart canvas')")
    ref.evaluate("""data=>new Promise(resolve=>require(['echarts'], E=>{
      const chart=E.getInstanceByDom(document.querySelector('#echart'));
      chart.setOption({animation:false,xAxis:{data:data.items.map(x=>x.date)},series:[{data:data.items.map(x=>x.count)}]});
      const cards=document.querySelectorAll('.sm-st-info span');
      cards[0].textContent=data.today_new;cards[1].textContent=data.today_login;
      resolve();
    }))""", fixture)
    ref.screenshot(path=str(OUT/'reference.png'))
    local=browser.new_page(viewport={'width':1920,'height':1080})
    def intercept(route):
        route.fulfill(json=fixture if '/summary' in route.request.url else {'items':fixture['items']})
    local.route('**/api/v1/dashboard/summary',intercept)
    local.route('**/api/v1/dashboard/registrations?*',intercept)
    local.goto('http://127.0.0.1:3000/#dashboard')
    local.fill('[name=username]','18532306918');local.fill('[name=password]','123456')
    local.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    local.wait_for_function("window.echarts && document.querySelector('#echart canvas')")
    local.evaluate("echarts.getInstanceByDom(document.querySelector('#echart')).setOption({animation:false})")
    local.screenshot(path=str(OUT/'local.png'),clip={'x':230,'y':50,'width':1690,'height':1030})
    assert local.locator('.dash-card strong').all_text_contents()==['4','12']
    browser.close()
a=Image.open(OUT/'reference.png').convert('RGB');b=Image.open(OUT/'local.png').convert('RGB')
diff=ImageChops.difference(a,b);diff.save(OUT/'diff.png')
report={'scope':'dashboard content only, identical browser fixture; does not certify backend parity',
        'mean_rgb':sum(ImageStat.Stat(diff).mean)/3,
        'changed_pixel_ratio':sum(max(pixel)>10 for pixel in diff.getdata())/(a.width*a.height)}
(OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
