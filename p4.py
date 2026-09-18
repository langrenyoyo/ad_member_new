from pathlib import Path
p=Path('backend/app/main_from_txt.py'); s=p.read_text(encoding='utf-8'); s=s.replace('    if name: q = name\n    if parent_id', '    if name: q = name\n    if game_name: q = game_name\n    if parent_id',1); p.write_text(s,encoding='utf-8')
