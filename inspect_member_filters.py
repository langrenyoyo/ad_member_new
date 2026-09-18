"""Read-only reference common-search control definitions with fixture member rows."""
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

source=Path('compare_members_fixture.py').read_text(encoding='utf-8')
prefix=source[:source.index('    local=browser.new_page')]
prefix=prefix.replace("out=Path('visual-baseline/fixtures/members')","out=Path('visual-baseline/reference-verified/member-filter-fixture')",1)
tail='''    result=ref.locator('form.form-commonsearch').evaluate_all("""forms=>forms.map(f=>({html:f.outerHTML,controls:[...f.querySelectorAll('input,select')].map(e=>({tag:e.tagName,name:e.name,cls:e.className,placeholder:e.placeholder,attrs:Object.fromEntries([...e.attributes].map(a=>[a.name,a.value]))}))}))""")
    configs=ref.locator('.selectpage').evaluate_all("""els=>els.map(e=>({name:e.name,options:Object.fromEntries(Object.entries(jQuery(e).data('selectPageObject').option).map(([k,v])=>[k,typeof v==='function'?String(v):v]))}))""")
    ref.route('**/ajax/*List_source/**',lambda r:r.fulfill(json={'list':[{'id':7200 if 'gameList' in r.request.url else 6200,'name':'fixture-game' if 'gameList' in r.request.url else 'fixture-agent'}],'total':1}))
    requests=[]
    ref.on('request',lambda r:requests.append({'url':r.url,'method':r.method,'body':r.post_data}) if r.resource_type in ('xhr','fetch') else None)
    for field in ['game.name_text','agent.name_text']:
        ref.locator('[name="'+field+'"]').click();ref.wait_for_timeout(600)
        ref.locator('.sp_result_area:visible li').first.click()
        ref.keyboard.press('Escape')
    selected=ref.locator('form.form-commonsearch').evaluate('f=>jQuery(f).serializeArray()')
    ref.locator('form.form-commonsearch button[type=submit]').click();ref.wait_for_load_state('networkidle')
    selected_request=requests[-1]
    for field in ['game.name_text','agent.name_text']:
        ref.locator('[name="'+field+'"]').fill('unselected-name');ref.locator('[name="'+field+'"]').press('Tab')
    ref.wait_for_timeout(700)
    typed=ref.locator('form.form-commonsearch').evaluate('f=>jQuery(f).serializeArray()')
    ref.locator('form.form-commonsearch button[type=submit]').click();ref.wait_for_load_state('networkidle')
    typed_request=requests[-1]
    chosen={item['name']:item['value'] for item in selected}
    assert chosen['game.name']=='7200' and chosen['agent.name']=='6200'
    query=parse_qs(urlparse(selected_request['url']).query)
    assert json.loads(query['filter'][0])=={'game.name':'7200','agent.name':'6200'}
    assert json.loads(query['op'][0])=={'game.name':'=','agent.name':'LIKE'}
    print(json.dumps({'selected':selected},ensure_ascii=True))
    Path('visual-baseline/reference-verified/member-filter-options.json').write_text(json.dumps({'configs':configs,'requests':requests,'selected':selected,'selected_request':selected_request,'typed':typed,'typed_request':typed_request},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'configs':configs,'requests':requests},ensure_ascii=True))
    print(ref.evaluate("performance.getEntriesByType('resource').map(r=>r.name).filter(n=>/selectpage|select-page/.test(n))"))
    print(ref.evaluate("({paths:require.s.contexts._.config.paths,selectpage:require.toUrl('selectpage')})"))
    Path('visual-baseline/reference-verified/member-filters.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([r['controls'] for r in result],ensure_ascii=True))
    browser.close()
'''
exec(compile(prefix+tail,__file__,'exec'))
