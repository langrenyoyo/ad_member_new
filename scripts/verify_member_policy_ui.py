"""Browser smoke test with fake API responses; no production writes."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content('<div id="host"></div>')
    page.add_script_tag(content="""
    const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const calls=[];
    async function api(path,options){
      calls.push({path,options});
      if(path.endsWith('/reward-preview'))return {coin:'8.000000'};
      if(path.endsWith('/level'))return {invite_code:'ABC'};
      if(path.includes('/usage?'))return {items:[{package_name:'com.test.app',duration_ms:60000,opens:3}]};
      if(path.includes('/reward-ledgers?')){
        const offset=Number(new URLSearchParams(path.split('?')[1]).get('offset'));
        return {total:51,items:Array.from({length:offset===0?50:1},(_,i)=>({id:offset+i+1,ad_session_id:'ad',member_id:1,beneficiary_id:2,kind:'commission_1',amount:'2'}))};
      }
      return {require_alipay:false,require_invite:false,require_usage:false,reset_login_block:false,reward_enabled:false,
        whitelist_risk_exempt:false,invite_min_level:1,reward_basis:'fixed_ecpm',fixed_ecpm:10,coins_per_yuan:100,
        whitelist_multiplier:1,max_reward:100,agent_member_id:0,announcement_version:1,announcement:'<script>bad</script>',
        network_rates:{kuaishou:1,gdt:1,csj:1,baidu:1,other:1},source_networks:{},commission_rates:[0,.1,.1,.1],block_signals:[]};
    }
    """)
    page.add_script_tag(path=str(ROOT / 'public/member-policy.js'))
    page.evaluate('mountMemberPolicy(document.querySelector("#host"))')
    page.locator('[name=game]').fill('1')
    page.locator('[data-load] button').click()
    page.locator('[name=require_invite]').check()
    page.locator('[name=commission_enabled]').check()
    page.locator('[name=sources]').fill('123=kuaishou')
    page.locator('[data-save] button').first.click()
    assert page.locator('[data-status]').inner_text() == '规则已保存'
    body = page.evaluate('JSON.parse(calls.find(c=>c.options?.method==="PUT").options.body)')
    assert body['require_invite'] and body['source_networks'] == {'123':'kuaishou'}
    assert body['announcement'] == '<script>bad</script>'
    assert body['commission_enabled'] and not body['reward_enabled']
    page.locator('[data-ledger]').click()
    assert page.locator('[data-ledgers] tbody tr').count() == 50
    assert page.locator('[data-prev]').is_disabled()
    page.locator('[data-next]').click()
    assert page.locator('[data-ledgers] tbody tr').count() == 1
    assert page.locator('[data-next]').is_disabled()
    page.locator('[data-prev]').click()
    assert page.locator('[data-ledgers] tbody tr').count() == 50
    page.locator('[name=reward_enabled]').check()
    page.locator('[name=reward_basis]').select_option('verified_cny_ecpm')
    page.locator('[name=tier_enabled]').check()
    page.locator('[name=tier_upper]').fill('50,100')
    page.locator('[name=tier_percent]').fill('200,70')
    page.locator('[name=label_rewards_enabled]').check()
    page.locator('[name=label_finance]').fill('10')
    page.locator('[name=preview_label]').select_option('finance')
    assert '200%' in page.locator('[data-tier-table]').inner_text()
    page.locator('[data-preview]').click()
    assert '8.000000' in page.locator('[data-preview-result]').inner_text()
    page.locator('[data-save] button').first.click()
    saved=page.evaluate('JSON.parse(calls.filter(c=>c.options?.method==="PUT").at(-1).options.body)')
    assert saved['tier_enabled'] and saved['ecpm_tiers']==[{'upper':'50','percent':'200'},{'upper':'100','percent':'70'}]
    assert saved['label_rewards_enabled'] and saved['label_rewards']=={'finance':'10'}
    page.locator('[name=member]').fill('2')
    page.locator('[name=level]').select_option('1')
    page.locator('[data-member] button').first.click()
    page.locator('[name=date]').fill('2026-10-10')
    page.locator('[data-usage]').click()
    assert 'com.test.app' in page.locator('[data-report]').inner_text()
    page.set_viewport_size({'width':390,'height':844})
    assert page.locator('[data-save] button').first.is_visible()
    browser.close()
print('member policy browser smoke passed')
