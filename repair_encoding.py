from pathlib import Path
import marshal, types, json

root = Path(__file__).parent
cache = root / 'backend/app/__pycache__/main.cpython-312.pyc'
saved = root / 'backend/main-recovery.cpython-312.pyc'
if not saved.exists():
    saved.write_bytes(cache.read_bytes())
code = marshal.loads(saved.read_bytes()[16:])
strings = set()
def collect(c):
    if isinstance(c, types.CodeType):
        for x in c.co_consts: collect(x)
    elif isinstance(c, (tuple, frozenset)):
        for x in c: collect(x)
    elif isinstance(c, str) and any(ord(x)>127 for x in c): strings.add(c)
collect(code)
p = root / 'backend/app/main.py'
s = p.read_text(encoding='utf-8-sig')
original = root / 'backend/main-before-encoding-repair.txt'
if not original.exists(): original.write_text(s, encoding='utf-8')
count = 0
for text in sorted(strings, key=len, reverse=True):
    for suffix in ['"', "'", '']:
        good = text + suffix
        bad = good.encode('utf-8').decode('cp936', errors='replace')
        # Windows PowerShell decoding uses '?' for invalid sequences.
        for broken in [bad, bad.replace('\ufffd','?')]:
            if broken != good and broken in s:
                count += s.count(broken)
                s = s.replace(broken, good)
p.write_text(s, encoding='utf-8')
print('Restored occurrences:', count)
try: compile(s, str(p), 'exec'); print('Syntax OK')
except SyntaxError as e:
    print(e.lineno, ascii(e.text), e.msg)
