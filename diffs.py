from PIL import Image,ImageChops,ImageStat
from pathlib import Path
for i in range(1,10):
 a=Path(f'visual-baseline/reference/page-{i}.png'); b=Path(f'visual-baseline/local/page-{i}.png')
 if a.exists() and b.exists():
  x=Image.open(a).convert('RGB'); y=Image.open(b).convert('RGB').resize(x.size); print(i,x.size,ImageStat.Stat(ImageChops.difference(x,y)).mean)
