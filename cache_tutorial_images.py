import json,re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen
source=Path('public/target-book.json')
data=json.loads(source.read_text(encoding='utf-8-sig'))
rows=data.get('items',data.get('rows',[]))
urls=sorted({url for row in rows for url in re.findall(r'src="([^"]+)"',row.get('content','')) if url.startswith('https://api.xmchujian.com/uploads/')})
out=Path('public/assets/tutorial');out.mkdir(parents=True,exist_ok=True)
def fetch(url):
    path=out/url.rsplit('/',1)[-1]
    try:
        with urlopen(url,timeout=15) as response: body=response.read()
        if not body.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Invalid PNG')
        path.write_bytes(body)
        return url,'/assets/tutorial/'+path.name
    except Exception as error:
        print(path.name,type(error).__name__)
        return url,None
with ThreadPoolExecutor(max_workers=4) as pool: mappings=dict(pool.map(fetch,urls))
for row in rows:
    for original,local in mappings.items():
        if local:row['content']=row.get('content','').replace(original,local)
source.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('Cached',sum(value is not None for value in mappings.values()),'of',len(urls),'images')
