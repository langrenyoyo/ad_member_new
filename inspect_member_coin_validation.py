"""Observe reference client validation with every non-read request intercepted."""
import json
from pathlib import Path
from urllib.parse import parse_qs

source=Path('inspect_member_coin_dialog.py').read_text(encoding='utf-8')
# Reuse only login and opening the existing read-only form.
setup=source[:source.index("tail='''")]
exec(compile(setup,__file__,'exec'))
tail='''    ref.goto(base+'/gameuser',wait_until='networkidle')
    ref.locator('#table a[title="修改金币"]').first.click()
    layer=ref.locator('.layui-layer-iframe').last;frame=layer.frame_locator('iframe')
    frame.locator('[name="row[coin]"]').wait_for()
    attempts=[]
    def intercept(route):
        if route.request.method not in ['GET','HEAD','OPTIONS']:
            data=parse_qs(route.request.post_data or '',keep_blank_values=True)
            attempts.append({key:value for key,value in data.items() if key in ['row[coin]','row[freeze_coin]']})
            route.fulfill(json={'code':0,'msg':'fixture: request intercepted; no business write','data':None})
        else:route.continue_()
    ref.route('**/*',intercept)
    results=[]
    for value in ['', 'abc', '-5', '1.25']:
        before=len(attempts)
        frame.locator('[name="row[coin]"]').fill(value)
        frame.locator('[name="row[freeze_coin]"]').fill('3')
        layer.locator('.layui-layer-footer [type=submit]').click()
        ref.wait_for_timeout(500)
        results.append({'coin_input':value,'client_sent_request':len(attempts)>before,'intercepted_fields':attempts[before:]})
    frame.locator('[name="row[coin]"]').evaluate("e=>{e.defaultValue='12.5';e.value='99'}")
    frame.locator('[name="row[freeze_coin]"]').evaluate("e=>{e.defaultValue='3';e.value='88'}")
    layer.locator('.layui-layer-footer [type=reset]').click()
    reset={'coin':frame.locator('[name="row[coin]"]').input_value(),'freeze_coin':frame.locator('[name="row[freeze_coin]"]').input_value()}
    artifact={'scope':'reference browser behavior only; all write requests fulfilled locally, no reference server validation inferred','cases':results,'reset':reset}
    (out/'client-validation.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(artifact,ensure_ascii=True));browser.close()
'''
exec(compile(prefix+tail,__file__,'exec'))
