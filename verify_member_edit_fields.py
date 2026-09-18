"""Member editor prefill and changed-only requests with isolated fixtures."""
from playwright.sync_api import sync_playwright
import json
from pathlib import Path
from io import BytesIO
from PIL import Image

avatar=BytesIO()
Image.new('RGB',(2,2),'blue').save(avatar,format='PNG')

row={'id':9200,'username':'账号甲','name':'昵称甲','sex':2,'real_name':'真实姓名','card_no':'00123','address':'原地址','image_url':'https://example.com/avatar.png','device_id':'device-x','vip':7,'exchange_enable':1,'status':1,'is_white':0,'percent_zhi':12.5}
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080});writes=[]
    page.route('**/api/v1/member-images',lambda r:r.fulfill(status=201,json={'url':'/api/member-images/'+'a'*48+'.png'}))
    page.route('**/api/v1/members?*',lambda r:r.fulfill(json={'total':1,'items':[row],'permissions':{'create':True}}))
    def detail(route):
        if route.request.method=='PATCH':writes.append(route.request.post_data_json)
        route.fulfill(json=row)
    page.route('**/api/v1/members/9200',detail)
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    def open_editor():
        page.locator('[data-edit="9200"]').click();page.locator('#modal').wait_for(state='visible')
    open_editor()
    reference=json.loads(Path('visual-baseline/reference-verified/member-edit-controls.json').read_text(encoding='utf-8'))
    for group in reference:
        key=group['controls'][0]['name'][4:-1]
        if key not in ['is_true','realname_enable','raffle_open','exchange_enable','game_addiction_enable','is_white','status','ht_status']:continue
        actual=page.locator(f'#formFields [name={key}]').evaluate_all("els=>els.map(el=>({type:el.type,value:el.value,label:el.closest('label').textContent.trim()}))")
        expected=[{'type':c['type'],**c['options'][0]} for c in group['controls']]
        assert actual==expected,(key,actual,expected)
    assert page.locator('#formFields [name=exchange_enable][value="1"]').is_checked()
    assert page.locator('#formFields [name=is_white][value="0"]').is_checked()
    assert page.locator('#formFields [name=ht_status]:checked').count()==0
    assert page.locator('[data-member-tab-button]').all_text_contents()==['基础信息','抽奖设置','下载设置','代理设置']
    assert page.locator('[data-member-tab-button="basic"]').get_attribute('aria-selected')=='true'
    assert page.locator('[data-member-image-choose]').count()==1
    assert page.locator('[data-member-image-select]').count()==1
    page.locator('[data-member-image-select]').click()
    assert page.locator('.member-edit-error').inner_text()=='附件选择无权限'
    page.locator('[data-member-tab-button="basic"]').focus();page.keyboard.press('ArrowRight')
    assert page.locator('[data-member-tab-button="lottery"]').get_attribute('aria-selected')=='true'
    assert page.locator('[data-member-tab-button="basic"]').get_attribute('aria-selected')=='false'
    page.keyboard.press('End')
    assert page.locator('[data-member-tab-button="agent"]').get_attribute('aria-selected')=='true'
    page.keyboard.press('Home')
    assert page.locator('[data-member-tab-button="basic"]').get_attribute('aria-selected')=='true'
    assert page.locator('[data-member-tab="agent"]').count()==5
    for tab in ('basic','lottery','download','agent'):
        page.locator(f'[data-member-tab-button="{tab}"]').click()
        visible=page.locator('[data-member-tab]').evaluate_all("els=>els.filter(el=>el.getClientRects().length).map(el=>el.dataset.memberTab)")
        assert visible and set(visible)=={tab},(tab,visible)
    page.locator('[data-member-tab-button="basic"]').click()
    page.locator('[data-member-image-file]').set_input_files({'name':'avatar.png','mimeType':'image/png','buffer':avatar.getvalue()})
    page.locator('[data-member-image-preview]').wait_for()
    page.wait_for_function("document.querySelector('[name=image_url]').value.startsWith('/api/member-images/')")
    assert len(page.locator('[name=image_url]').input_value())<255
    valid_avatar=page.locator('[name=image_url]').input_value()
    assert page.locator('[data-member-image-preview]').is_visible()
    page.locator('[data-member-image-file]').set_input_files({'name':'large.png','mimeType':'image/png','buffer':b'0'*(2*1024*1024+1)})
    assert page.locator('.member-edit-error').inner_text()=='图片不能超过 2MB'
    assert page.locator('[name=image_url]').input_value()==valid_avatar
    page.locator('[data-member-tab-button="agent"]').click()
    assert page.locator('[data-member-tab="agent"]').first.is_visible()
    assert page.locator('[data-member-tab="basic"]').first.is_hidden()
    page.locator('[data-member-tab-button="lottery"]').click()
    assert page.locator('[data-member-tab-empty]').count()==0
    assert page.locator('[data-member-tab="lottery"]').count()==5
    reference_fields=json.loads(Path('visual-baseline/reference-verified/member-edit-fields.json').read_text(encoding='utf-8'))
    expected_groups=[group for group in reference_fields if group['fields'] and group['fields'][0]['name'] in ['row[raffle_open]','row[raffle_num]','row[star_countdown]','row[raffle_num2]','row[star_countdown2]']]
    actual_groups=page.locator('[data-member-tab="lottery"]').evaluate_all("els=>els.map(el=>({label:el.firstElementChild.textContent.trim(),fields:[...el.querySelectorAll('[name]')].map(input=>input.name)}))")
    assert actual_groups==[{'label':group['label'],'fields':[field['name'][4:-1] for field in group['fields']]} for group in expected_groups]
    assert page.locator('[name=raffle_num2]').is_visible()
    assert page.locator('[name=raffle_open][type=radio]').count()==2
    page.fill('[name=raffle_num2]','19')
    assert page.locator('[name=raffle_num2]').input_value()=='19'
    assert page.locator('[data-member-tab="agent"]').first.is_hidden()
    page.locator('[data-member-tab-button="download"]').click()
    assert page.locator('[name=down_load]').is_visible()
    assert page.locator('[name=raffle_num2]').is_hidden()
    page.locator('[data-member-tab-button="lottery"]').click()
    assert page.locator('[name=raffle_num2]').input_value()=='19'
    page.locator('[data-member-tab-button="basic"]').click()
    assert page.locator('#formFields [name=is_true]:checked').count()==0
    assert page.locator('#formFields [name=realname_enable]:checked').count()==0
    reference_geometry=json.loads(Path('visual-baseline/reference-verified/member-edit-geometry.json').read_text(encoding='utf-8'))
    window=page.locator('#modal>.modal').bounding_box()
    assert window==reference_geometry['window'],window
    assert page.locator('#modal .modal-head').bounding_box()['height']==45
    footer=page.locator('#modal .modal-actions').bounding_box()
    assert footer['height']==53 and footer['y']+53==window['y']+window['height']
    assert page.locator('#formFields [name=username]').bounding_box()['height']==33
    account=page.locator('#formFields [name=username]').bounding_box()
    expected_account=next(e['rect'] for e in reference_geometry['elements'] if e['name']=='row[username]')
    assert abs(account['x']-window['x']-expected_account['x'])<1
    assert abs(account['width']-expected_account['width'])<1
    assert page.locator('#editorForm [type=submit]').evaluate('el=>getComputedStyle(el).backgroundColor')=='rgb(68, 76, 105)'
    page.fill('#formFields [name=address]','临时修改')
    page.locator('#formFields [name=exchange_enable][value="0"]').check()
    page.locator('#formFields [name=is_true][value="1"]').check()
    page.select_option('#formFields [name=vip]','1')
    page.locator('#editorForm [type=reset]').click()
    assert page.locator('#formFields [name=address]').input_value()==row['address']
    assert page.locator('#formFields [name=exchange_enable][value="1"]').is_checked()
    assert page.locator('#formFields [name=vip]').input_value()=='7'
    assert page.locator('#formFields [name=is_true]:checked').count()==0
    assert not writes
    page.locator('[data-member-tab-button="agent"]').click()
    page.locator('#formFields [name=percent_dai_two]').scroll_into_view_if_needed()
    assert page.locator('#modal .modal-actions').bounding_box()==footer
    page.locator('[data-member-tab-button="basic"]').click()
    page.locator('.member-edit-fields').evaluate('el=>el.scrollTop=0')
    out=Path('visual-baseline/verified/member-edit');out.mkdir(parents=True,exist_ok=True)
    page.locator('#modal>.modal').screenshot(path=str(out/'local.png'))
    (out/'geometry.json').write_text(json.dumps({'window':window,'footer':footer,'scope':'local supported editor fields; reference window/header/footer sizes verified; full form parity remains incomplete'},indent=2),encoding='utf-8')
    for key in ['sex','card_no','device_id','real_name','address','percent_zhi','vip']:
        assert page.locator(f'#formFields [name={key}]').input_value()==str(row[key])
    page.locator('#editorForm [type=submit]').click();page.locator('#modal').wait_for(state='hidden');assert not writes
    open_editor();page.fill('#formFields [name=address]','新地址');page.select_option('#formFields [name=sex]','1')
    page.locator('#formFields [name=exchange_enable][value="0"]').check()
    page.locator('#formFields [name=is_true][value="1"]').check()
    page.locator('#formFields [name=status][value="0"]').check()
    page.locator('#formFields [name=is_white][value="1"]').check()
    page.locator('#formFields [name=realname_enable][value="1"]').check()
    page.locator('#editorForm [type=submit]').click();page.locator('#modal').wait_for(state='hidden')
    assert writes==[{'address':'新地址','sex':'1','is_true':1,'realname_enable':1,'exchange_enable':0,'status':0,'is_white':1}]
    assert all(type(writes[0][key]) is int for key in ('is_true','realname_enable','exchange_enable','status','is_white'))
    assert 'vip' not in writes[0] and 'card_no' not in writes[0]
    open_editor()
    page.locator('[data-member-tab-button="lottery"]').click()
    page.locator('[name=raffle_open][value="1"]').check()
    lottery_values={'raffle_num':'12','star_countdown':'3.5','over_countdown':'9','raffle_num2':'7','star_countdown2':'1.25','over_countdown2':'8.75'}
    for key,value in lottery_values.items():page.fill(f'[name={key}]',value)
    page.locator('#modal>.modal').screenshot(path=str(out/'lottery.png'))
    page.locator('[data-member-tab-button="download"]').click()
    page.fill('[name=down_load]','https://example.test/app.apk')
    page.locator('[data-member-tab-button="agent"]').click()
    page.fill('[name=percent_zhi]','20')
    page.locator('#editorForm [type=submit]').click()
    page.locator('#modal').wait_for(state='hidden')
    assert writes[-1]=={**lottery_values,'raffle_open':1,'down_load':'https://example.test/app.apk','percent_zhi':'20'}
    open_editor()
    extra=page.locator('[name=otherlevel]')
    assert extra.get_attribute('type') in (None,'text')
    assert extra.locator('xpath=..').locator('label').inner_text()=='其它信息:'
    extra.fill('临时内容');page.locator('#editorForm [type=reset]').click()
    assert extra.input_value()==''
    extra.fill('中文 <>& "quoted"')
    page.locator('[data-member-tab-button="download"]').click()
    page.locator('[data-member-tab-button="basic"]').click()
    assert extra.input_value()=='中文 <>& "quoted"'
    page.locator('#editorForm [type=submit]').click();page.locator('#modal').wait_for(state='hidden')
    assert writes[-1]=={'otherlevel':'中文 <>& "quoted"'}
    page.locator('#createButton').click()
    for name in ('password','pay_password'):
        assert page.locator(f'#formFields [name={name}]').get_attribute('type')=='password'
        assert page.locator(f'#formFields [name={name}]').get_attribute('autocomplete')=='new-password'
    browser.close()
print('Member editor: supported profile/state fields, sex/identity prefill, unchanged save, unknown stored value preservation and changed-only PATCH passed')
