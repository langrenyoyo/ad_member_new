// Adds data actions to the global game-management table.
const genericGameObserver=new MutationObserver(()=>{
 if(typeof state==='undefined'||state.view!=='games'||typeof openGameUserData!=='function')return;
 const table=document.querySelector('#content table');if(!table||table.dataset.dataActions)return;
 const head=table.tHead?.rows[0];if(!head)return;table.dataset.dataActions='true';const h=document.createElement('th');h.textContent='数据查看';head.append(h);
 [...table.tBodies[0].rows].forEach(row=>{const id=Number(row.querySelector('[data-select]')?.dataset.select);if(!Number.isInteger(id)||id<=0)return;const cell=row.insertCell();const u=document.createElement('button');u.className='game-user-open';u.dataset.gameUser=String(id);u.textContent='用户数据';u.onclick=()=>openGameUserData(id);const p=document.createElement('button');p.className='game-profit-open';p.textContent='收益数据';p.onclick=()=>openGameProfitData(id);cell.append(u,p);});
});
document.addEventListener('DOMContentLoaded',()=>genericGameObserver.observe(document.querySelector('#content'),{childList:true,subtree:true}));

// This script is loaded before app.js in the single-line shell, so inject the
// editor before the page registers its generic create/edit handlers.
document.write('<link rel="stylesheet" href="/game-form.css"><script src="/game-form.js"><\/script>');



