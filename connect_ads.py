from pathlib import Path
p=Path('public/app.js');data=p.read_bytes();old=b"if(state.view==='dashboard'){await renderDashboard();return}";assert data.count(old)==1;data=data.replace(old,old+b"if(state.view==='ads'){await renderAds();return}");p.write_bytes(data)
p=Path('public/index.html');data=p.read_bytes();data=data.replace(b'</head>',b'<link rel="stylesheet" href="/ads.css"></head>');data=data.replace(b'<script src="/app.js">',b'<script src="/ads.js"></script><script src="/app.js">');p.write_bytes(data)
