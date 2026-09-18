"""Image-gallery interactions using local fixture images, without business writes."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1280,'height':800})
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.route('http://gallery.test/',lambda route:route.fulfill(content_type='text/html',body='<table><tbody><tr><td id="first"></td></tr><tr><td id="second"></td></tr></tbody></table>'))
    page.route('http://gallery.test/a.svg',lambda route:route.fulfill(content_type='image/svg+xml',body='<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200"><rect width="300" height="200" fill="#18bc9c"/></svg>'))
    page.route('http://gallery.test/b.svg',lambda route:route.fulfill(content_type='image/svg+xml',body='<svg xmlns="http://www.w3.org/2000/svg" width="240" height="300"><rect width="240" height="300" fill="#3c8dbc"/></svg>'))
    page.route('http://gallery.test/missing.png',lambda route:route.fulfill(status=404,body='missing'))
    page.goto('http://gallery.test/')
    page.evaluate('''() => {window.esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}''')
    page.add_style_tag(path=str(ROOT/'public/review-details.css'))
    page.add_script_tag(path=str(ROOT/'public/subsidies.js'))
    page.evaluate('''() => {
      document.querySelector('#first').innerHTML=subsidyPictures(['/a.svg','javascript:alert(1)','/b.svg','/missing.png']);
      document.querySelector('#second').innerHTML=subsidyPictures('/a.svg');
      attachSubsidyPictures();
    }''')
    page.locator('#first .subsidy-picture').nth(1).click()
    assert page.locator('.subsidy-gallery figcaption').inner_text()=='2 / 3'
    page.wait_for_function("document.querySelector('.subsidy-gallery img').naturalWidth===240")
    assert len(page.context.pages)==1
    page.screenshot(path=str(ROOT/'visual-baseline/verified/subsidy-gallery-fixture.png'))
    page.keyboard.press('ArrowRight')
    page.locator('.subsidy-gallery [role=alert]').wait_for()
    assert page.locator('.subsidy-gallery figcaption').inner_text()=='3 / 3'
    assert page.locator('.subsidy-gallery img').is_hidden()
    page.keyboard.press('ArrowRight')
    page.wait_for_function("document.querySelector('.subsidy-gallery img').naturalWidth===300")
    assert page.locator('.subsidy-gallery figcaption').inner_text()=='1 / 3'
    page.locator('.subsidy-gallery-prev').click()
    page.locator('.subsidy-gallery [role=alert]').wait_for()
    page.keyboard.press('Escape')
    page.locator('.subsidy-gallery').wait_for(state='detached')
    page.locator('#second .subsidy-picture').click()
    assert page.locator('.subsidy-gallery figcaption').inner_text()=='1 / 1'
    assert page.locator('.subsidy-gallery-next').is_hidden()
    page.locator('.subsidy-gallery-close').click()
    page.locator('.subsidy-gallery').wait_for(state='detached')
    page.locator('#second .subsidy-picture').click()
    page.mouse.click(5,5)
    page.locator('.subsidy-gallery').wait_for(state='detached')
    page.locator('#first .subsidy-picture').first.click()
    page.evaluate("location.hash='another-page'")
    page.wait_for_function("!document.querySelector('.subsidy-gallery')")
    assert not errors,errors
    browser.close()
    print('PASS: clicked-image start, row isolation, navigation, failed image recovery, close/Escape/backdrop/route cleanup, no new tab (fixture data).')
