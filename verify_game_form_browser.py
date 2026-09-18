"""Synthetic browser verification for global and scoped game create/edit forms."""
import json
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect

game = {
    "id": 237, "agent_id": 133, "name": "Fixture game", "game_icon": "",
    "game_key": "fixture.game", "game_url": "https://fixture.invalid/game", "game_type": 0,
    "game_ad_status": 1, "game_lottery_num": 0, "status": 1, "ad_status": 1,
    "lucky_enable": 1, "is_landscape": 0, "is_game": 1, "is_mobile": 0, "is_imei": 0,
    "raffle_num": 500, "star_countdown": 30, "over_countdown": 50,
    "star_coin": 0.01, "over_coin": 0.01, "coin_get": 1000000, "exchange_num": 10,
    "commission_status": 0, "commission_source": 0, "commission_rate": 0,
    "tixian_price": "", "tixian_coin": "", "tixian_wx": 0, "wx_appid": "",
    "wx_secert": "", "other_url": "", "settings_json": "{}",
}

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    writes = []
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def fixture(route):
        request = route.request
        url = urlparse(request.url)
        path = url.path.removeprefix("/api/").removeprefix("v1/").lstrip("/")
        if path == "auth/login":
            route.fulfill(json={"access_token": "fixture", "user": {"username": "fixture"}})
            return
        if request.method != "GET":
            writes.append({"method": request.method, "path": path, "body": request.post_data_json})
            route.fulfill(json={**game, **request.post_data_json})
            return
        if path == "games":
            route.fulfill(json={"items": [game], "total": 1})
            return
        if path == "games/237":
            route.fulfill(json=game)
            return
        if path.startswith("member-filter-options/agents"):
            route.fulfill(json={"items": [{"id": 133, "name": "主体 A"}, {"id": 134, "name": "主体 B"}], "total": 2})
            return
        if path == "agents/133":
            route.fulfill(json={"id": 133, "name": "主体 A"})
            return
        route.fulfill(json={"items": [], "total": 0})

    page.route("**/api/**", fixture)
    page.goto("http://127.0.0.1:3000/#games")
    page.fill("#loginForm [name=username]", "fixture")
    page.fill("#loginForm [name=password]", "fixture")
    page.locator("#loginForm").evaluate("f=>f.requestSubmit()")
    page.locator("[data-edit='237']").wait_for()

    page.locator("#createButton").click()
    expect(page.locator(".game-form-fields")).to_be_visible()
    expect(page.locator("#editorForm [name=agent_id]")).to_be_visible()
    assert page.locator(".game-form-field").count() == 30
    page.locator("#editorForm [name=agent_id]").select_option("133")
    page.locator("#editorForm [name=name]").fill("Created game")
    page.locator("#editorForm [name=raffle_num]").fill("800")
    page.locator("#editorForm [name=settings_json]").fill('{"mode":"fixture"}')
    page.locator("#editorForm").evaluate("f=>f.requestSubmit()")
    page.wait_for_function("document.querySelector('#modal').hidden")
    assert writes[-1]["method"] == "POST" and writes[-1]["path"] == "games"
    assert writes[-1]["body"]["raffle_num"] == 800 and writes[-1]["body"]["agent_id"] == 133

    page.locator("[data-edit='237']").click()
    page.locator("#editorForm [name=commission_rate]").fill("2.5")
    page.locator("#editorForm").evaluate("f=>f.requestSubmit()")
    page.wait_for_function("document.querySelector('#modal').hidden")
    assert writes[-1]["method"] == "PATCH" and writes[-1]["body"]["commission_rate"] == 2.5

    page.locator("#createButton").click()
    page.locator("#editorForm [name=name]").fill(" ")
    page.locator("#editorForm").evaluate("f=>f.requestSubmit()")
    expect(page.locator(".game-form-error")).to_have_text("游戏名称不能为空")
    assert len(writes) == 2
    page.locator("#editorForm [name=name]").fill("Invalid JSON")
    page.locator("#editorForm [name=settings_json]").fill("{")
    page.locator("#editorForm").evaluate("f=>f.requestSubmit()")
    expect(page.locator(".game-form-error")).to_have_text("高级配置 JSON 格式无效")
    assert len(writes) == 2

    page.evaluate("sessionStorage.setItem('agent-dashboard-id','133'); location.hash='agent-games'")
    page.locator("[data-game-edit='237']").wait_for()
    page.locator("#agentGameCreate").click()
    expect(page.locator(".game-form-fields")).to_be_visible()
    assert page.locator("#editorForm [name=agent_id]").get_attribute("type") == "hidden"
    assert page.locator("#editorForm [name=agent_id]").input_value() == "133"
    page.set_viewport_size({"width": 390, "height": 844})
    box = page.locator("#modal > .modal").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 390
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path="visual-baseline/verified/game-form-mobile.png", full_page=True)
    page.locator("#editorForm [name=name]").fill("Scoped game")
    page.locator("#editorForm").evaluate("f=>f.requestSubmit()")
    page.wait_for_function("document.querySelector('#modal').hidden")
    assert writes[-1]["body"]["agent_id"] == 133
    assert not errors, errors
    print(json.dumps({"passed": True, "writes": len(writes), "fields": 30}))
    browser.close()
