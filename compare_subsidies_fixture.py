"""Read-only subsidy-list comparison with identical three-row browser fixtures."""
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

OUT = Path("visual-baseline/fixtures/subsidies")
OUT.mkdir(parents=True, exist_ok=True)

rows = []
for i, status in enumerate((0, 1, 2)):
    rows.append({
        "id": 9300 + i, "user_id": 8300 + i, "username": f"对比账号{i}",
        "vip": i, "parent_id": 0, "parent_username": "", "parent_name": "上级昵称",
        "game_id": 7300, "game_name": "对比游戏", "agent_id": 6300,
        "agent_name": "对比主体", "name": "测试会员", "tx_price": (0.01, 12.5, 9999.99)[i],
        "pics": ["https://img.example.test/a.svg", "https://img.example.test/b.svg"] if i == 0 else [],
        "receive_name": "收件人<&>", "receive_tel": "13800000000",
        "price": (0.01, 12.0, 9999.0)[i], "status": status,
        "sub_msg": "拒绝原因 <>&" if status == 2 else "",
        "created_at": "2026-09-16T00:00:00Z", "updated_at": "2026-09-16T00:00:00Z",
    })
ref_rows = [{**r, "status": 4 if r["status"] == 2 else r["status"],
             "user": {"id": r["user_id"], "username": r["username"], "vip": r["vip"],
                      "parent_id": 0, "parent_username": "", "parent_name": r["parent_name"], "name": r["name"]},
             "game": {"name": r["game_name"]}, "agent": {"name": r["agent_name"]},
             "create_time": 1789516800, "update_time": 1789516800} for r in rows]
(OUT / "data.json").write_text(json.dumps({"local": rows, "reference": ref_rows}, ensure_ascii=False, indent=2), encoding="utf-8")

import os
from decimal import Decimal
summary = {key:float(sum((Decimal(str(r["price"])) for r in rows if r["status"]==status),Decimal(0)))
           for key,status in (("paid",1),("pending",0))}
