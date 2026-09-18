const navigationIcons={dashboard:'\uf0e4',agents:'\uf0b1',games:'\uf11b',ads:'\uf016',members:'\uf2bd',withdrawals:'\uf0d6',subsidies:'\uf0d6','coin-logs':'\uf0d6','risk-whitelist':'\uf069','risk-history':'\uf069','risk-devices':'\uf069',profile:'\uf007',book:'\uf02d'};
const visitedPages=['members'];
function shellIcon(key){return `<span class="shell-icon" aria-hidden="true">${navigationIcons[key]||'\uf013'}</span>`;}
function updateShell(){
 const baseKey=({general:'profile',profit:'coin-logs'})[state.view]||state.view;
 const key=baseKey+(state.agentScope?'?agent_id='+state.agentScope:'');
 if(!visitedPages.includes(key))visitedPages.push(key);
 document.querySelector('.target-tabs').innerHTML=visitedPages.map(k=>{const base=k.split('?')[0],scope=new URLSearchParams(k.split('?')[1]||'').get('agent_id');return `<a href="#${k}" class="${k===key?'active':''}" ${k===key?'aria-current="page"':''}>${shellIcon(base)}${esc(views[base]?.[0]||base)}${scope?' · 主体 '+esc(scope):''}</a>`;}).join('');
 document.querySelectorAll('#nav .nav-item').forEach(a=>{
  a.querySelector('.nav-icon').innerHTML=shellIcon(a.hash.slice(1));
  if(a.classList.contains('active'))a.setAttribute('aria-current','page');
 });
 document.querySelectorAll('#nav .nav-group-title').forEach((button,i)=>{
  button.insertAdjacentHTML('afterbegin',shellIcon(['coin-logs','risk-history','settings'][i]));
 });
}
document.querySelector('.target-header-link').addEventListener('click',async event=>{
 const button=event.currentTarget;
 button.disabled=true;
 try{
  if('caches' in window)for(const key of await caches.keys())await caches.delete(key);
  await load();
 }finally{button.disabled=false;}
});
const sidebarToggle=document.createElement('button');
sidebarToggle.className='shell-sidebar-toggle';
sidebarToggle.type='button';
sidebarToggle.setAttribute('aria-label','收起或展开导航');
sidebarToggle.setAttribute('aria-expanded','true');
sidebarToggle.innerHTML='<span class="shell-icon">\uf0c9</span>';
document.querySelector('.target-tabs').before(sidebarToggle);
sidebarToggle.onclick=()=>{
 if(matchMedia('(max-width:640px)').matches){
  document.querySelector('.sidebar').classList.toggle('open');
  document.querySelector('#sidebarOverlay').classList.toggle('open');
 }else{
  const collapsed=document.body.classList.toggle('shell-collapsed');
  sidebarToggle.setAttribute('aria-expanded',String(!collapsed));
 }
};
document.addEventListener('DOMContentLoaded',()=>{
 const token=state.token,generation=profileIdentityGeneration;if(!token)return;
 api('/auth/me',{},'/api').then(user=>{
  if(state.token===token&&profileIdentityGeneration===generation)updateProfileIdentity(user);
 }).catch(()=>{});
});
