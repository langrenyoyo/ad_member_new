"""Verify real ECharts rendering, resizing and disposal without business writes."""
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parent
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.set_content('<div id="agentChart" style="width:800px;height:360px"></div>')
    page.add_script_tag(path=str(root / 'public/vendor/echarts.min.js'))
    page.evaluate("window.fetch=async()=>({ok:true,json:async()=>({})})")
    page.add_script_tag(path=str(root / 'public/agent-chart.js'))
    page.evaluate("mountAgentChart([{date:'2026-09-15',count:2},{date:'2026-09-16',count:3}])")
    assert page.locator('#agentChart canvas').count() > 0
    assert page.locator('[role=alert]').count() == 0
    page.evaluate("document.querySelector('#agentChart').style.width='500px'")
    page.wait_for_function("echarts.getInstanceByDom(document.querySelector('#agentChart')).getWidth()===500")
    page.evaluate("window.testChart=echarts.getInstanceByDom(document.querySelector('#agentChart'));document.querySelector('#agentChart').remove()")
    page.wait_for_function('testChart.isDisposed()')
    page.evaluate("document.body.innerHTML='<div id=content></div>'")
    page.add_style_tag(path=str(root / 'public/dashboard.css'))
    page.evaluate("""window.state={view:'dashboard'};window.$=s=>document.querySelector(s);
      window.esc=String;window.api=async path=>path.includes('summary')?{today_new:2,today_login:3}:
      {items:Array.from({length:31},(_,i)=>({date:'2026-09-'+String(i+1).padStart(2,'0'),count:i===4?2:0}))};void 0;""")
    page.add_script_tag(path=str(root / 'public/dashboard.js'))
    page.evaluate('renderDashboard()')
    assert page.locator('.dash-card strong').all_text_contents() == ['2', '3']
    assert page.locator('#echart canvas').count() > 0
    assert page.evaluate("echarts.getInstanceByDom(document.querySelector('#echart')).getOption().series[0].data.length") == 31
    page.evaluate("window.dashboardChart=echarts.getInstanceByDom(document.querySelector('#echart'));document.querySelector('#content').innerHTML=''")
    page.wait_for_function('dashboardChart.isDisposed()')
    assert not errors, errors
    browser.close()
print('Agent and dashboard charts: render, data binding, resize and disposal passed')
