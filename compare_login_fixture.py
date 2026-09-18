"""Compare unauthenticated login screens without submitting credentials."""
import json
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
from playwright.sync_api import sync_playwright

out=Path('visual-baseline/fixtures/login');out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch();metrics={}
    for name,url in [('reference','https://ad.leadink.cn/DmvTqXBpfF.php/index/login'),('local','http://127.0.0.1:3000/')]:
        page=browser.new_page(viewport={'width':1920,'height':1080})
        page.goto(url,wait_until='networkidle')
        page.locator('[name=username]').fill('');page.locator('[name=password]').fill('')
        page.locator('[name=password]').blur()
        page.evaluate('document.fonts.ready')
        page.screenshot(path=str(out/(name+'.png')))
        metrics[name]=page.evaluate("""()=>['[name=username]','[name=password]','button[type=submit],.login-submit','[name=keeplogin]'].map(selector=>{const e=[...document.querySelectorAll(selector)].find(el=>el.getClientRects().length && getComputedStyle(el).visibility!=='hidden' && el.closest('form')?.querySelector('[name=password]'));if(!e)return {selector};const s=getComputedStyle(e);return {selector,rect:e.getBoundingClientRect().toJSON(),font:s.font,color:s.color,background:s.backgroundColor,border:s.border,radius:s.borderRadius};})""")
        page.close()
    browser.close()
(out/'layout.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
a=Image.open(out/'reference.png').convert('RGB');b=Image.open(out/'local.png').convert('RGB');d=ImageChops.difference(a,b);d.save(out/'diff.png')
report={'scope':'login empty state at 1920x1080, no submission','mean_rgb':sum(ImageStat.Stat(d).mean)/3,'changed_pixel_ratio':sum(max(pixel)>10 for pixel in d.getdata())/(a.width*a.height)}
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report)
