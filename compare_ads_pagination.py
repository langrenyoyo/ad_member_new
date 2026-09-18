"""Compare local pagination states to reference captures with identical row counts."""
import json
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from PIL import Image,ImageChops,ImageStat
from playwright.sync_api import sync_playwright,expect

out=Path('visual-baseline/fixtures/ads-pagination')
reference=json.loads((out/'reference.json').read_text(encoding='utf-8'))
seed=json.loads(Path('visual-baseline/fixtures/ads/data.json').read_text(encoding='utf-8'))['local'][0]
queries=[];results=[]
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080})
    def listing(route):
        q=parse_qs(urlparse(route.request.url).query);queries.append(q)
        offset=int(q['offset'][0]);limit=int(q['limit'][0])
        route.fulfill(json={'total':205,'items':[{**seed,'id':9200+i} for i in range(offset,min(205,offset+limit))],'summary':{}})
    page.route('**/api/v1/ads?*',listing)
    page.goto('http://127.0.0.1:3000/#ads')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()');page.locator('#adsSearchToggle').click()
    for sample in reference:
        if 'page' not in sample:continue
        n=sample['page']
        if n!=1:
            page.locator('[aria-label="跳转页码"]').fill(str(n))
            page.locator('[data-ads-jump]').click()
        expect(page.locator('#adsPagination [aria-current=page]')).to_have_text(str(n))
        expect(page.locator('#adsTable tbody td[data-ads-field=id]').first).to_have_text(str(9200+(n-1)*10),use_inner_text=True)
        page.mouse.move(0,0)
        panel=page.locator('#adsPagination')
        geom=panel.evaluate('e=>e.getBoundingClientRect().toJSON()')
        styles=panel.locator('summary,[data-ads-jump]').evaluate_all('es=>es.map(e=>{const c=getComputedStyle(e);return {text:e.innerText,font:c.font,rect:e.getBoundingClientRect().toJSON(),border:c.border,background:c.backgroundColor}})')
        text=panel.inner_text()
        assert ''.join(text.split())==''.join(sample['text'].split()),(n,text,sample['text'])
        panel.screenshot(path=str(out/f'local-{n}.png'))
        a=Image.open(out/f'reference-{n}.png').convert('RGB');b=Image.open(out/f'local-{n}.png').convert('RGB')
        assert a.size==b.size,(n,a.size,b.size)
        diff=ImageChops.difference(a,b);diff.save(out/f'diff-{n}.png')
        results.append({'page':n,'reference_rect':sample['rect'],'local_rect':geom,'styles':styles,'mean_rgb':sum(ImageStat.Stat(diff).mean)/3,'changed_pixel_ratio':sum(max(pixel)>10 for pixel in diff.get_flattened_data())/(diff.width*diff.height)})
    for label,first in [('下一页','9200'),('上一页','9400')]:
        page.locator('#adsPagination [aria-label="'+label+'"]').click()
        expect(page.locator('#adsTable tbody td[data-ads-field=id]').first).to_have_text(first,use_inner_text=True)
    before=len(queries)
    page.locator('#adsPageSizeMenu summary').click()
    expect(page.locator('[data-ads-size]')).to_have_count(6)
    page.locator('[data-ads-size=All]').click()
    expect(page.locator('#adsTable tbody tr')).to_have_count(205)
    expect(page.locator('#adsPagination nav')).to_be_hidden()
    assert [q['offset'] for q in queries[before:]]==[['0'],['200']]
    assert '显示第 1 到第 205 条记录，总共 205 条记录' in page.locator('#adsPagination').inner_text()
    page.reload()
    expect(page.locator('#adsTable tbody tr')).to_have_count(205)
    expect(page.locator('#adsPageSizeMenu summary')).to_have_text('All')
    page.locator('#adsPageSizeMenu summary').click();page.locator('[data-ads-size="25"]').click()
    expect(page.locator('#adsTable tbody tr')).to_have_count(25)
    browser.close()
(out/'comparison.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print([{'page':row['page'],'changed_pixel_ratio':row['changed_pixel_ratio']} for row in results])
print('PASS: reference page windows, boundaries, All rows/persistence and restoration to 25 per page')