payload={"total":3,"rows":ref_rows,"extend":{"tixian1":summary["paid"],"tixian2":summary["pending"]}}
report={"comparison_valid":False,"browser_capture":False,"rows":3}
def save_report():
    (OUT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
save_report()
if os.getenv("SUBSIDY_COMPARE_CAPTURE") != "1":
    print(json.dumps(report))
    raise SystemExit(0)
blocked=[]
try:
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(timezone_id="Asia/Shanghai")
        def picture(route):
            color="#18bc9c" if route.request.url.endswith("a.svg") else "#3c8dbc"
            route.fulfill(content_type="image/svg+xml",body=f'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><rect width="40" height="40" fill="{color}"/></svg>')
        context.route("https://img.example.test/**",picture)
        ref=context.new_page()
        ref.set_viewport_size({"width":1690,"height":1030})
        ref.set_default_timeout(15000)
        base="https://ad.leadink.cn/DmvTqXBpfF.php"
        def reference_route(route):
            req=route.request
            path=urlparse(req.url).path
            if path.endswith("/butie/index") and req.resource_type in ("xhr","fetch"):
                return route.fulfill(json=payload)
            if req.method not in ("GET","HEAD") and not path.endswith("/index/login"):
                blocked.append({"method":req.method,"path":path})
                return route.abort()
            return route.fallback()
        ref.route("**/*",reference_route)
        print("Reference login",flush=True)
        ref.goto(base+"/index/login",wait_until="domcontentloaded")
        ref.fill("[name=username]","18532306918")
        ref.fill("[name=password]","123456")
        ref.locator("button[type=submit],input[type=submit]").first.click()
        ref.locator('a[href*="butie?ref=addtabs"]').wait_for(state="attached")
        ref.goto(base+"/butie",wait_until="networkidle")
        ref.wait_for_function("window.jQuery && jQuery('#table').data('bootstrap.table')")
        ref.locator("button[name=commonSearch]").click()
        ref.locator("input[name=user_id]").wait_for(state="hidden")
        ref.evaluate("""data=>{
            jQuery('#table').bootstrapTable('load',data);
            jQuery('#table').bootstrapTable('hideLoading');
            jQuery('#tixian1').text(data.extend.tixian1);
            jQuery('#tixian2').text(data.extend.tixian2);
        }""",payload)
        assert ref.locator("#table tbody tr[data-index]").count()==3
        assert ref.evaluate("jQuery('#table').bootstrapTable('getData').map(r=>r.id)")==[r["id"] for r in rows]
        print("Reference fixture ready",flush=True)
        local=context.new_page()
        local.set_viewport_size({"width":1920,"height":1080})
        local.set_default_timeout(15000)
        local.route("**/api/v1/subsidies?*",lambda route:route.fulfill(json={"total":3,"items":rows,"summary":summary}))
        local.goto("http://127.0.0.1:3000/#subsidies")
        local.fill("#loginForm [name=username]","18532306918")
        local.fill("#loginForm [name=password]","123456")
        local.locator("#loginForm").evaluate("f=>f.requestSubmit()")
        local.locator("#reviewSearchToggle").click()
        local.locator("#reviewFilters").wait_for(state="hidden")
        assert local.locator("[data-review-cell=id]").all_inner_texts()==[str(r["id"]) for r in rows]
        layout={}
        for name,page,table in (("reference",ref,"#table"),("local",local,".withdrawal-panel .ads-table")):
            page.evaluate("document.fonts.ready")
            page.mouse.move(0,0)
            page.wait_for_function("Array.from(document.querySelectorAll('tbody img')).every(i=>i.complete && i.naturalWidth>0)")
            layout[name]=page.locator(table).evaluate("""table=>({
                table:table.getBoundingClientRect().toJSON(),
                headers:[...table.querySelectorAll('thead th')].filter(n=>n.getClientRects().length).map(n=>({text:n.textContent.trim(),rect:n.getBoundingClientRect().toJSON()})),
                rows:[...table.querySelectorAll('tbody tr')].map(n=>({text:n.textContent.trim(),rect:n.getBoundingClientRect().toJSON()}))
            })""")
            options={} if name=="reference" else {"clip":{"x":230,"y":50,"width":1690,"height":1030}}
            page.screenshot(path=str(OUT/(name+".png")),**options)
        (OUT/"layout.json").write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding="utf-8")
        assert layout['reference']['table']['height']==layout['local']['table']['height']==183
        assert all(row['rect']['height']==47 for side in layout.values() for row in side['rows'])
        assert [h['text'] for h in layout['reference']['headers']]==[h['text'].replace('▲','').replace('▼','').replace('▴','').replace('▾','').strip() for h in layout['local']['headers']]
        searches=[]
        for field,reference_field in [('user_id','user_id'),('username','user.username'),('receive_name','receive_name'),('receive_tel','receive_tel')]:
            with ref.expect_request(lambda request:'/butie/index?' in request.url) as event:
                ref.locator(f'#table tbody tr[data-index="0"] .searchit[data-field="{reference_field}"]').click()
            reference_query=parse_qs(urlparse(event.value.url).query)
            reference_filter=json.loads(reference_query['filter'][0])
            reference_operate=json.loads(reference_query['op'][0])
            assert str(reference_filter[reference_field])==str(rows[0][field])
            assert reference_operate[reference_field]==('LIKE' if field=='username' else '=')
            with local.expect_request(lambda request:'/api/v1/subsidies?' in request.url) as event:
                local.locator(f'[data-review-search="{field}"]').first.click()
            local_query=parse_qs(urlparse(event.value.url).query)
            assert local_query[field]==[str(rows[0][field])]
            local.wait_for_function("!document.querySelector('#reviewError')?.textContent")
            searches.append({'field':field,'value':str(rows[0][field]),'reference_filter':reference_filter,'reference_operate':reference_operate,'local_query':local_query})
        (OUT/'searches.json').write_text(json.dumps(searches,ensure_ascii=False,indent=2),encoding='utf-8')
        browser.close()
    a=Image.open(OUT/"reference.png").convert("RGB")
    b=Image.open(OUT/"local.png").convert("RGB")
    assert a.size==b.size==(1690,1030)
    diff=ImageChops.difference(a,b)
    diff.save(OUT/"diff.png")
    report.update(comparison_valid=True,browser_capture=True,reference_live=True,
        scope="Three identical subsidy records, loaded images, collapsed filters; content area only",
        mean_rgb=sum(ImageStat.Stat(diff).mean)/3,
        changed_pixel_ratio=sum(max(px)>10 for px in diff.getdata())/(a.width*a.height))
except Exception as error:
    report["error"]=str(error)
    raise
finally:
    report["blocked_requests"]=blocked
    save_report()
print(json.dumps(report,ensure_ascii=False))
