import requests
r=requests.get('http://127.0.0.1:3010/api/v1/members?limit=1&offset=0');print(r.status_code,r.headers.get('content-type'));print(r.text[:500])
