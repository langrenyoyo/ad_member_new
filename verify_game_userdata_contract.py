# -*- coding: utf-8 -*-
"""Structural browser contract checks for the game-user dialog."""
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:3000"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(5000)
        page.goto(BASE + "/", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1000)
        # Existing sessions are accepted; otherwise perform the normal login flow.
        if page.locator("input[type=password]").count():
            page.locator("input[type=tel], input[name=phone], input[name=username]").first.fill("18532306918")
            page.locator("input[type=password]").fill("123456")
            page.locator("#loginForm .login-submit").click()
            page.wait_for_timeout(1000)
        page.goto(BASE + "/#games", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1500)
        trigger = page.locator(".game-user-open").first
        if not trigger.count():
            page.screenshot(path="visual-baseline/verified/contract-failure.png", full_page=True)
            raise AssertionError("games page has no game-user trigger")
        trigger.click()
        dialog = page.locator("[role=dialog], .game-user-dialog").last
        dialog.wait_for()
        tabs = dialog.locator("[role=tab]")
        assert tabs.count() == 7, f"expected 7 tabs, got {tabs.count()}"
        for i in range(7):
            tabs.nth(i).click()
            assert dialog.locator("[role=tabpanel]").count() >= 1
        tabs.nth(6).click()
        stats = dialog.locator(".game-user-stats")
        stats.wait_for()
        page.wait_for_function("document.querySelectorAll('[data-stat-chart] canvas').length===4")
        assert stats.locator(".game-stat-cards").count() == 1
        assert stats.locator("[data-stat-chart]").count() == 4
        tabs.nth(2).click()
        assert dialog.locator("form").count() >= 1
        assert dialog.locator("input, select, button").count() >= 1
        browser.close()

if __name__ == "__main__":
    main()
