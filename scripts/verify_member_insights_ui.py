"""Isolated browser contract check, mocked API only."""
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page()
    page.set_content('<div id="host"></div>')
    page.add_script_tag(content="""
    const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const calls=[];
    async function api(path,options){
      calls.push({path,options});
      if(options?.method==='PUT')return {category:'finance',revision:1};
      if(path.includes('/insights'))return {id:1,name:'<img src=x onerror=alert(1)>',status:1,level:3,parent_id:0,invite_code:'TEST',direct_count:2,coin:'10',frozen_coin:'0',commission_total_coin:'5',commission_today_coin:'1',contribution_coin:'2',paid_withdrawal_cents:1234,ad_views:3,ad_views_today:1,category_reason:'unknown'};
      if(path.includes('/ad-settlements'))return {total:1,items:[{id:'ad',provider:'taku',status:'rewarded',user_reward_coin:'2',allocations:[{member_id:2,kind:'commission_3',coin:'0.2',rule:{ratio:'.1'}}],events:[{type:'rewarded',time:'today'}]}]};
      return {total:1,items:[{member_id:1,device_id:null,ip:'test',same_ip_verified_devices:0,same_device_accounts:null,nearby_verified_devices:null,battery:80,charging:true,observed_seconds:0,charging_ratio:null,location_stable_seconds:null,samples:1,updated_at:'today'}]};
    }
    """)
    page.add_script_tag(path=str(Path(__file__).resolve().parents[1]/'public/member-insights.js'))
    page.evaluate('mountMemberInsights(document.querySelector("#host"))')
    page.locator('[data-insight] input').fill('1')
    page.locator('[data-insight] button').click()
    page.locator('[data-insight-result] h3').wait_for()
    assert page.locator('[data-insight-result] img').count()==0
    assert '12.34' in page.locator('[data-insight-result]').inner_text()
    page.locator('summary').click()
    assert 'commission_3' in page.locator('[data-ad-page]').inner_text()
    page.locator('[data-ad-page] [name=category]').select_option('finance')
    page.locator('[data-ad-page] [name=reason]').fill('verified creative')
    page.locator('[data-ad-page] form button').click()
    body=page.evaluate('JSON.parse(calls.find(c=>c.options?.method==="PUT").options.body)')
    assert body['category']=='finance' and body['expected_revision']==0
    page.locator('[data-observations] input').fill('1')
    page.locator('[data-observations] button').click()
    assert '无法判定' in page.locator('[data-observation-result]').inner_text()
    browser.close()
print('member insights browser checks passed')
