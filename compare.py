from PIL import Image,ImageChops,ImageStat
from pathlib import Path
for p in [Path('visual-baseline/reference/dashboard.png'),Path('visual-baseline/local/dashboard.png'),Path('login-reference.png'),Path('visual-baseline/local/login.png')]:
 im=Image.open(p); print(p,im.size)
ref=Image.open('visual-baseline/reference/dashboard.png').convert('RGB'); loc=Image.open('visual-baseline/local/dashboard.png').convert('RGB').resize(ref.size)
d=ImageChops.difference(ref,loc); print('mean diff',ImageStat.Stat(d).mean)
d.save('visual-baseline/dashboard-diff.png')
