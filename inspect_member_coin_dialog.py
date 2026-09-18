"""Read reference coin dialog geometry; fill synthetic values without submitting."""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

source=Path('compare_members_fixture.py').read_text(encoding='utf-8')
prefix=source[:source.index("    ref.route(")]
prefix=prefix.replace("out=Path('visual-baseline/fixtures/members')","out=Path('visual-baseline/reference-verified/member-coin-dialog')")
prefix=prefix.replace("{'width':1690,'height':1030}","{'width':1920,'height':1080}")
tail='''    ref.goto(base+'/gameuser',wait_until='networkidle')
    ref.locator('#table a[title="修改金币"]').first.click()
    layer=ref.locator('.layui-layer-iframe').last
    frame=layer.frame_locator('iframe')
    frame.locator('[name="row[coin]"]').evaluate("e=>e.value='12.5'")
    frame.locator('[name="row[freeze_coin]"]').evaluate("e=>e.value='3'")
    frame.locator('[name="row[freeze_coin]"]').evaluate('e=>e.blur()')
    frame.locator('input[name="__token__"]').evaluate_all('els=>els.forEach(e=>e.remove())')
    layer.screenshot(path=str(out/'reference.png'))
    layout={'outer':layer.evaluate("e=>({rect:e.getBoundingClientRect().toJSON(),html:e.outerHTML})"),'form':frame.locator('form').evaluate("e=>({html:e.outerHTML,rect:e.getBoundingClientRect().toJSON(),elements:[...e.querySelectorAll('label,input,button')].map(n=>{const c=getComputedStyle(n);return {tag:n.tagName,name:n.name,text:n.tagName==='INPUT'?'':n.textContent.trim(),rect:n.getBoundingClientRect().toJSON(),font:c.font,padding:c.padding,margin:c.margin}})})")}
    (out/'layout.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding='utf-8')
    header=layer.evaluate("e=>[...e.querySelectorAll('.layui-layer-title,.layui-layer-setwin,.layui-layer-setwin a')].map(n=>{const c=getComputedStyle(n);return {cls:n.className,rect:n.getBoundingClientRect().toJSON(),font:c.font,color:c.color,background:c.backgroundImage,position:c.backgroundPosition,margin:c.margin,padding:c.padding,filter:c.filter,before:{content:getComputedStyle(n,'::before').content,font:getComputedStyle(n,'::before').font},after:{content:getComputedStyle(n,'::after').content,font:getComputedStyle(n,'::after').font}}})")
    (out/'header.json').write_text(json.dumps(header,indent=2),encoding='utf-8')
    print(json.dumps(header,ensure_ascii=True))
    if '--drag' in sys.argv:
        title=layer.locator('.layui-layer-title').bounding_box()
        ref.mouse.move(title['x']+100,title['y']+20);ref.mouse.down();ref.mouse.move(title['x']+200,title['y']+80,steps=6);ref.mouse.up()
        dragged=layer.bounding_box()
        layer.locator('.layui-layer-max').click();ref.wait_for_timeout(250)
        layer.locator('.layui-layer-max').click();ref.wait_for_timeout(250)
        (out/'drag-states.json').write_text(json.dumps({'dragged':dragged,'restored':layer.bounding_box()},indent=2),encoding='utf-8')
    layer.locator('.layui-layer-min').click()
    ref.wait_for_timeout(250)
    layer.screenshot(path=str(out/'minimized.png'))
    minimized=layer.bounding_box()
    layer.locator('.layui-layer-max').click()
    ref.wait_for_timeout(250)
    states={'minimized':minimized,'restored':layer.bounding_box()}
    layer.locator('.layui-layer-max').click();ref.wait_for_timeout(250)
    states['maximized']=layer.bounding_box()
    states['minimize_visible_when_maximized']=layer.locator('.layui-layer-min').is_visible()
    layer.locator('.layui-layer-max').click();ref.wait_for_timeout(250)
    states['restored_from_maximized']=layer.bounding_box()
    (out/'window-states.json').write_text(json.dumps(states,indent=2),encoding='utf-8')
    print(json.dumps(states))
    browser.close()
'''
exec(compile(prefix+tail,__file__,'exec'))
