// Adds data actions to the global game-management table.
const genericGameObserver=new MutationObserver(()=>{
 if(typeof state==='undefined'||state.view!=='games'||typeof openGameUserData!=='function')return;
 const table=document.querySelector('#content table');if(!table||table.dataset.dataActions)return;
 const head=table.tHead?.rows[0];if(!head)return;table.dataset.dataActions='true';const h=document.createElement('th');h.textContent='鏁版嵁鏌ョ湅';head.append(h);
 [...table.tBodies[0].rows].forEach(row=>{const id=[...row.cells].map(cell=>Number(cell.textContent.trim())).find(n=>Number.isInteger(n)&&n>0);if(!Number.isInteger(id))return;const cell=row.insertCell();const u=document.createElement('button');u.className='game-user-open';u.dataset.gameUser=String(id);u.textContent='鐢ㄦ埛鏁版嵁';u.onclick=()=>openGameUserData(id);const p=document.createElement('button');p.className='game-profit-open';p.textContent='鏀剁泭鏁版嵁';p.onclick=()=>openGameProfitData(id);cell.append(u,p);});
});
document.addEventListener('DOMContentLoaded',()=>genericGameObserver.observe(document.querySelector('#content'),{childList:true,subtree:true}));



