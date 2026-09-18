import json
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
m={'dash':'dashboard','gameuser':'members','agent':'agents','game':'games','ad':'ads','tixian':'withdrawals','butie':'subsidies','profit-coinlog':'coin-logs','risk-userw':'risk-whitelist','risk-risk':'risk-history','risk-userd':'risk-devices','general-profile':'profile','book':'book'}
root=Path('visual-baseline'); out=[]
for ref,name in m.items():
 a=root/'reference-captured'/f'{ref}.png'; b=root/'local'/f'page-{list(m.values()).index(name)}.png'
 if not a.exists() or not b.exists(): out.append({'page':name,'status':'missing'}); continue
 ia,ib=Image.open(a).convert('RGB'),Image.open(b).convert('RGB'); ia=ia.crop((230,50,1920,1080)); ib=ib.crop((230,50,1920,1080)); d=ImageChops.difference(ia,ib); mean=sum(ImageStat.Stat(d).mean)/3; ratio=sum(max(p)>10 for p in d.getdata())/(ia.width*ia.height); out.append({'page':name,'mean_rgb':round(mean,2),'diff_ratio':round(ratio,4)})
(root/'content-comparison.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8'); print(json.dumps(out,ensure_ascii=False,indent=2))
