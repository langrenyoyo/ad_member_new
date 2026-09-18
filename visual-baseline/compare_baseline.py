import json
import warnings
from pathlib import Path
from PIL import Image, ImageChops, ImageStat

root=Path(__file__).parent; m=json.loads((root/'manifest.json').read_text(encoding='utf-8')); out=[]
warnings.filterwarnings('ignore', category=DeprecationWarning)
for r in m['routes']:
    a,b=root/r['reference'],root/r['local']
    if not a.exists() or not b.exists(): out.append({"name":r['name'],"status":"missing"}); continue
    ia,ib=Image.open(a).convert('RGB'),Image.open(b).convert('RGB')
    # Reference captures are content-only; remove the 230px local sidebar for a like-for-like comparison.
    if ib.width == 1920 and ia.width == 1690:
        ib = ib.crop((230, 0, 1920, ib.height))
    if ia.width == 1920 and ib.width == 1690:
        ia = ia.crop((0, 0, 1690, ia.height))
    if ia.size!=ib.size: out.append({"name":r['name'],"status":"size-mismatch","reference":ia.size,"local":ib.size}); continue
    d=ImageChops.difference(ia,ib); mean=sum(ImageStat.Stat(d).mean)/3; ratio=sum(1 for p in d.getdata() if max(p)>10)/(ia.width*ia.height)
    diff=root/f"diff-{r['name']}.png"; d.save(diff)
    out.append({"name":r['name'],"status":"pass" if mean<=m['thresholds']['mean_rgb'] and ratio<=m['thresholds']['diff_ratio'] else "review","mean_rgb":round(mean,3),"diff_ratio":round(ratio,4),"diff":str(diff.relative_to(root))})
(root/'comparison-report.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(out,ensure_ascii=False,indent=2))
rows=''.join(f"<tr><td>{x['name']}</td><td>{x['status']}</td><td>{x.get('mean_rgb','')}</td><td>{x.get('diff_ratio','')}</td></tr>" for x in out)
(root/'comparison-report.html').write_text('<meta charset="utf-8"><h1>视觉基准对比</h1><table border="1"><tr><th>页面</th><th>状态</th><th>平均 RGB</th><th>差异像素占比</th></tr>'+rows+'</table>',encoding='utf-8')
