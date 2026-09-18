"""Read reference editor control definitions, excluding account values and tokens."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width':1920,'height':1080})
    base = 'https://ad.leadink.cn/DmvTqXBpfF.php'
    page.goto(base + '/index/login', wait_until='domcontentloaded')
    page.fill('[name=username]', '18532306918')
    page.fill('[name=password]', '123456')
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.locator('a[href*="gameuser?ref=addtabs"]').wait_for(state='attached')
    def readonly(route):
        if route.request.method not in ('GET', 'HEAD', 'OPTIONS'):
            route.abort()
        else:
            route.continue_()
    page.route('**/*', readonly)
    page.goto(base + '/gameuser', wait_until='networkidle')
    page.locator('#table tbody input[type=checkbox]').first.check()
    page.locator('#toolbar .btn-edit').click()
    frame = page.locator('.layui-layer-iframe').last.frame_locator('iframe')
    frame.locator('[name="row[username]"]').wait_for()
    page.wait_for_function("Math.abs(document.querySelector('.layui-layer-iframe').getBoundingClientRect().width-800)<0.1")
    frame.locator('body').evaluate('async()=>{await document.fonts.ready;await new Promise(r=>setTimeout(r,500));}')
    definitions = frame.locator('form .form-group').evaluate_all('''groups=>groups.map(group=>({
      label:group.querySelector('.control-label')?.textContent.trim(),
      controls:[...group.querySelectorAll('input[type=radio],select')].map(el=>({
        name:el.name,type:el.type,
        options:el.tagName==='SELECT'?[...el.options].map(o=>({value:o.value,label:o.textContent.trim()})):
          [{value:el.value,label:el.closest('label')?.textContent.trim()}]
      }))
    })).filter(group=>group.controls.length)''')
    target = Path('visual-baseline/reference-verified/member-edit-controls.json')
    target.write_text(json.dumps(definitions, ensure_ascii=False, indent=2), encoding='utf-8')
    geometry = {'window':page.locator('.layui-layer-iframe').last.bounding_box()}
    geometry['tabs'] = frame.locator('.nav-tabs a').evaluate_all("els=>els.map(el=>({text:el.textContent.trim(),href:el.getAttribute('href'),rect:el.getBoundingClientRect().toJSON()}))")
    geometry['chrome'] = page.locator('.layui-layer-iframe').last.evaluate('''el=>[...el.querySelectorAll('.layui-layer-title,.layui-layer-footer,button')].map(n=>({cls:n.className,text:n.textContent.trim(),rect:n.getBoundingClientRect().toJSON()}))''')
    geometry['elements'] = frame.locator('form, .form-group, .control-label, input:not([type=hidden]), select, .layer-footer, button').evaluate_all('''els=>els.map(el=>{
      const s=getComputedStyle(el);return {tag:el.tagName,name:el.name,cls:el.className,
        text:el.matches('button,.control-label')?el.textContent.trim():null,
        rect:el.getBoundingClientRect().toJSON(),font:s.font,padding:s.padding,margin:s.margin,
        display:s.display,position:s.position,color:s.color,background:s.backgroundColor};
    })''')
    target.with_name('member-edit-geometry.json').write_text(json.dumps(geometry,ensure_ascii=False,indent=2),encoding='utf-8')
    extra = frame.locator('[name="row[otherlevel]"]').evaluate('''el=>({
        tag:el.tagName,type:el.type,rows:el.rows,maxLength:el.maxLength,
        placeholder:el.placeholder,disabled:el.disabled,readOnly:el.readOnly,
        label:el.closest('.form-group').querySelector('label')?.textContent.trim(),
        rect:el.getBoundingClientRect().toJSON()
    })''')
    target.with_name('member-otherlevel-control.json').write_text(json.dumps(extra,ensure_ascii=False,indent=2),encoding='utf-8')
    date_control=frame.locator('[name="row[game_addiction_time]"]').evaluate('''el=>({
      tag:el.tagName,type:el.type,placeholder:el.placeholder,cls:el.className,
      attributes:Object.fromEntries([...el.attributes].filter(a=>a.name.startsWith('data-')).map(a=>[a.name,a.value])),
      parentButtons:[...el.parentElement.querySelectorAll('button')].map(b=>b.textContent.trim())
    })''')
    target.with_name('member-date-control.json').write_text(json.dumps(date_control,ensure_ascii=False,indent=2),encoding='utf-8')
    picker=frame.locator('[name="row[game_addiction_time]"]')
    picker.evaluate("el=>{el.value='2026-09-17 12:34:56';}")
    picker.click()
    picker.evaluate("el=>window.jQuery(el).data('DateTimePicker')?.show()")
    page.wait_for_timeout(300)
    info=picker.evaluate('''el=>{
      const p=window.jQuery(el).data('DateTimePicker');const o=p?.options();
      return {format:o?.format,locale:o?.locale,sideBySide:o?.sideBySide,
        scripts:[...document.scripts].map(s=>s.src).filter(s=>/moment|datetime|require/.test(s)),
        styles:[...document.querySelectorAll('link[rel=stylesheet]')].map(l=>l.href),
        widget:document.querySelector('.bootstrap-datetimepicker-widget')?.outerHTML};
    }''')
    target.with_name('member-date-picker.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(definitions, ensure_ascii=True))
    browser.close()
