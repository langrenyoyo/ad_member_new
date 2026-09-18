from pathlib import Path
p=Path('backend/app/main_from_txt.py'); s=p.read_text()
s=s.replace('    q: str | None = None,\n    agent_id: int | None = None,\n    game_id: int | None = None,','    q: str | None = None,\n    username: str | None = None,\n    name: str | None = None,\n    parent_id: int | None = None,\n    game_name: str | None = None,\n    agent_id: int | None = None,\n    game_id: int | None = None,',1)
s=s.replace('    conditions: list[Any] = []\n    if agent_id is not None:', '    conditions: list[Any] = []\n    if username: q = username\n    if name: q = name\n    if parent_id is not None: conditions.append(Member.parent_id == parent_id)\n    if agent_id is not None:',1)
p.write_text(s)
