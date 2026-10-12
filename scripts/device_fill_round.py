"""Continue a device fill round, checking each advancement and final result."""
import re
import time
from device_ui import adb, nodes


def tap(node):
    x1,y1,x2,y2 = map(int,re.findall(r'\d+',node.get('bounds')))
    adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2))


for _ in range(12):
    current = nodes()
    text = [n.get('text','') for n in current]
    title = next((t for t in text if re.fullmatch(r'第 \d+ / 10 题',t)),None)
    if title is None:
        print('\n'.join(t for t in text if t),flush=True)
        break
    if not any(t in text for t in ('回答正确','再想一想')):
        tap(next(n for n in current if n.get('text')=='A'))
        current = nodes()
        assert any(n.get('text') in ('回答正确','再想一想') for n in current)
    next_button = next((n for n in current if n.get('text') in ('下一题','查看结果') and n.get('bounds')!='[0,0][0,0]'),None)
    assert next_button is not None, [n.get('text') for n in current]
    tap(next_button)
    time.sleep(.3)
    assert title not in [n.get('text') for n in nodes()], 'Question did not advance'
    print(title+' completed',flush=True)
else:
    raise AssertionError('Round did not finish')
