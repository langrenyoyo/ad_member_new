"""Exercise membership editing and filtering with local static files and fake APIs."""
import copy
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT/'public')))
Thread(target=server.serve_forever, daemon=True).start()
rows = [{'id': 9200+i, 'username': f'user-{i}', 'name': f'Member {i}', 'game_id': 238,
    'game_name': 'Test app', 'agent_id': 1, 'status': 1, 'vip': 2, 'is_white': 0,
    'member_level': level, 'member_level_name': {0:'用户',1:'团长',3:'代理'}[level],
    'can_edit_member_level': True} for i,level in enumerate((0,1,3))]
writes=[]
queries=[]
try:
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={'width':1440,'height':950})
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        def api(route):
            request=route.request
            url=urlsplit(request.url); path=url.path; query=parse_qs(url.query)
            if path=='/api/auth/me':
                route.fulfill(json={'username':'root','display_name':'Test admin','role':'superadmin'});return
            if path=='/api/v1/members':
                queries.append(query)
                items=rows
                if 'member_level' in query:
                    items=[row for row in items if row['member_level']==int(query['member_level'][0])]
                route.fulfill(json={'total':len(items),'items':items,'permissions':{'create':False,'edit':True,'member_level':True}});return
            if path in ('/api/v1/withdrawals','/api/v1/subsidies'):
                queries.append(query)
                items=[{**row,'user_id':row['id'],'price':10,'exchange_value':10,'status':0,'pics':''} for row in rows]
                if 'member_level' in query:items=[row for row in items if row['member_level']==int(query['member_level'][0])]
                route.fulfill(json={'total':len(items),'items':items,'summary':{'paid':0,'pending':10},'permissions':{'edit':False,'review':False}});return
            if path.startswith('/api/v1/members/') and path.rsplit('/',1)[-1].isdigit():
                row=next(r for r in rows if r['id']==int(path.rsplit('/',1)[-1]))
                if request.method=='PATCH':
                    body=request.post_data_json;writes.append(body);row.update(body)
                    row['member_level_name']={0:'用户',1:'团长',3:'代理'}[row['member_level']]
                route.fulfill(json=row);return
            route.fulfill(json={'items':[],'total':0})
        page.route('**/api/**',api)
        page.add_init_script("sessionStorage.setItem('admin_access_token','isolated-ui-test')")
        page.goto(f'http://127.0.0.1:{server.server_port}/#members')
        expect(page.locator('th[data-field=member_level]')).to_have_text('会员身份')
        assert page.locator('[data-field=vip],[data-mf=vip],[data-member-column=vip]').count()==0
        assert page.locator('tbody [data-member-search-field=member_level]').all_text_contents()==['用户','团长','代理']
        page.locator('[data-edit="9200"]').click()
        level=page.locator('#editorForm [name=member_level]')
        expect(level).to_be_enabled();expect(level).to_have_value('0')
        assert page.locator('#editorForm [name=vip]').count()==0
        level.select_option('3')
        page.locator('#editorForm [name=name]').fill('Updated')
        page.locator('#editorForm button[type=submit]').click()
        expect(page.locator('#modal')).to_be_hidden()
        assert writes==[{'name':'Updated','member_level':3}],writes
        expect(page.locator('tbody [data-member-search-field=member_level]').first).to_have_text('代理')
        page.locator('[data-edit="9200"]').click()
        expect(level).to_have_value('3')
        page.locator('#closeModal').click()
        filt=page.locator('[data-mf=member_level]')
        if not filt.is_visible():page.locator('#memberSearchToggle').click()
        filt.select_option('1');page.locator('#memberFilterSubmit').click()
        expect(page.locator('tbody [data-member-search-field=member_level]')).to_have_count(1)
        expect(page.locator('tbody [data-member-search-field=member_level]')).to_have_text('团长')
        assert queries[-1]['member_level']==['1']
        page.locator('#memberFilterReset').click()
        expect(page.locator('tbody [data-member-search-field=member_level]')).to_have_count(3)
        page.locator('[data-member-search-field=member_level][data-member-search-value="3"]').first.click()
        expect(page.locator('tbody [data-member-search-field=member_level]')).to_have_count(2)
        assert queries[-1]['member_level']==['3']
        rows[0]['can_edit_member_level']=False
        page.locator('[data-edit="9200"]').click()
        expect(level).to_be_disabled()
        page.locator('#editorForm [name=name]').fill('Operator edit')
        page.locator('#editorForm button[type=submit]').click()
        expect(page.locator('#modal')).to_be_hidden()
        assert writes[-1]=={'name':'Operator edit'},writes
        for kind in ('withdrawals','subsidies'):
            page.goto(f'http://127.0.0.1:{server.server_port}/#{kind}')
            expect(page.locator('th[data-review-column=member_level]')).to_have_text('会员身份')
            assert page.locator('[name=vip],[data-review-column=vip],[data-review-cell=vip]').count()==0
            select=page.locator('#reviewFilters [name=member_level]')
            select.select_option('1');page.locator('#reviewFilters button[type=submit]').click()
            expect(page.locator('td[data-review-cell=member_level]')).to_have_count(1)
            expect(page.locator('td[data-review-cell=member_level] [data-review-search=member_level]')).to_have_text('团长')
            assert queries[-1]['member_level']==['1'] and 'vip' not in queries[-1]
            select.select_option('3');page.locator('#reviewFilters button[type=submit]').click()
            expect(page.locator('td[data-review-cell=member_level]')).to_have_count(2)
            page.locator('#reviewFilters button[type=reset]').click()
            expect(page.locator('td[data-review-cell=member_level]')).to_have_count(3)
            page.locator('[data-review-search=member_level][data-review-value="3"]').first.click()
            expect(page.locator('td[data-review-cell=member_level]')).to_have_count(2)
            assert queries[-1]['member_level']==['3']
            # Exercise actual export markup with a stubbed file writer.
            page.evaluate('''()=>{reviewExporterReady=Promise.resolve();jQuery.fn.tableExport=function(){window.identityExport=this[0].innerText;return this;};}''')
            page.locator('.review-export summary').click()
            page.locator('[data-review-export=csv]').click()
            page.wait_for_function("window.identityExport && window.identityExport.includes('会员身份')")
            exported=page.evaluate('window.identityExport')
            assert 'VIP' not in exported and '代理' in exported,exported
            page.evaluate('window.identityExport=null')
        assert not errors,errors
        browser.close()
    print('Member identity UI passed: display, edit/reload, filter/reset, click-to-filter, read-only permission.')
finally:
    server.shutdown();server.server_close()
