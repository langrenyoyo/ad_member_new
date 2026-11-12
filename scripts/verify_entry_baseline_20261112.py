"""Inspect the two pre-existing white-list failures without changing those tests."""
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
baseline = subprocess.check_output(['git','show','HEAD:backend/app/main_from_txt.py'], cwd=root).decode('utf-8')
current = (root/'backend/app/main_from_txt.py').read_text(encoding='utf-8')
marker = '@api.get("/risk/whitelist")'
def section(s):
    a = s.index(marker)
    return s[a:s.index('@api.get', a+len(marker))]
same = section(current) == section(baseline)
assert same
(root/'artifacts/app-entry-20261112/whitelist-baseline.txt').write_text(
    'Whitelist endpoint unchanged against HEAD: true\n'+section(current), encoding='utf-8')
print('Whitelist endpoint unchanged against HEAD')
