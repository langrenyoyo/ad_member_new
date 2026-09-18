"""Exercise the actual behavior renderer with controlled responses, without business writes."""
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('http://fixture.test/**',lambda route:route.fulfill(body='<dialog class="game-user-dialog"></dialog>',content_type='text/html'))
    page.goto('http://fixture.test/')
    page.add_script_tag(content="""
      const esc=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
      const profileLogTime=String,attachReviewDates=()=>{},reviewDateBindings=new Map();
      localStorage.setItem('pagesize','20');
      window.calls=[];window.pending=[];
      const api=(path,options)=>new Promise(resolve=>{
        calls.push({path,signal:options.signal});pending.push(resolve);
      });
    """)
    page.add_script_tag(path=str(Path('public/game-userdata.js').resolve()))
    page.add_style_tag(path=str(Path('public/game-userdata.css').resolve()))
    page.evaluate("()=>{document.querySelector('.game-user-dialog').showModal();openMemberBehavior(42,237,'multiple');}")
    dialog = page.locator('.member-behavior-dialog')
    assert dialog.locator('[role=tab]').count() == 8
    dialog.locator('[data-behavior-tab=coins]').click()
    assert page.evaluate("calls[0].signal.aborted")
    assert page.evaluate("new URL(calls[1].path,'http://local').searchParams.has('type')") is False
    assert page.evaluate("new URL(calls[1].path,'http://local').searchParams.get('user_id')") == '42'
    page.evaluate("pending[1]({total:21,items:Array.from({length:20},(_,i)=>({id:i+1,coin:100+i}))})")
    coins=dialog.locator('#behavior-pane-coins')
    coins.locator('[aria-label="下一页"]').click()
    assert page.evaluate("new URL(calls[2].path,'http://local').searchParams.get('offset')") == '20'
    page.evaluate("pending[2]({total:21,items:[{id:21,coin:555}]})")
    assert coins.locator('tbody td').first.inner_text() == '21'
    # An old response must not overwrite the current page, even if abort is ignored.
    page.evaluate("pending[0]({total:1,items:[{id:999}]})")
    assert coins.locator('tbody td').first.inner_text() == '21'
    dialog.locator('[data-behavior-tab=members]').click()
    assert page.evaluate("new URL(calls[3].path,'http://local').searchParams.get('parent_id')") == '42'
    assert page.evaluate("new URL(calls[3].path,'http://local').searchParams.has('id')") is False
    assert page.evaluate("new URL(calls[3].path,'http://local').searchParams.has('user_id')") is False
    page.evaluate("pending[3]({total:1,items:[{id:77,username:'child'}]})")
    assert 'child' in dialog.locator('#behavior-pane-members tbody').inner_text()
    dialog.locator('[data-behavior-tab=coins]').click()
    assert page.evaluate("new URL(calls[4].path,'http://local').searchParams.get('offset')") == '20'
    page.evaluate("document.querySelector('.game-user-dialog').close()")
    dialog.wait_for(state='detached')
    assert page.evaluate('calls[4].signal.aborted')
    page.evaluate("pending[4]({total:0,items:[]})")
    page.evaluate("openMemberBehavior(42,237,'single')")
    page.evaluate("window.dispatchEvent(new Event('hashchange'))")
    dialog.wait_for(state='detached')
    assert page.evaluate('calls[5].signal.aborted')
    assert not errors, errors
    browser.close()
    print('Behavior contracts: descendants, coin types, pagination, stale responses and parent cleanup passed')
