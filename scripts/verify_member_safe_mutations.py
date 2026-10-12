"""Mocked browser checks for balance/rebind contracts; no business writes."""
from pathlib import Path
from playwright.sync_api import sync_playwright

source = (Path(__file__).resolve().parents[1] / 'public/app.js').read_text(encoding='utf-8')
function = source[source.index('async function openMemberValueDialog('):source.index('function memberFilterMarkup(')]
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content('<main></main>')
    page.add_script_tag(content="""
    let pageLoadGeneration=0;const writes=[];
    async function load(){}
    async function api(path,options){
      if(options){writes.push({path,...options});return {};}
      return {id:1,coin:12.5,freeze_coin:3,parent_id:2,ht_id:0,ht_top_id:0};
    }
    """ + function)
    page.evaluate("openMemberValueDialog(1,'coin')")
    page.locator('[name=coin]').fill('15')
    assert page.locator('[name=freeze_coin]').get_attribute('readonly') is not None
    page.locator('[name=reason]').fill('correction')
    page.locator('[name=coin]').fill('1000000001')
    page.locator('[type=submit]').click()
    assert page.evaluate('writes.length') == 0
    page.locator('[name=coin]').fill('15.1234567')
    page.locator('[type=submit]').click()
    assert page.evaluate('writes.length') == 0
    page.locator('[name=coin]').fill('15.123456')
    page.locator('[type=submit]').click()
    result=page.evaluate('writes[0]')
    assert result['path']=='/members/1/adjust-balance' and result['method']=='POST'
    import json
    body=json.loads(result['body'])
    assert body['expected_coin']=='12.5' and body['expected_freeze_coin']=='3'
    assert body['reason']=='correction'
    assert body['coin']=='15.123456'
    page.evaluate("openMemberValueDialog(1,'rebind')")
    page.locator('[name=parent_id]').fill('0')
    page.locator('[type=submit]').click()
    result=page.evaluate('writes[1]')
    assert result['path']=='/members/1/rebind'
    assert json.loads(result['body'])['expected_parent_id']==2
    browser.close()
print('safe member mutation browser checks passed')
