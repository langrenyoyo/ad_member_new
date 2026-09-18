from pathlib import Path
p=Path('public/app.js');data=p.read_bytes();old=b"$('#nav').innerHTML=nav();";assert data.count(old)==1;data=data.replace(old,old+b'updateShell();');p.write_bytes(data)
p=Path('public/index.html');data=p.read_bytes();data=data.replace(b'</head>',b'<link rel="stylesheet" href="/shell.css"></head>');data=data.replace(b'<script src="/app.js"></script>',b'<script src="/shell.js"></script><script src="/app.js"></script>');p.write_bytes(data)
