from pathlib import Path
p=Path('public/app.js'); data=p.read_bytes()
old=b'async function load(){const v='
new=b"async function load(){const bar=document.querySelector('.topbar');document.querySelector('.main').prepend(bar);document.body.classList.toggle('member-view',state.view==='members');const v="
assert data.count(old)==1
data=data.replace(old,new)
old=b'</div></section>`}'
new=b"</div></section>`;if(state.view==='members'){const tableArea=document.querySelector('#content .table-wrap,#content .empty');tableArea.before(bar)}}"
assert data.count(old)==1
data=data.replace(old,new)
p.write_bytes(data)
