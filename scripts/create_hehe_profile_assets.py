from pathlib import Path
import html
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/hehe-profile-refresh'
out.mkdir(parents=True,exist_ok=True)
res=root/'apk/guangjiyexing/app/src/main/res/drawable'
C='#B5521B'; O='#ED9850'; L='#F9D4AC'; P='#FFF1E4'; W='#FFFFFF'
def circle(x,y,r):return f'M{x-r},{y}a{r},{r} 0,1 0 {2*r},0a{r},{r} 0,1 0 -{2*r},0'
def box(x,y,w,h,r=8):return f'M{x+r},{y}h{w-2*r}q{r},0 {r},{r}v{h-2*r}q0,{r} -{r},{r}h-{w-2*r}q-{r},0 -{r},-{r}v-{h-2*r}q0,-{r} {r},-{r}Z'
def asset(name,w,h,paths):
    xml=f'<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="{w}dp" android:height="{h}dp" android:viewportWidth="{w}" android:viewportHeight="{h}">'
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
    for d,fill in paths:
        xml+=f'<path android:fillColor="{fill}" android:pathData="{d}"/>'
        svg+=f'<path fill="{fill}" d="{d}"/>'
    (res/(name+'.xml')).write_text(xml+'</vector>',encoding='utf-8')
    (out/(name+'.svg')).write_text(svg+'</svg>',encoding='utf-8')

asset('hehe_avatar',100,100,[(circle(50,50,50),P),(circle(50,50,41),'#FBE2C5'),('M48,72V40h5v32Z',C),('M50,52C26,53 24,34 26,28C44,28 54,35 50,52Z',O),('M51,43C51,25 64,19 78,21C78,38 65,47 51,43Z',C),('M29,73Q50,60 72,73L68,80H33Z',C),('M34,34L47,46L45,48L32,37Z','#FFEBD4'),('M58,36L69,26L71,28L60,38Z',L)])
asset('hehe_coins',64,64,[(box(6,28,33,27,9),O),(circle(39,27,20),C),(circle(39,27,15),'#FFD89F'),('M37,16h4v22h-4Z',C),('M29,24h20v3H29Z M32,31h14v3H32Z',C)])
asset('hehe_invite',64,64,[(circle(32,32,29),P),('M18,40L24,58L32,52L40,58L46,40Z',O),(circle(32,27,20),C),(circle(32,27,15),'#FFD9AC'),('M30,15h4v24h-4Z M20,22Q32,21 32,31Q20,32 20,22Z M44,18Q32,18 32,28Q44,29 44,18Z',C)])
asset('hehe_balance_strip',300,56,[(box(0,0,300,56,14),'#FFF8F1')])
asset('hehe_wallet_card',150,154,[(box(0,0,150,154,18),P),(circle(125,140,55),'#FBE3C9'),('M57,88L116,73Q123,72 125,80L128,105L58,116Z',C),('M67,85L111,76L114,83L69,92Z',W),(box(48,91,91,57,12),O),(box(102,108,38,23,8),C),(circle(114,119,4),'#FFE3BD'),('M57,101h34v3H57Z','#FFD9AC')])
asset('hehe_income_card',140,71,[(box(0,0,140,71,18),P),(circle(133,61,35),'#FBE3C9'),('M112,15h23v47l-6,-4 -6,4 -6,-4 -5,4Z',C),('M116,19h15v34h-15Z','#FFE3BD'),('M119,26h9v3h-9Z M119,33h9v3h-9Z M119,40h6v3h-6Z',O)])
asset('hehe_subsidy_card',140,71,[(box(0,0,140,71,18),P),(circle(133,61,35),'#FBE3C9'),(box(108,34,30,28,5),O),(box(105,29,35,10,3),C),('M120,30h6v32h-6Z','#FFE3BD'),('M122,28C102,26 111,8 122,23C133,8 146,26 124,28L124,23C134,22 133,18 130,20L123,28L116,20Q110,18 115,23Z',C)])

profile=root/'apk/guangjiyexing/app/src/main/java/com/example/idiomquiz/ui/MobanProfile.kt'
s=profile.read_text(encoding='utf-8')
for a,b in {'moban_avatar':'hehe_avatar','orange_balance_strip':'hehe_balance_strip','moban_coins':'hehe_coins','orange_wallet_card':'hehe_wallet_card','orange_income_card':'hehe_income_card','orange_subsidy_card':'hehe_subsidy_card','moban_crown':'hehe_invite'}.items():s=s.replace('R.drawable.'+a,'R.drawable.'+b)
profile.write_text(s,encoding='utf-8')

