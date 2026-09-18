from pathlib import Path
p=Path('public/app.js');data=p.read_bytes()
start=data.index(b"if(state.view==='profile'||state.view==='general'){")
end=data.index(b"if(state.view==='dashboard')",start)
data=data[:start]+b"if(state.view==='profile'||state.view==='general'){await renderProfile();return}\n"+data[end:]
old=b"document.body.classList.toggle('member-view',state.view==='members');"
assert data.count(old)==1
data=data.replace(old,old+b"document.body.classList.toggle('profile-view',['profile','general'].includes(state.view));")
p.write_bytes(data)
p=Path('public/index.html');data=p.read_bytes()
data=data.replace(b'</head>',b'<link rel="stylesheet" href="/profile.css"></head>')
data=data.replace(b'<script src="/app.js">',b'<script src="/profile.js"></script><script src="/app.js">')
p.write_bytes(data)
