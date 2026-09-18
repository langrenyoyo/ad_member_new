from pathlib import Path
p=Path('backend/app/main_from_txt.py'); s=p.read_text(encoding='utf-8')
block='    if username: q = username\n    if name: q = name\n    if game_name: q = game_name\n    if parent_id is not None: conditions.append(Member.parent_id == parent_id)\n'
# remove only occurrence before list_members
idx=s.index('def list_games'); a=s.index(block,idx); s=s[:a]+s[a:].replace(block,'',1)
# ensure member has game_name line
m=s.index('def list_members'); tail=s[m:]; target='    if name: q = name\n'; assert target in tail
if '    if game_name: q = game_name\n' not in tail[:tail.index('    if parent_id')]: tail=tail.replace(target,target+'    if game_name: q = game_name\n',1); s=s[:m]+tail
p.write_text(s,encoding='utf-8')
