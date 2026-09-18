"""No old-scope batch mutation after navigation or replacing page state."""
from pathlib import Path
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parent
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page()
    page.set_content('<main id="content"></main>')
    page.evaluate("""() => {
      window.state={view:'withdrawals'};window.reviewStates={withdrawals:{generation:1,agentScope:9000}};
      window.esc=String;
      window.calls=[];window.api=async (path,options)=>{calls.push({path,body:JSON.parse(options.body)});return {}};
      window.renderReviewPage=async()=>{};
    }""")
    page.add_script_tag(path=str(root/'public/withdrawal-actions.js'))
    def mount():
        page.evaluate("""() => {
          document.querySelector('#content').innerHTML='<section class="withdrawal-panel"><div class="withdrawal-toolbar"></div><p id="reviewError"></p><table><thead><tr><th>Id</th></tr></thead><tbody><tr><td>7</td></tr></tbody></table></section>';
          attachWithdrawalSelection([{id:7}]);
        }""")
        page.locator('[data-withdrawal-select]').check()
    mount()
    page.locator('#withdrawalBatchRefuse').click()
    page.locator('.withdrawal-confirm').wait_for()
    page.evaluate("window.dispatchEvent(new HashChangeEvent('hashchange'))")
    page.locator('.withdrawal-confirm').wait_for(state='detached')
    assert page.evaluate('calls.length')==0
    # Same generation number on a different state object must not authorize old IDs.
    page.locator('#withdrawalBatchRefuse').click()
    page.evaluate("reviewStates.withdrawals={generation:1,agentScope:9001}")
    page.locator('.withdrawal-confirm-ok').click()
    page.locator('.withdrawal-confirm').wait_for(state='detached')
    assert page.evaluate('calls.length')==0
    mount()
    page.locator('#withdrawalBatchRefuse').click()
    page.locator('.withdrawal-confirm-ok').click()
    page.wait_for_function('calls.length===1')
    assert page.evaluate('calls[0]')=={'path':'/withdrawals/batch-refuse','body':{'ids':[7]}}
    browser.close()
print('Batch confirmation: navigation cancels, replaced scope cannot submit, current scope can submit')
