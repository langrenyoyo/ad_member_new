"""Read-only agent list inspection; no OSS secrets are requested."""
import ast
import json
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

BASE = 'https://ad.leadink.cn/DmvTqXBpfF.php'
OUT = Path('visual-baseline/fixtures/agents-current')
OUT.mkdir(parents=True, exist_ok=True)
rows = [{'id': 9003-i, 'name': ['Fixture agent', 'Fixture <>&', 'Fixture child'][i], 'parent_id': 9003 if i == 2 else 0,
         'status': '1' if i != 1 else '0', 'create_time': 1789689600+i*60, 'update_time': 1789776000+i*60} for i in range(3)]
(OUT/'fixture-rows.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')

class SyntheticOssHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False);self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag=='input':
            values=dict(attrs);name=values.get('name','').removeprefix('row[').removesuffix(']')
            if name in ('ossKey','ossKeySecret','endPoint','bucket'):
                values['value']={'ossKey':'synthetic-key','ossKeySecret':'synthetic-secret','endPoint':'https://fixture.invalid','bucket':'fixture-bucket'}[name]
                self.parts.append('<input '+' '.join(key if value is None else key+'="'+escape(value,quote=True)+'"' for key,value in values.items())+'>');return
        self.parts.append(self.get_starttag_text())
    def handle_endtag(self,tag):self.parts.append('</'+tag+'>')
    def handle_data(self,data):self.parts.append(data)
    def handle_entityref(self,name):self.parts.append('&'+name+';')
    def handle_charref(self,name):self.parts.append('&#'+name+';')
    def handle_decl(self,decl):self.parts.append('<!'+decl+'>')

