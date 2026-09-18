"""Download reference/local member exports using identical browser fixtures."""
import csv,io,json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

source=Path('compare_members_fixture.py').read_text(encoding='utf-8')
prefix=source[:source.index('    layout={}')].replace('fixtures/members','fixtures/member-export')
hidden='--hidden' in sys.argv
if hidden:
    prefix=prefix.replace('fixtures/member-export','fixtures/member-hidden-export')
    prefix=prefix.replace('reference=[',"for row in rows: row.update(parent_username='parent-account',agent_name='对照主体',game_addiction_enable=row['vip']%2,game_addiction_time='2026-09-15 12:00:00',exchange_enable=row['vip']%2,last_login_device_id='device-001',last_login_ip='198.51.100.25',last_login_time='2026-09-16T00:00:00Z')\nrows[-1]['username']='000123'\nreference=[",1)
    prefix=prefix.replace("'create_time':1789516800", "'create_time':1789516800,'last_login_time':1789516800",1)
tail='''    ref.route('**/gameuser*',lambda route:route.fulfill(json={'total':3,'rows':reference}) if route.request.resource_type in ['xhr','fetch'] else route.continue_())
    if hidden:
        mapping={'parent_id':'parent_id','parent_username':'parent_username','agent_name':'agent.name','name':'name','game_addiction_enable':'game_addiction_enable','game_addiction_time':'game_addiction_time','exchange_enable':'exchange_enable','last_login_device_id':'last_login_device_id','last_login_ip':'last_login_ip','last_login_time':'last_login_time'}
        local.locator('.member-columns summary').click()
        for field,reference_field in mapping.items():
            ref.evaluate("field=>jQuery('#table').bootstrapTable('showColumn',field)",reference_field)
            local.locator('[data-member-column="'+field+'"]').check()
        local.locator('.member-columns summary').focus();local.keyboard.press('Escape')
    results=[]
    for selected in [False,True]:
        if selected:
            ref.locator('#table tbody input[type=checkbox]').first.check()
            local.locator('[data-select]').first.check()
        for kind in ['csv','json','xml','txt','doc','excel']:
            documents={}
            for side,page in [('reference',ref),('local',local)]:
                if side=='reference':
                    page.locator('.export>button').click()
                    button=page.locator('.export li[data-type="'+kind+'"]')
                else:
                    page.locator('.member-export summary').click()
                    button=page.locator('[data-member-export="'+kind+'"]')
                with page.expect_download() as event:button.click()
                content=Path(event.value.path()).read_text(encoding='utf-8-sig')
                (out/(side+('-selected' if selected else '-all')+'.'+kind)).write_text(content,encoding='utf-8')
                documents[side]=content
                page.wait_for_load_state('networkidle')
            if kind in ['csv','txt']:
                parsed={side:list(csv.reader(io.StringIO(value),delimiter=',' if kind=='csv' else '\\t')) for side,value in documents.items()}
            elif kind=='json':parsed={side:json.loads(value) for side,value in documents.items()}
            elif kind=='xml':parsed={side:ET.tostring(ET.fromstring(value),encoding='unicode') for side,value in documents.items()}
            else:parsed=documents
            results.append({'format':kind,'selected':selected,'equal':parsed['reference']==parsed['local'],'reference':parsed['reference'],'local':parsed['local']})
    (out/'comparison.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{k:v for k,v in result.items() if k not in ['reference','local']} for result in results]))
    assert all(result['equal'] for result in results), 'Reference/local export mismatch; inspect comparison.json'
    browser.close()
'''
exec(compile(prefix+tail,__file__,'exec'))
