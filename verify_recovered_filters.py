import os
os.environ['DATABASE_URL']='sqlite://'
from backend.app import main_from_txt as m
m.Base.metadata.create_all(m.engine)
with m.SessionLocal() as s:
 s.add_all([m.Agent(id=1,name='Studio'),m.Game(id=1,name='Puzzle'),m.Game(id=2,name='Racing'),m.Member(id=1,username='alpha',name='Alice',game_id=1,agent_id=1),m.Member(id=2,username='beta',name='Alice',game_id=2,parent_id=1)])
 s.commit()
def query(**kw):
 args=dict(member_id=None,status_filter=None,is_white=None,exchange_enable=None,limit=20,offset=0)
 args.update(kw)
 return m.list_members(**args)
assert query(username='alpha',name='Alice')['total']==1
assert query(username='alpha',name='Nobody')['total']==0
assert query(game_name='Puzzle')['items'][0]['id']==1
assert query(game_name='Missing')['total']==0
assert query(username='%',game_name='Puzzle')['total']==0
assert m.list_games(status_filter=None,limit=20,offset=0)['total']==2
assert query(member_id=2)['items'][0]['username']=='beta'
assert query(member_id=999)['total']==0
assert query(member_id=2,username='alpha')['total']==0
assert query(agent_name='Studio')['total']==1
assert query(agent_name='%')['total']==0
assert query(member_id=1)['items'][0]['game_name']=='Puzzle'
assert query(member_id=1)['items'][0]['agent_name']=='Studio'
assert query(member_id=2)['items'][0]['parent_name']=='Alice'
print('Recovered source: 14 query assertions passed')
m.engine.dispose()
