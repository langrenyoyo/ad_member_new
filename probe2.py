import requests
for u in ['http://127.0.0.1:8010/api/v1/games?limit=1','http://127.0.0.1:8010/api/v1/members?limit=1&game_name=x']:
 try:
  r=requests.get(u,timeout=5); print(u,r.status_code,r.text[:120])
 except Exception as e: print(e)
