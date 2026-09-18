"""Image-upload browser lifecycle using valid PNG fixtures and delayed responses."""
from io import BytesIO
from PIL import Image
from playwright.sync_api import sync_playwright

buffer=BytesIO();Image.new('RGB',(2,2),'blue').save(buffer,format='PNG')
file={'name':'avatar.png','mimeType':'image/png','buffer':buffer.getvalue()}
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page();uploads=[];writes=[];errors=[]
    row={'id':9200,'username':'fixture','image_url':'/original.png'}
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('**/api/auth/login',lambda r:r.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}}))
    page.route('**/api/v1/members?*',lambda r:r.fulfill(json={'total':1,'items':[row]}))
    def detail(r):
        if r.request.method=='PATCH':writes.append(r.request.post_data_json)
        r.fulfill(json=row)
    page.route('**/api/v1/members/9200',detail)
    page.route('**/api/v1/member-images',lambda r:uploads.append(r))
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    def open_editor():
        page.locator('[data-edit="9200"]').click();page.locator('#modal').wait_for(state='visible')
    def select():
        with page.expect_request('**/api/v1/member-images'):
            page.locator('[data-member-image-file]').set_input_files(file)
        page.wait_for_timeout(50)
        return uploads.pop()
    open_editor();first=select()
    assert page.locator('#editorForm [type=submit]').is_disabled()
    page.locator('#editorForm').evaluate('f=>f.requestSubmit()');assert not writes
    second=select();second.fulfill(status=201,json={'url':'/second.png'})
    page.wait_for_function("document.querySelector('[name=image_url]').value==='/second.png'")
    first.fulfill(status=201,json={'url':'/stale.png'})
    page.locator('#editorForm [type=reset]').click()
    page.wait_for_function("document.querySelector('[data-member-image-preview]').getAttribute('src')==='/original.png'")
    assert page.locator('[name=image_url]').input_value()=='/original.png'
    assert page.locator('[data-member-image-preview]').get_attribute('src')=='/original.png'
    pending=select();page.locator('#editorForm [type=reset]').click()
    pending.fulfill(status=201,json={'url':'/after-reset.png'})
    assert page.locator('#editorForm [type=submit]').is_enabled()
    failed=select();failed.fulfill(status=422,json={'detail':'invalid image fixture'})
    page.locator('.member-edit-error').get_by_text('invalid image fixture').wait_for()
    assert page.locator('[name=image_url]').input_value()=='/original.png'
    manual=select();page.fill('[name=image_url]','/manual.png')
    assert page.locator('[data-member-image-preview]').get_attribute('src')=='/manual.png'
    manual.fulfill(status=201,json={'url':'/must-not-overwrite.png'})
    page.wait_for_timeout(100)
    assert page.locator('[name=image_url]').input_value()=='/manual.png'
    assert page.locator('#editorForm [type=submit]').is_enabled()
    page.fill('[name=image_url]','');assert page.locator('[data-member-image-preview]').is_hidden()
    page.locator('#editorForm [type=reset]').click()
    late=select();page.locator('#closeModal').click();open_editor()
    late.fulfill(status=201,json={'url':'/closed.png'})
    assert page.locator('[name=image_url]').input_value()=='/original.png'
    final=select();final.fulfill(status=201,json={'url':'/api/member-images/'+'a'*48+'.png'})
    page.wait_for_function("document.querySelector('[name=image_url]').value.startsWith('/api/member-images/')")
    page.locator('#editorForm [type=submit]').click();page.locator('#modal').wait_for(state='hidden')
    assert writes==[{'image_url':'/api/member-images/'+'a'*48+'.png'}],writes
    assert not errors,errors
    browser.close()
print('Image browser lifecycle: pending save blocked, latest file wins, reset/close isolation, error retry and URL-only save passed')
