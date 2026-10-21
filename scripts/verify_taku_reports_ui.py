"""Isolated browser check: no live accounts or reports."""
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page()
    page.set_content('<div id="host"></div>')
    page.add_script_tag(content="""
    const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const calls=[];
    async function api(path,options){calls.push({path,options});
      if(path.includes('/sync'))return {status:'waiting_report'};
      if(options)return {};
      return {status:'rechecked',flagged_members:[1],items:[{member_id:1,placement_id:'<img src=x>',network_id:'all',currency:'CNY',impressions:10,estimate:'10',revenue:'7',difference:'3',reduction_percent:'30',status:'suspected_reduction',flagged:true}]};
    }
    """)
    page.add_script_tag(path=str(Path(__file__).resolve().parents[1]/'public/taku-reports.js'))
    page.evaluate('mountTakuReports(document.querySelector("#host"))')
    page.locator('[name=game]').fill('1')
    page.locator('[name=day]').fill('2026-10-19')
    page.locator('[data-query] button').click()
    page.locator('tbody tr').wait_for()
    assert page.locator('[data-results] img').count()==0
    assert '30.00' in page.locator('[data-results]').inner_text()
    page.locator('[data-sync] button').click()
    page.wait_for_function("document.querySelector('[data-status]').textContent.includes('TAKU')")
    assert page.locator('tbody tr').count()==1
    page.locator('[name=threshold_percent]').fill('25')
    page.locator('[data-rule] button').click()
    assert page.evaluate("JSON.parse(calls.find(c=>c.options?.method==='PUT').options.body).threshold_percent")=='25'
    browser.close()
print('TAKU reconciliation browser checks passed')