def img(n,cls=''):return f'<img class="{cls}" src="{n}.svg">'
navpaths=['M3 4q5-2 9 1q4-3 9-1v16q-5-2-9 1q-4-3-9-1z M12 5v16','M3 9h18v4H3z M5 13v8h14v-8 M12 9v12 M12 9C2 9 5 0 12 9C19 0 22 9 12 9','M3 9h18v4H3z M5 13v8h14v-8 M12 9v12 M12 9C2 9 5 0 12 9C19 0 22 9 12 9','M15 20H3v-2q0-6 12-6 M10 3a4 4 0 1 0 0 8a4 4 0 1 0 0-8 M19 7v8 M15 11h8','M12 3a4 4 0 1 0 0 8a4 4 0 1 0 0-8 M3 21v-2q0-7 9-7q9 0 9 7v2z']
page='''<!doctype html><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;color:#443125;background:#fffaf5;font-family:'Microsoft YaHei',sans-serif}.status{height:40px;background:#fafafa;padding:11px 18px;display:flex;justify-content:space-between;font-size:13px}.head{position:absolute;top:40px;height:250px;width:100%;background:linear-gradient(110deg,#fff0e3,#fffbf7);z-index:-1}.identity{display:flex;align-items:center;gap:14px;padding:28px 20px 32px}.identity img{width:70px;height:70px}.identity b{font-size:19px}.identity p{font-size:11px;margin:12px 0 0}.card{margin:0 16px;background:white;border-radius:28px;padding:16px;box-shadow:0 3px 5px #3d2e2420}.balance{height:56px;background:url(hehe_balance_strip.svg) center/100% 100%;display:flex;align-items:center;padding:0 14px;gap:10px}.balance img{width:28px;height:28px}.balance b{font-size:15px;flex:1}.balance strong{font-size:19px}.metrics{display:flex;text-align:center;margin-top:20px}.metrics div{flex:1}.metrics b{display:block;font-size:28px;color:#b5521b;line-height:40px}.metrics small{display:block;color:#817568;font-size:11px;margin-top:6px}.secondary{background:#fff0e3;border-radius:18px;padding:14px 0}.secondary b{font-size:22px;color:#443125;line-height:30px}.secondary div+div{border-left:1px solid #efddcf}.features{display:flex;gap:12px;height:154px;margin-top:18px}.tile{border-radius:18px;background-size:100% 100%;position:relative;overflow:hidden}.wallet{flex:1.08;background-image:url(hehe_wallet_card.svg);padding:16px}.tile b{font-size:15px;color:#b5521b;display:block;line-height:22px}.wallet b{font-size:16px}.tile small{font-size:10px;color:#b5521b;display:block;margin-top:4px}.wallet small{font-size:11px}.right{flex:1;display:flex;flex-direction:column;gap:12px}.right .tile{flex:1;padding:14px}.income{background-image:url(hehe_income_card.svg)}.subsidy{background-image:url(hehe_subsidy_card.svg)}.invite{display:flex;align-items:center;gap:8px;margin:16px;padding:10px 12px;background:linear-gradient(100deg,#fff0e3,#fffbf7);border-radius:12px;min-height:56px}.invite img{width:24px}.invite div{flex:1;font-size:12px;color:#b5521b;line-height:22px}.invite span{color:#443125;font-size:13px}.invite strong{background:white;border-radius:24px;padding:8px 14px;color:#b5521b;font-size:12px}.nav{position:absolute;bottom:0;background:white;width:100%;height:88px;display:flex;align-items:center;padding-bottom:8px}.nav div{flex:1;text-align:center;font-size:12px;color:#817568}.nav svg{width:24px;height:24px;display:block;margin:0 auto 8px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}.nav .selected{color:#443125}.nav .selected svg{color:#b5521b;background:#fff0e3;border-radius:24px;box-sizing:content-box;padding:5px 20px;margin-bottom:3px}.nav .reward{color:#b5521b;font-weight:bold}.nav .reward svg{width:30px;height:30px;color:white;background:#b5521b;padding:11px;box-sizing:content-box;border-radius:18px;box-shadow:0 4px 7px #44312530;margin-top:-12px;margin-bottom:8px}
</style><div class="status"><span>09:41</span><span>▴ ▴ ▴　▰</span></div><div class="head"></div>'''
page+='<div class="identity">'+img('hehe_avatar')+'<div><b>点击登录</b><p>ID：—　普通会员</p></div></div>'
page+='<div class="card"><div class="balance">'+img('hehe_coins')+'<b>余额</b><strong>—</strong></div><div class="metrics"><div><b>0</b><small>学习积分</small></div><div><b>0</b><small>累计答题</small></div></div><div class="metrics secondary"><div><b>0</b><small>答对题数</small></div><div><b>0</b><small>连续学习(天)</small></div><div><b>0</b><small>待复习</small></div></div><div class="features"><div class="tile wallet"><b>提现中心</b><small>可申请提现</small></div><div class="right"><div class="tile income"><b>收支明细</b><small>查看收支流水</small></div><div class="tile subsidy"><b>补贴入口</b><small>申请补贴</small></div></div></div></div>'
page+='<div class="invite">'+img('hehe_invite')+'<div>我的邀请码 · 普通会员<br><span>查看邀请资格</span></div><strong>查看邀请</strong></div><div class="nav">'
for i,(label,path) in enumerate(zip(['学习','福利','奖励','邀请','我的'],navpaths)):
    page+=f'<div class="{ "reward" if i==2 else "selected" if i==4 else ""}"><svg viewBox="0 0 24 24"><path d="{path}"/></svg>{label}</div>'
page+='</div>'
(out/'profile-preview.html').write_text(page,encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    tab=browser.new_page(viewport={'width':360,'height':813},device_scale_factor=3)
    tab.goto((out/'profile-preview.html').as_uri())
    tab.wait_for_function('Array.from(document.images).every(i=>i.complete && i.naturalWidth>0)')
    tab.screenshot(path=str(out/'hehe-profile-preview.png'))
    browser.close()
print('Assets integrated. Preview is a static illustration, not a device screenshot.')
