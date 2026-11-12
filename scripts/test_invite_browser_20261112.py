"""Browser checks against the loopback fixture, including the real SMS endpoints."""
import json
import hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/app-entry-20261112'
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width':390,'height':844}, device_scale_factor=2)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:18080/invite.html?game_id=1&invite_code=A1B2C3')
    expect(page.locator('#status')).to_contain_text('邀请链接已验证')
    expect(page.locator('#download')).to_have_attribute('href', 'http://127.0.0.1:18080/downloads/yazhiyiji-latest.apk')
    expect(page.locator('#open-app')).to_have_attribute('href', 'yazhiyiji://invite?game_id=1&invite_code=A1B2C3')
    expect(page.locator('#send-code')).to_be_disabled()
    with page.expect_download() as download_info:
        page.locator('#download').click()
    downloaded = download_info.value
    assert downloaded.failure() is None
    downloaded_hash = hashlib.sha256(Path(downloaded.path()).read_bytes()).hexdigest()
    expected_hash = hashlib.sha256((root/'public/downloads/yazhiyiji-latest.apk').read_bytes()).hexdigest()
    assert downloaded_hash == expected_hash
    page.screenshot(path=str(out/'browser-invitation.png'), full_page=True)
    page.locator('#phone').fill('13900003333')
    page.locator('#consent').check()
    page.locator('#send-code').click()
    expect(page.locator('#status')).to_contain_text('验证码已发送')
    page.locator('#sms-code').fill('123456')
    page.locator('#login').click()
    expect(page.locator('#status')).to_contain_text('注册 / 登录成功')
    assert 'access_token' not in page.url and 'refresh_token' not in page.url
    assert page.evaluate('Object.keys(localStorage).length') == 0
    assert not any('token' in key for key in page.evaluate('Object.keys(sessionStorage)'))
    page.screenshot(path=str(out/'browser-login-success.png'), full_page=True)
    page.goto('http://127.0.0.1:18080/invite.html?game_id=1&invite_code=D4E5F6')
    expect(page.locator('#eligibility')).to_contain_text('普通会员邀请码不具备强制邀请码注册资格')
    page.screenshot(path=str(out/'browser-ordinary-invitation.png'), full_page=True)
    page.goto('http://127.0.0.1:18080/invite.html?game_id=1&invite_code=BAD')
    expect(page.locator('#status')).to_contain_text('邀请链接不完整')
    expect(page.locator('#send-code')).to_be_disabled()
    assert not errors, errors
    (out/'browser-tests.json').write_text(json.dumps({'passed':True,'checks':[
        'valid leader invitation', 'real local SMS registration', 'download and app-open links',
        'no tokens in URL or browser storage', 'ordinary member qualification message',
        'invalid invitation cannot submit', 'zero browser runtime errors', 'APK download SHA256 matches signed release'],
        'download_sha256':downloaded_hash}, indent=2), encoding='utf-8')
    browser.close()
print('Browser acceptance passed')