def main():
    source = ast.parse(Path('inspect_withdrawal_blacklist.py').read_text(encoding='utf-8-sig'))
    credentials = {}
    for node in ast.walk(source):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'fill' and len(node.args) == 2:
            key = ast.literal_eval(node.args[0])
            if key in ('[name=username]', '[name=password]'):
                credentials[key] = ast.literal_eval(node.args[1])
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1690, 'height': 1030})
        page.goto(BASE+'/index/login')
        for selector, value in credentials.items(): page.fill(selector, value)
        page.locator('button[type=submit],input[type=submit]').first.click()
        page.wait_for_url(lambda url: '/index/login' not in url)
        mode = {'many': False}
        def readonly(route):
            request = route.request; url = urlparse(request.url)
            if request.method=='GET' and '/agent/ossedit/ids/' in url.path:
                response=route.fetch();parser=SyntheticOssHTML();parser.feed(response.text())
                route.fulfill(response=response,body=''.join(parser.parts));return
            if request.method not in ('GET', 'HEAD') or any(part in url.path for part in ('/update', '/lahei', '/multi', '/del', '/agree', '/refuse', '/alipay', '/ban', '/coinclear', '/oss')):
                route.abort(); return
            if url.path.endswith(('/agent', '/agent/index')) and request.headers.get('x-requested-with') == 'XMLHttpRequest':
                q = parse_qs(url.query)
                items = [{**rows[i % 3], 'id': i+1} for i in range(225)] if mode['many'] else rows
                start = int(q.get('offset', ['0'])[0]); limit = int(q.get('limit', [str(len(items))])[0])
                route.fulfill(json={'total': len(items), 'rows': items[start:start+limit]}); return
            route.continue_()
        page.route('**/*', readonly)
        page.goto(BASE+'/agent', wait_until='networkidle')
        page.wait_for_function("window.jQuery&&jQuery('#table').data('bootstrap.table')&&jQuery.active===0")
        response = page.request.get('https://ad.leadink.cn/assets/js/backend/agent.js')
        if response.ok: (OUT/'reference-controller.js').write_text(response.text(), encoding='utf-8')
        report = page.evaluate("""()=>{const o=jQuery('#table').bootstrapTable('getOptions');return {
          table:{sortName:o.sortName,sortOrder:o.sortOrder,pageSize:o.pageSize,pageList:o.pageList,search:o.search,
            columns:o.columns.map(cols=>cols.map(c=>({field:c.field,title:c.title,visible:c.visible,sortable:c.sortable,operate:c.operate,formatter:c.formatter?.toString()})))},
          permissions:{...document.querySelector('#table').dataset},
          controls:[...document.querySelectorAll('button,a.btn')].map(n=>({text:n.textContent,cls:n.className,href:n.getAttribute('href'),title:n.title,visible:!!n.offsetWidth,parent:n.parentElement.className})),
          geometry:[...document.querySelectorAll('#table th')].map(n=>({field:n.dataset.field,width:n.getBoundingClientRect().width})),
          cells:[...document.querySelectorAll('#table tbody tr:first-child td')].map(n=>({text:n.textContent,html:n.innerHTML}))
        }}""")
        page.evaluate('document.fonts.ready'); page.locator('#main').screenshot(path=str(OUT/'reference.png'))
        page.locator('[name=commonSearch]').click(); page.locator('#main').screenshot(path=str(OUT/'filters-reference.png'))
        report['filters'] = page.locator('.commonsearch-table input,.commonsearch-table select').evaluate_all('nodes=>nodes.map(n=>({name:n.name,placeholder:n.placeholder,type:n.type,html:n.outerHTML}))')
        page.locator('[name=commonSearch]').click()
        for prefix in ['', 'selected-']:
            if prefix: page.locator('[name=btSelectItem]').first.check()
            for kind in ['json', 'xml', 'csv', 'txt', 'doc', 'excel']:
                page.locator('.export button').click()
                with page.expect_download() as download: page.locator('.export [data-type="'+kind+'"]').click()
                download.value.save_as(str(OUT/(prefix+'export-reference.'+kind)))
        page.locator('#main').screenshot(path=str(OUT/'selection-reference.png'))
        page.locator('[name=btSelectItem]').first.uncheck()
        page.locator('[name=toggle]').click(); page.locator('#main').screenshot(path=str(OUT/'cards-reference.png'))
        page.locator('[name=toggle]').click(); mode['many'] = True; page.locator('.btn-refresh').click()
        page.wait_for_function('jQuery.active===0'); page.locator('.fixed-table-pagination').screenshot(path=str(OUT/'pagination-reference.png'))
        (OUT/'reference.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        actual=page.request.get(BASE+'/agent/index',params={'limit':1,'offset':0,'sort':'id','order':'desc'},headers={'X-Requested-With':'XMLHttpRequest'}).json()
        aid=actual['rows'][0]['id'];del actual
        page.evaluate("id=>jQuery('#table').bootstrapTable('updateRow',{index:0,row:{id}})",aid)
        page.locator('#table .btn-detail').first.click();page.wait_for_timeout(800)
        frame=next(frame for frame in page.frames if '/agent/ossedit/' in frame.url)
        frame.locator('[name="row[ossKey]"]').wait_for()
        for key,value in {'ossKey':'synthetic-key','ossKeySecret':'synthetic-secret','endPoint':'https://fixture.invalid','bucket':'fixture-bucket'}.items():
            assert frame.locator('[name="row['+key+']"]').input_value()==value
        report['oss_window']=page.locator('.layui-layer').evaluate('n=>({x:n.offsetLeft,y:n.offsetTop,width:n.offsetWidth,height:n.offsetHeight,header:n.querySelector(".layui-layer-title").outerHTML,buttons:n.querySelector(".layui-layer-setwin").innerHTML,shade:!!document.querySelector(".layui-layer-shade")})')
        report['oss_styles']=frame.locator('body,#main,form,.form-group,.control-label,input,.layer-footer,button').evaluate_all('nodes=>nodes.map(n=>{const r=n.getBoundingClientRect(),c=getComputedStyle(n);return {tag:n.tagName,cls:n.className,name:n.name,type:n.type,text:n.tagName==="INPUT"?null:n.children.length?null:n.textContent.trim(),x:r.x,y:r.y,width:r.width,height:r.height,font:c.font,color:c.color,background:c.backgroundColor,padding:c.padding,margin:c.margin,border:c.border}})')
        page.locator('.layui-layer').screenshot(path=str(OUT/'oss-reference.png'))
        (OUT/'reference.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'oss_window':report['oss_window'],'permissions':report['permissions'],'geometry':report['geometry']}, ensure_ascii=False))
        browser.close()

if __name__ == '__main__': main()
