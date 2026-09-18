"""Capture reference search query semantics with browser-only member fixtures."""
import json
from pathlib import Path
from urllib.parse import urlparse,parse_qs

source=Path('compare_members_fixture.py').read_text(encoding='utf-8')
prefix=source[:source.index('    local=browser.new_page')]
prefix=prefix.replace("out=Path('visual-baseline/fixtures/members')","out=Path('visual-baseline/reference-verified/member-search-fixture')",1)
prefix=prefix.replace('reference=[',"for row in rows: row['last_login_ip']='198.51.100.25'\nreference=[",1)
tail='''    captures=[]
    def capture(route):
        if route.request.resource_type in ['xhr','fetch'] and '/gameuser' in route.request.url:
            captures.append(parse_qs(urlparse(route.request.url).query))
            route.fulfill(json={'total':3,'rows':reference})
        else:route.continue_()
    ref.route('**/*',capture)
    result={}
    for field in ['username','parent_id','game.name','agent.name','name','ip_check','vip','last_login_ip']:
        ref.evaluate("field=>jQuery('#table').bootstrapTable('showColumn',field)",field)
        selector='#table .searchit[data-field="'+field+'"]'
        element=ref.locator(selector).first
        if element.count()==0:
            result[field]={'present':False};continue
        captures.clear();element.click();ref.wait_for_load_state('networkidle')
        result[field]={'queries':captures.copy(),'form':ref.locator('form.form-commonsearch').evaluate_all("els=>els.map(e=>jQuery(e).serializeArray())")}
    Path('visual-baseline/reference-verified/member-search-contract.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:{'requests':len(value.get('queries',[])),'op':value.get('queries',[{}])[-1].get('op') if value.get('queries') else None} for key,value in result.items()},ensure_ascii=True))
    browser.close()
'''
exec(compile(prefix+tail,__file__,'exec'))
