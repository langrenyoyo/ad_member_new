"""Isolated browser verification: mocked APIs, no login or production traffic."""
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import json
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/ad-types-20261108'
ART.mkdir(parents=True,exist_ok=True)
requests=[]
errors=[]
rows=[]
for i,(name,is_fu,fu_type) in enumerate([('激励视频',0,1),('开屏',1,1),('横幅',1,2),('插屏',1,3),('信息流',1,4)],1):
    rows.append({'id':i,'user_id':1,'game_id':238,'game_name':'鸭只易记','is_fu':is_fu,
        'fu_type':fu_type,'is_look':1,'ad_title':'<示例广告> '+name,'ad_app_name':'示例应用',
        'ad_app_package':'com.example.ad','ad_creative_id':'creative-'+str(i),
        'ad_network':'快手','ad_source_id':'source-'+str(i),'ad_content_status':'reported',
        'ad_behaviors':['shown','clicked'],'watched_at':'2026-11-08T08:00:00Z'})
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless=True)
    page=browser.new_page(viewport={'width':1920,'height':1080})
    page.on('pageerror',lambda e:errors.append(str(e)))
    def route(req):
        url=urlparse(req.request.url)
        if url.path.startswith('/api/'):
            if url.path=='/api/v1/ads':
                query=parse_qs(url.query);requests.append(query)
                visible=rows if 'is_fu' not in query else [r for r in rows if str(r['is_fu'])==query['is_fu'][0]]
                req.fulfill(json={'items':visible,'total':len(visible),'summary':{}})
            elif url.path.endswith('/auth/me'):
                req.fulfill(json={'id':1,'role':'superadmin','display_name':'本地验证'})
            else:req.fulfill(json={'items':[],'total':0})
            return
        if url.netloc!='ad-types.local':raise AssertionError('Unexpected external request')
        file=ROOT/'public'/('index.html' if url.path=='/' else url.path.lstrip('/'))
        req.fulfill(path=str(file)) if file.is_file() else req.fulfill(status=404,body='missing')
    page.route('**/*',route)
    page.add_init_script("localStorage.setItem('admin_access_token','local-fixture');")
    page.goto('http://ad-types.local/#ads',wait_until='networkidle')
    expect(page.locator('#adsFilters [name=is_fu]')).to_have_value('')
    expect(page.locator('#adsTable tbody tr')).to_have_count(5)
    assert 'is_fu' not in requests[0]
    expect(page.locator('td[data-ads-field=sub_ad_type] .ads-card-value').first).to_have_text('—')
    for i in range(1,6):
        expect(page.locator(f'#adsTable tbody tr:nth-child({i}) [data-ads-field=ad_title] .ads-card-value')).to_have_text(rows[i-1]['ad_title'])
    assert page.locator('#adsTable script').count()==0
    for key in ['ad_app_name','ad_app_package','ad_creative_id','ad_source_id','ad_network','ad_content_status']:
        assert page.locator('#adsTable th[data-ads-field='+key+']').is_visible()
    page.locator('#adsFilters [name=is_fu]').select_option('1')
    page.locator('#adsFilters [type=submit]').click()
    expect(page.locator('#adsTable tbody tr')).to_have_count(4)
    assert requests[-1]['is_fu']==['1']
    page.locator('#adsFilters [type=reset]').click()
    expect(page.locator('#adsTable tbody tr')).to_have_count(5)
    assert 'is_fu' not in requests[-1]
    assert not errors,errors
    page.screenshot(path=str(ART/'admin-ad-types.png'),full_page=True)
    browser.close()
(ART/'browser-verification.json').write_text(json.dumps({'result':'passed','rows':5,
    'checks':['default all types','secondary filter','reset all types','rewarded subtype absent',
    'creative content columns','escaped SDK title','no script errors','no external requests'],
    'page_errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: all five formats, secondary filter/reset, content fields and escaped titles; no external requests.')
