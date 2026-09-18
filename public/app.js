const views={'agent-analysis':['数据分析','/dashboard/summary'],dashboard:['\u4eea\u8868\u76d8','/dashboard/summary'],agents:['\u4e3b\u4f53\u7ba1\u7406','/agents'],games:['\u6e38\u620f\u7ba1\u7406','/games'],ads:['\u5e7f\u544a\u5217\u8868','/ads'],members:['\u4f1a\u5458\u7ba1\u7406','/members'],withdrawals:['\u7528\u6237\u63d0\u73b0','/withdrawals'],subsidies:['\u8865\u8d34\u7533\u8bf7','/subsidies'],'coin-logs':['\u91d1\u5e01\u6d41\u6c34','/coin-logs'],profit:['\u6536\u76ca\u7ba1\u7406','/coin-logs'],'risk-whitelist':['\u767d\u540d\u5355','/risk/whitelist'],'risk-history':['\u98ce\u63a7\u5386\u53f2','/risk/history'],'risk-devices':['\u8bbe\u5907\u98ce\u63a7','/risk/devices'],profile:['\u4e2a\u4eba\u8d44\u6599','/auth/me'],general:['\u5e38\u89c4\u7ba1\u7406','/auth/me'],book:['\u517b\u673a\u6559\u7a0b','/book']};

const state={view:location.hash.slice(1).split('?')[0]||'members',token:localStorage.getItem('admin_access_token')||sessionStorage.getItem('admin_access_token')||'',page:1,q:'',status:'',memberFilters:{},memberPermissions:{} };const $=s=>document.querySelector(s),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

let pageLoadGeneration=0;
async function load(){
 const generation=++pageLoadGeneration,route=location.hash,content=document.querySelector('#content');
 if(state.view!=='members')document.querySelectorAll('[data-member-toolbar]').forEach(element=>element.remove());
 document.querySelector('#pageLoadError')?.remove();
 content.setAttribute('aria-busy','true');
 try{await loadPage(generation);}
 catch(error){
  if(generation!==pageLoadGeneration||route!==location.hash)return;
  const box=document.createElement('div');box.id='pageLoadError';box.className='error-state';box.setAttribute('role','alert');
  const message=document.createElement('span');message.textContent=error.message||'加载失败';
  const retry=document.createElement('button');retry.type='button';retry.textContent='重试';retry.onclick=load;
  box.append(message,retry);
  const filters=state.view==='members'?content.querySelector('.member-filters'):null;
  if(filters)filters.after(box);else content.replaceChildren(box);
 }finally{if(generation===pageLoadGeneration)content.removeAttribute('aria-busy');}
}
function syncAgentRouteScope(){
 const params=new URLSearchParams(location.hash.split('?')[1]||'');
 const raw=params.get('agent_id');
 const scoped=['members','withdrawals'].includes(state.view)&&raw!==null;
 if(scoped&&(!/^[1-9]\d*$/.test(raw)||!Number.isSafeInteger(Number(raw))))throw Error('主体范围无效');
 const id=scoped?Number(raw):null;
 state.agentScope=id;
 if(state.view==='members'&&state.memberScope!==id){state.memberScope=id;state.page=1;state.q='';state.status='';state.memberFilters={};}
 if(state.view==='withdrawals'&&reviewStates.withdrawals.agentScope!==id){reviewStates.withdrawals={status:'',page:1,agentScope:id};}
}
function lockAgentScopeFilter(form){
 if(!state.agentScope||!form)return;
 const input=form.querySelector('[data-mf="agent_id"],[name="agent_id"]');
 if(input){input.value=String(state.agentScope);input.disabled=true;input.title='当前主体';}
}
async function api(path,opt={},prefix='/api/v1'){const h={'Content-Type':'application/json',...(opt.headers||{})};if(state.token)h.Authorization='Bearer '+state.token;const r=await fetch(prefix+path,{...opt,headers:h}),d=await r.json().catch(()=>({}));if(path.startsWith('/members?')&&d.permissions)state.memberPermissions=d.permissions;if(!r.ok)throw Error(d.detail||('HTTP '+r.status));return d}

function nav(){

 const groups=[['', ['dashboard','agents','games','ads','members','withdrawals','subsidies']],['\u6536\u76ca\u7ba1\u7406',['coin-logs']],['\u98ce\u63a7\u7ba1\u7406',['risk-whitelist','risk-history','risk-devices']],['\u5e38\u89c4\u7ba1\u7406',['profile']]];

 const current=({profit:'coin-logs',general:'profile'})[state.view]||state.view;

 const item=k=>`<a class="nav-item ${current===k?'active':''}" href="#${k}"><span class="nav-icon" aria-hidden="true">&#8250;</span>${views[k][0]}</a>`;

 return groups.map(([label,keys],i)=>{

  if(!label)return keys.map(item).join('');

  const expanded=keys.includes(current);

  return `<div class="nav-group ${expanded?'':'collapsed'}"><button type="button" class="nav-group-title" aria-expanded="${expanded}" aria-controls="nav-subitems-${i}">${label}<span aria-hidden="true">&#8249;</span></button><div class="nav-subitems" id="nav-subitems-${i}">${keys.map(item).join('')}</div></div>`;

 }).join('')+item('book');

}

function table(items){if(!items?.length)return '<div class="empty">\u6682\u65e0\u6570\u636e</div>';const labels={ip:'\u6ce8\u518cIP',real_name:'\u771f\u5b9e\u59d3\u540d',username:'\u7528\u6237\u8d26\u53f7',name:(state.view==='agents'?'\u4e3b\u4f53\u540d\u79f0':state.view==='games'?'\u6e38\u620f\u540d\u79f0':'\u4f1a\u5458\u540d\u79f0'),user_name:'\u4e3b\u4f53\u8d26\u53f7',parent_name:'\u4e0a\u7ea7',agent_id:'\u4e3b\u4f53ID',game_id:'\u6e38\u620fID',coin:'\u91d1\u5e01',freeze_coin:'\u51bb\u7ed3\u91d1\u5e01',parent_name:'\u4e0a\u7ea7\u6635\u79f0',game_name:'\u6e38\u620f\u540d\u79f0',coin_user:'\u7d2f\u8ba1\u91d1\u5e01\u6536\u76ca',coin_user_month:'\u672c\u6708\u91d1\u5e01\u6536\u76ca',coin_user_day:'\u4eca\u65e5\u91d1\u5e01\u6536\u76ca',available_coin:'\u53ef\u7528\u91d1\u5e01',vip:'VIP\u7b49\u7ea7',status:'\u72b6\u6001',is_white:'\u767d\u540d\u5355',device_id:'\u8bbe\u5907ID',last_login_ip:'\u767b\u5f55IP',last_login_time:'\u6700\u540e\u767b\u5f55',create_time:'\u521b\u5efa\u65f6\u95f4',update_time:'\u66f4\u65b0\u65f6\u95f4',amount:'\u91d1\u989d',type:'\u7c7b\u578b',remark:'\u5907\u6ce8',user_id:'\u7528\u6237ID',receive_name:'\u6536\u6b3e\u4eba',receive_tel:'\u6536\u6b3e\u7535\u8bdd',receive_address:'\u6536\u6b3e\u5730\u5740',exchange_value:'\u63d0\u73b0\u91d1\u989d',exchange_type:'\u63d0\u73b0\u65b9\u5f0f',reason:'\u9a73\u56de\u539f\u56e0',tx_price:'\u7533\u8bf7\u91d1\u989d',price:'\u8865\u8d34\u91d1\u989d',sub_msg:'\u5907\u6ce8',created_at:'\u521b\u5efa\u65f6\u95f4'};const preferred={members:['username','parent_name','game_name','vip','receive_name','coin_user','coin_user_month','coin_user_day','coin','freeze_coin','is_white','status','ip','created_at'],agents:['user_name','name','parent_name','status','game_ad_status','ht_status'],games:['name','agent_id','status','game_type','player_num','create_time'],withdrawals:['user_id','agent_id','game_id','receive_name','receive_tel','exchange_value','exchange_type','status','created_at','reason'],subsidies:['user_id','agent_id','game_id','tx_price','price','status','created_at','sub_msg'],'coin-logs':['username','coin','type','remark','create_time']}[state.view];if(state.view==='members')Object.assign(labels,{username:'账号',vip:'VIP',receive_name:'支付宝姓名',coin:'可用金币'});if(state.view==='members')Object.assign(labels,Object.fromEntries(memberColumnSchema.map(c=>[c[0],c[1]])));const keys=state.view==='members'?memberColumnSchema.map(c=>c[0]).filter(k=>!['id','operate'].includes(k)):preferred?(state.view==='members'?preferred:preferred.filter(k=>k in items[0])):Object.keys(items[0]).filter(k=>!['id','created_at','updated_at','password','salt'].includes(k)).slice(0,10);const val=(x,k)=>k==='status'?(['withdrawals','subsidies'].includes(state.view)?(String(x[k])==='0'?'\u5f85\u5ba1\u6838':String(x[k])==='1'?'\u5df2\u901a\u8fc7':String(x[k])==='2'?'\u5df2\u9a73\u56de':x[k]):(String(x[k])==='1'?'\u542f\u7528':String(x[k])==='0'?'\u7981\u7528':x[k])):x[k];return `<div class="table-wrap"><table class="table"><thead><tr><th><input type="checkbox" aria-label="select"></th><th data-field="id">${state.view==='members'?'Id':'ID'}</th>${keys.map(k=>`<th data-field="${k}">${labels[k]||k}</th>`).join('')}<th data-field="operate">\u64cd\u4f5c</th></tr></thead><tbody>${items.map(x=>`<tr><td><input type="checkbox" data-select="${x.id}" aria-label="select"></td><td data-field="id">${x.id??'-'}</td>${keys.map(k=>`<td data-field="${k}">${memberCell(x,k,val(x,k))}</td>`).join('')}<td data-field="operate">${state.view==='members'?`<button class="game-member-behavior" data-member-behavior="single" data-member-id="${esc(x.id)}" data-game-id="${esc(x.game_id)}">单APP行为</button>`:''}<button class="button ghost" data-detail="${x.id}">\u67e5\u770b</button>${['agents','games','members'].includes(state.view)?` <button class="button ghost" data-edit="${x.id}">\u7f16\u8f91</button> <button class="button danger" data-delete="${x.id}">\u5220\u9664</button> <button class="button ghost" data-toggle="${x.id}" data-next-status="${String(x.status)==='1'?'0':'1'}">${String(x.status)==='1'?'\u7981\u7528':'\u542f\u7528'}</button>${state.view==='members'?` <button class="button ghost" data-white="${x.id}" data-next-white="${String(x.is_white)==='1'?'0':'1'}">${String(x.is_white)==='1'?'\u53d6\u6d88\u767d\u540d\u5355':'\u52a0\u5165\u767d\u540d\u5355'}</button> <button class="button ghost" data-coin="${x.id}">\u4fee\u6539\u91d1\u5e01</button>`:''}`:''}${((state.view==='withdrawals'||state.view==='subsidies')&&['0','pending'].includes(String(x.status).toLowerCase()))?` <button class="button success" data-approve="${x.id}">\u901a\u8fc7</button> <button class="button danger" data-reject="${x.id}">\u9a73\u56de</button>`:''}</td></tr>`).join('')}</tbody></table></div>`}

async function loadPage(generation){syncAgentRouteScope();const routeAtStart=location.hash;const bar=document.querySelector('.topbar');document.querySelector('.main').prepend(bar);document.body.classList.toggle('member-view',state.view==='members');document.body.classList.toggle('dashboard-view',state.view==='dashboard');document.body.classList.toggle('withdrawals-view',state.view==='withdrawals');document.body.classList.toggle('subsidies-view',state.view==='subsidies');document.body.classList.toggle('book-view',state.view==='book');document.body.classList.toggle('risk-history-view',state.view==='risk-history');document.body.classList.toggle('risk-devices-view',state.view==='risk-devices');document.body.classList.toggle('whitelist-view',state.view==='risk-whitelist');document.body.classList.toggle('coin-view',['coin-logs','profit'].includes(state.view));document.body.classList.toggle('profile-view',['profile','general'].includes(state.view));const v=views[state.view]||views.dashboard;document.body.classList.toggle('target-ad-mode',state.view==='ads');$('#nav').innerHTML=nav();updateShell();$('#pageTitle').textContent=v[0];$('#pageEyebrow').textContent='\u7ba1\u7406\u7cfb\u7edf / '+v[0];if(state.view==='book'){await renderBook();return}if(state.view==='profile'||state.view==='general'){await renderProfile();return}
if(state.view==='agent-dashboard'){await renderAgentDashboard();return}if(state.view==='agent-analysis'){await renderAgentAnalysis();return}if(state.view==='agent-games'){await renderAgentGames();return}if(state.view==='agents'){await renderAgents();return}if(state.view==='dashboard'){await renderDashboard();return}if(state.view==='ads'){await renderAds();return}if(state.view==='withdrawals'){await renderWithdrawals();return}if(state.view==='subsidies'){await renderSubsidies();return}if(state.view==='risk-history'){await renderRiskHistory();return}if(state.view==='risk-devices'){await renderRiskDevices();return}if(state.view==='risk-whitelist'){await renderWhitelist();return}if(['coin-logs','profit'].includes(state.view)){await renderCoinLogs();return}

const pageSize=state.view==='members'?(state.memberPageSize||10):20;const p=new URLSearchParams({limit:pageSize==='All'?200:pageSize,offset:pageSize==='All'?0:(state.page-1)*pageSize});if(state.q)p.set('q',state.q);if(state.status)p.set('status',state.status);if(state.view==='members'&&state.memberFilters){for(const [k,val] of Object.entries(state.memberFilters)){if(val&&['id','username','name','parent_id','vip','status','game_id','game_name','agent_id','agent_name','ip','create_time'].includes(k))p.set(k,val)}}if(state.view==='members'){p.set('sort',state.memberSort||'id');p.set('order',state.memberOrder||'desc');if(state.agentScope)p.set('agent_id',String(state.agentScope));}const d=await api(v[1]+'?'+p);if(state.view==='members'&&pageSize==='All'){while(d.items.length<d.total){if(location.hash!==routeAtStart||generation!==pageLoadGeneration)return;p.set('offset',String(d.items.length));const more=await api(v[1]+'?'+p);if(!more.items.length){d.total=d.items.length;break;}d.items.push(...more.items);d.total=more.total;}}if(location.hash!==routeAtStart||generation!==pageLoadGeneration)return;const lastPage=Math.max(1,Math.ceil(d.total/(pageSize==='All'?Math.max(1,d.total):pageSize)));if(state.page>lastPage){state.page=lastPage;return load();}$('#content').innerHTML=`<section class="panel">${state.view==='ads'?`<div class="ad-summary">${Object.entries(d.summary||{}).map(([k,v])=>`<span class="ad-metric"><b>${esc(v)}</b> ${esc(k)}</span>`).join('')}</div><div class="target-ad-toolbar"><button class="button ghost" id="refresh">ˢ</button><button class="button ghost" id="exportAds"></button></div>`:''}${state.view==='members'?memberFilterMarkup():''}<div class="panel-head"><h2>${v[0]}</h2><input id="listSearch" placeholder="\u641c\u7d22" value="${esc(state.q)}"><select id="statusFilter"><option value="">\u5168\u90e8\u72b6\u6001</option>${['withdrawals','subsidies'].includes(state.view)?`<option value="0" ${state.status==='0'?'selected':''}>\u5f85\u5ba1\u6838</option><option value="1" ${state.status==='1'?'selected':''}>\u5df2\u901a\u8fc7</option><option value="2" ${state.status==='2'?'selected':''}>\u5df2\u9a73\u56de</option>`:`<option value="1" ${state.status==='1'?'selected':''}>\u542f\u7528</option><option value="0" ${state.status==='0'?'selected':''}>\u7981\u7528</option>`}</select></div>${table(d.items||[])}${state.view==='members'?memberPaginationMarkup(d.total,pageSize):`<div class="pagination"><button class="button ghost" id="prevPage" ${state.page<=1?'disabled':''}>\u4e0a\u4e00\u9875</button><span>\u7b2c ${state.page} \u9875</span><button class="button ghost" id="nextPage" ${state.page*20>=d.total?'disabled':''}>\u4e0b\u4e00\u9875</button></div>`}</section>`;if(state.view==='members'){attachMemberPagination(d.total,pageSize);attachMemberSorting();attachMemberToolbar();attachMemberExport(d.items||[],p);lockAgentScopeFilter(document.querySelector('.member-filters'));const tableArea=document.querySelector('#content .table-wrap,#content .empty');tableArea.before(bar)}}

$('#nav').addEventListener('click',e=>{const a=e.target.closest('a');if(!a)return;e.preventDefault();location.hash=a.hash;state.view=a.hash.slice(1).split('?')[0];state.page=1;load().catch(x=>$('#content').innerHTML='<div class="error-state">'+esc(x.message)+'</div>')});window.addEventListener('hashchange',()=>{state.view=location.hash.slice(1).split('?')[0]||'members';state.page=1;load()});document.addEventListener('click',e=>{if(e.target.id==='prevPage'){state.page--;load()}if(e.target.id==='nextPage'){state.page++;load()}if(e.target.matches('[data-approve]')||e.target.matches('[data-reject]')){const id=e.target.dataset.approve||e.target.dataset.reject;const action=e.target.dataset.approve?'approve':'reject';const reason=action==='reject'?prompt('\u8bf7\u8f93\u5165\u9a73\u56de\u539f\u56e0',''):'';if(action==='reject'&&reason===null)return;api('/'+state.view+'/'+id+'/'+action,{method:'POST',body:JSON.stringify(action==='reject'?{reason}: {})}).then(()=>load()).catch(x=>alert(x.message));return}if(e.target.matches('[data-delete]')){if(!confirm('\u786e\u5b9a\u5220\u9664\u6b64\u8bb0\u5f55\u5417\uff1f'))return;api('/'+state.view+'/'+e.target.dataset.delete,{method:'DELETE'}).then(()=>load()).catch(x=>alert(x.message));return}if(e.target.matches('[data-coin]')){openMemberCoinDialog(e.target.dataset.coin);return}if(e.target.matches('[data-white]')){api('/members/'+e.target.dataset.white,{method:'PATCH',body:JSON.stringify({is_white:Number(e.target.dataset.nextWhite)})}).then(()=>load()).catch(x=>alert(x.message));return}if(e.target.matches('[data-toggle]')){api('/'+state.view+'/'+e.target.dataset.toggle,{method:'PATCH',body:JSON.stringify({status:Number(e.target.dataset.nextStatus)})}).then(()=>load()).catch(x=>alert(x.message));return}if(e.target.matches('[data-edit]')){api('/'+state.view+'/'+e.target.dataset.edit).then(d=>{const fields={agents:[['user_name','\u4e3b\u4f53\u8d26\u53f7'],['name','\u4e3b\u4f53\u540d\u79f0']],games:[['name','\u6e38\u620f\u540d\u79f0'],['agent_id','\u4e3b\u4f53ID'],['game_key','\u6e38\u620f\u6807\u8bc6']],members:[['username','\u7528\u6237\u8d26\u53f7'],['name','\u7528\u6237\u540d\u79f0'],['receive_name','\u652f\u4ed8\u5b9d\u59d3\u540d']]}[state.view];$('#modalTitle').textContent='\u7f16\u8f91'+views[state.view][0];$('#formFields').innerHTML=state.view==='members'?renderMemberEditor(d):'<div class="detail-grid">'+fields.map(([k,l])=>`<label class="detail-field"><span>${l}</span><input name="${k}" value="${esc(d[k])}"></label>`).join('')+'</div><div class="modal-actions"><button type="submit" class="button primary">\u4fdd\u5b58</button></div>';$('#editorForm').dataset.edit=state.view+'/'+d.id;$('#editorForm').dataset.create='';$('#modal').hidden=false}).catch(x=>alert(x.message));return}if(e.target.matches('[data-detail]'))api('/'+state.view+'/'+e.target.dataset.detail).then(d=>{$('#editorForm').dataset.create='';$('#editorForm').dataset.edit='';const labels={ip:'\u6ce8\u518cIP',real_name:'\u771f\u5b9e\u59d3\u540d',username:'\u7528\u6237\u8d26\u53f7',name:'\u540d\u79f0',status:'\u72b6\u6001',coin:'\u91d1\u5e01',freeze_coin:'\u51bb\u7ed3\u91d1\u5e01',create_time:'\u521b\u5efa\u65f6\u95f4',update_time:'\u66f4\u65b0\u65f6\u95f4',remark:'\u5907\u6ce8',amount:'\u91d1\u989d',device_id:'\u8bbe\u5907ID',last_login_ip:'\u767b\u5f55IP',last_login_time:'\u6700\u540e\u767b\u5f55'};const entries=Object.entries(d).filter(([k])=>!['password','salt'].includes(k));$('#modalTitle').textContent=(views[state.view]||['\u8be6\u60c5'])[0]+'\u8be6\u60c5';$('#formFields').innerHTML='<div class="detail-grid">'+entries.map(([k,v])=>`<label class="detail-field"><span>${labels[k]||k}</span><input readonly value="${esc(v)}"></label>`).join('')+'</div>';$('#modal').hidden=false}).catch(x=>alert(x.message))});document.addEventListener('click',e=>{if(e.target.id==='createButton'){const cfg={agents:[['user_name','\u4e3b\u4f53\u8d26\u53f7'],['name','\u4e3b\u4f53\u540d\u79f0'],['password','\u5bc6\u7801']],games:[['name','\u6e38\u620f\u540d\u79f0'],['agent_id','\u4e3b\u4f53ID'],['game_key','\u6e38\u620f\u6807\u8bc6']],members:[['username','\u7528\u6237\u8d26\u53f7'],['name','\u7528\u6237\u540d\u79f0'],['receive_name','\u652f\u4ed8\u5b9d\u59d3\u540d'],['password','\u5bc6\u7801'],['pay_password','\u652f\u4ed8\u5bc6\u7801']]};const fields=cfg[state.view];if(!fields){alert('\u5f53\u524d\u9875\u9762\u6682\u4e0d\u652f\u6301\u65b0\u5efa');return}$('#modalTitle').textContent='\u65b0\u5efa'+views[state.view][0];$('#formFields').innerHTML='<div class="detail-grid">'+fields.map(([k,l])=>`<label class="detail-field"><span>${l}</span><input name="${k}" ${['password','pay_password'].includes(k)?'type="password" autocomplete="new-password"':''} required></label>`).join('')+'</div><div class="modal-actions"><button type="submit" class="button primary">\u4fdd\u5b58</button></div>';$('#editorForm').dataset.edit='';$('#editorForm').dataset.path=views[state.view][1];$('#editorForm').dataset.create='1';$('#modal').hidden=false}});$('#editorForm').addEventListener('submit',e=>{e.preventDefault();if(!e.target.dataset.create&&!e.target.dataset.edit)return;let body=Object.fromEntries(new FormData(e.target));if(e.target.dataset.edit?.startsWith('members/')&&e.target.dataset.memberSnapshot){const initial=JSON.parse(e.target.dataset.memberSnapshot);body=Object.fromEntries(Object.entries(body).filter(([key,value])=>value!==initial[key]));if(!Object.keys(body).length){$('#modal').hidden=true;return;}}api(e.target.dataset.edit?'/'+e.target.dataset.edit:e.target.dataset.path,{method:e.target.dataset.edit?'PATCH':'POST',body:JSON.stringify(body)}).then(()=>{e.target.dataset.create='';e.target.dataset.edit='';$('#modal').hidden=true;load()}).catch(x=>alert(x.message))});document.addEventListener('click',e=>{if(e.target.id==='memberFilterSubmit'){const vals=[...document.querySelectorAll('[data-mf]')].map(x=>[x.dataset.mf,x.value.trim()]).filter(([,v])=>v);state.memberFilters=Object.fromEntries(vals);state.q='';state.status='';state.page=1;load()}if(e.target.id==='memberFilterReset'){document.querySelectorAll('[data-mf]').forEach(x=>x.value='');state.q='';state.status='';state.memberFilters={};state.page=1;load()}});document.addEventListener('change',e=>{if(e.target.id==='statusFilter'){state.status=e.target.value;state.page=1;load()}});document.addEventListener('input',e=>{if(e.target.id==='listSearch'||e.target.id==='search'){state.q=e.target.value;clearTimeout(window._t);window._t=setTimeout(load,250)}});$('#loginForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{const d=await api('/login',{method:'POST',body:JSON.stringify({username:f.get('username'),password:f.get('password')})},'/api/auth');state.token=d.access_token;const keep=f.get('keeplogin')==='on';(keep?localStorage:sessionStorage).setItem('admin_access_token',state.token);$('#loginScreen').hidden=true;$('.app-shell').hidden=false;$('#accountName').textContent=d.user.display_name||d.user.name||d.user.username;updateProfileIdentity(d.user);load()}catch(x){$('#loginError').textContent=x.message}});$('#logoutButton').onclick=()=>{localStorage.removeItem('admin_access_token');sessionStorage.removeItem('admin_access_token');location.reload()};$('#refresh')?.addEventListener('click',load);$('#closeModal')?.addEventListener('click',()=>$('#modal').hidden=true);$('#cancelModal')?.addEventListener('click',()=>$('#modal').hidden=true);if(state.token){$('#loginScreen').hidden=true;$('.app-shell').hidden=false;load()}



document.addEventListener('change',e=>{if(e.target.matches('table thead input[type=checkbox]')){const on=e.target.checked;document.querySelectorAll('table tbody input[type=checkbox]').forEach(x=>x.checked=on)}});

document.addEventListener('click',e=>{const t=e.target.closest('.nav-group-title');if(t){const g=t.parentElement;g.classList.toggle('collapsed');t.setAttribute('aria-expanded',String(!g.classList.contains('collapsed')));}});



document.querySelector('.target-menu-search')?.addEventListener('submit',e=>e.preventDefault());document.querySelector('.target-menu-search input')?.addEventListener('input',e=>{const q=e.target.value.trim().toLowerCase();document.querySelectorAll('#nav .nav-item').forEach(a=>{a.hidden=!!q&&!a.textContent.toLowerCase().includes(q)})});



(function(){const b=document.getElementById("mobileMenuButton"),o=document.getElementById("sidebarOverlay"),sb=document.querySelector(".sidebar");if(!b||!o||!sb)return;const close=()=>{sb.classList.remove("open");o.classList.remove("open")};b.addEventListener("click",()=>{sb.classList.add("open");o.classList.add("open")});o.addEventListener("click",close);sb.addEventListener("click",e=>{if(e.target.closest("a"))close()});})();






document.addEventListener('click',function(e){if(e.target.id!=='exportAds')return;var t=document.querySelector('.target-ad-table');if(!t)return;var csv=Array.from(t.querySelectorAll('tr')).map(function(r){return Array.from(r.querySelectorAll('th,td')).map(function(c){return '"'+String(c.innerText||'').replace(/"/g,'""')+'"';}).join(',');}).join('\n');var a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}));a.download='ads.csv';a.click();});




function renderMemberEditor(row){
 $('#modalTitle').textContent='编辑';
const fields=[
 ['image_url','头像'],['username','账号'],['password','密码'],['pay_password','支付密码'],['name','昵称'],['device_id','机器码id'],
 ['sex','性别',[[0,'未知'],[1,'男'],[2,'女']]],['real_name','真实姓名'],['card_no','身份证号码'],['address','联系地址'],
 ['is_true','内部号',[[0,'否'],[1,'是']]],['realname_enable','实名状态',[[0,'否'],[1,'是']]],['exchange_enable','兑换状态',[[0,'否'],[1,'是']]],
 ['game_addiction_enable','关键行为达标',[[0,'否'],[1,'是']]],['game_addiction_time','达标时间'],['is_white','白名单',[[0,'否'],[1,'是']]],
 ['status','状态',[[0,'禁用'],[1,'启用']]],['vip','vip',[[0,'0'],[1,'1'],[2,'2']]],['raffle_open','独立抽奖设置',[[1,'开启'],[0,'关闭']]],
 ['raffle_num','抽奖次数'],['star_countdown','开始倒计时'],['over_countdown','结束倒计时'],['raffle_num2','其它抽奖次数'],
 ['star_countdown2','其它开始倒计时'],['over_countdown2','其它结束倒计时'],['down_load','下载地址'],['ht_status','代理',[[0,'否'],[1,'是']]],
 ['percent_zhi','直推比例（%）'],['percent_jian','间推比例（%）'],['percent_dai','代理比例（%）'],['percent_dai_two','二级代理比例（%）']
];
const tabMap={raffle_open:'lottery',raffle_num:'lottery',star_countdown:'lottery',over_countdown:'lottery',raffle_num2:'lottery',star_countdown2:'lottery',over_countdown2:'lottery',down_load:'download',ht_status:'agent',percent_zhi:'agent',percent_jian:'agent',percent_dai:'agent',percent_dai_two:'agent'};
 fields.splice(fields.findIndex(([key])=>key==='raffle_open'),0,['otherlevel','其它信息']);
 const snapshot={};
 const lotteryLabels={raffle_open:'独立抽奖设置',raffle_num:'抽奖次数(穿上甲)',star_countdown:'倒计时(穿上甲)',raffle_num2:'抽奖次数(其它)',star_countdown2:'倒计时(其它)'};
 const html=fields.map(([key,label,options])=>{
  const value=row[key]==null?'':String(row[key]);snapshot[key]=value;
  if(key==='over_countdown'||key==='over_countdown2')return '';
  label=lotteryLabels[key]||label;
  if(key==='star_countdown'||key==='star_countdown2'){
   const endKey=key==='star_countdown'?'over_countdown':'over_countdown2';
   return `<div class="detail-field" data-member-tab="lottery" role="group" aria-labelledby="member-edit-${key}-label"><span id="member-edit-${key}-label">${label}:</span><div class="member-countdown-range"><div class="member-input-unit"><input id="member-edit-${key}" name="${key}" value="${esc(value)}" aria-label="${label}开始（分钟）"><span>分钟</span></div><span class="member-range-separator" aria-hidden="true">-</span><div class="member-input-unit"><input id="member-edit-${endKey}" name="${endKey}" value="${esc(row[endKey]??'')}" aria-label="${label}结束（分钟）"><span>分钟</span></div></div></div>`;
  }
  if(key==='raffle_num'||key==='raffle_num2')return `<div class="detail-field" data-member-tab="lottery"><label for="member-edit-${key}">${label}:</label><div class="member-input-unit"><input id="member-edit-${key}" name="${key}" value="${esc(value)}"><span>次</span></div></div>`;
  const radio=['is_true','realname_enable','raffle_open','exchange_enable','game_addiction_enable','is_white','status','ht_status'].includes(key);
  const control=(key==='password'||key==='pay_password')?`<input id="member-edit-${key}" name="${key}" type="password" value="" autocomplete="new-password" placeholder="不修改密码请留空">`:key==='image_url'?`<div class="member-image-control"><input id="member-edit-${key}" name="${key}" value="${esc(value)}"><input type="file" accept="image/*" data-member-image-file hidden><button type="button" class="button member-image-upload" data-member-image-choose>上传</button><button type="button" class="button member-image-select" data-member-image-select>选择</button><img data-member-image-preview src="${esc(value)}" alt="头像预览" ${value?'':'hidden'}></div>`:radio?`<div class="member-edit-radios">${options.map(([v,text])=>`<label><input type="radio" name="${key}" value="${v}" ${String(v)===value?'checked':''}>${text}</label>`).join('')}</div>`:options?`<select id="member-edit-${key}" name="${key}">${!options.some(([v])=>String(v)===value)?`<option value="${esc(value)}">${esc(value)}</option>`:''}${options.map(([v,text])=>`<option value="${v}" ${String(v)===value?'selected':''}>${text}</option>`).join('')}</select>`:`<input id="member-edit-${key}" name="${key}" value="${esc(value)}">`;
  return radio?`<div class="detail-field" data-member-tab="${tabMap[key]||'basic'}" role="group" aria-labelledby="member-edit-${key}-label"><span id="member-edit-${key}-label">${label}:</span>${key==='raffle_open'?`<div>${control}<p class="member-lottery-help">开启后以当前数据为准</p></div>`:control}</div>`:`<div class="detail-field" data-member-tab="${tabMap[key]||'basic'}"><label for="member-edit-${key}">${label}:</label>${control}</div>`;
 }).join('');
 $('#editorForm').dataset.memberSnapshot=JSON.stringify(snapshot);
 return '<div class="member-edit-fields"><nav class="member-edit-tabs" role="tablist"><button type="button" role="tab" aria-selected="true" aria-controls="member-edit-panel" class="active" data-member-tab-button="basic">\u57fa\u7840\u4fe1\u606f</button><button type="button" role="tab" aria-selected="false" aria-controls="member-edit-panel" data-member-tab-button="lottery">\u62bd\u5956\u8bbe\u7f6e</button><button type="button" role="tab" aria-selected="false" aria-controls="member-edit-panel" data-member-tab-button="download">\u4e0b\u8f7d\u8bbe\u7f6e</button><button type="button" role="tab" aria-selected="false" aria-controls="member-edit-panel" data-member-tab-button="agent">\u4ee3\u7406\u8bbe\u7f6e</button></nav><div id="member-edit-panel" role="tabpanel" class="detail-grid member-edit-rows">'+html+'</div></div><div class="member-edit-error" role="alert"></div><div class="modal-actions"><button type="submit" class="button primary">\u786e\u5b9a</button><button type="reset" class="button ghost">\u91cd\u7f6e</button></div>';
}
function attachMemberEditorWindow(onChange=()=>{}){
 const modal=$('#modal'),panel=modal.querySelector('.modal'),header=modal.querySelector('.modal-head');
 const minimize=document.createElement('button'),maximize=document.createElement('button');
 for(const [button,action,label] of [[minimize,'minimize','最小化'],[maximize,'maximize','最大化']]){
  button.type='button';button.className='member-editor-window-button';button.dataset.memberWindow=action;button.setAttribute('aria-label',label);header.insertBefore(button,$('#closeModal'));
 }
 let drag=null,shiftX=0,shiftY=0;
 const update=()=>{maximize.setAttribute('aria-label',modal.classList.contains('member-editor-expanded')||modal.classList.contains('member-editor-minimized')?'还原':'最大化');onChange();};
 minimize.onclick=()=>{modal.classList.add('member-editor-minimized');update();};
 maximize.onclick=()=>{if(modal.classList.contains('member-editor-minimized'))modal.classList.remove('member-editor-minimized');else modal.classList.toggle('member-editor-expanded');update();};
 header.addEventListener('pointerdown',event=>{
  if(!modal.querySelector('.member-edit-fields')||event.button!==0||event.target.closest('button')||modal.classList.contains('member-editor-expanded')||modal.classList.contains('member-editor-minimized'))return;
  const rect=panel.getBoundingClientRect();drag={id:event.pointerId,x:event.clientX,y:event.clientY,left:rect.left,top:rect.top,width:rect.width,height:rect.height,shiftX,shiftY};header.setPointerCapture(event.pointerId);event.preventDefault();
 });
 header.addEventListener('pointermove',event=>{
  if(!drag||drag.id!==event.pointerId)return;
  const left=Math.min(Math.max(0,drag.left+event.clientX-drag.x),Math.max(0,innerWidth-drag.width));
  const top=Math.min(Math.max(0,drag.top+event.clientY-drag.y),Math.max(0,innerHeight-drag.height));
  shiftX=drag.shiftX+left-drag.left;shiftY=drag.shiftY+top-drag.top;panel.style.transform=`translate(${shiftX}px,${shiftY}px)`;
 });
 const end=event=>{if(drag?.id!==event.pointerId)return;drag=null;if(header.hasPointerCapture(event.pointerId))header.releasePointerCapture(event.pointerId);};
 header.addEventListener('pointerup',end);header.addEventListener('pointercancel',end);header.addEventListener('lostpointercapture',()=>{drag=null;});
 return ()=>{if(drag&&header.hasPointerCapture(drag.id))header.releasePointerCapture(drag.id);drag=null;shiftX=shiftY=0;panel.style.removeProperty('transform');modal.classList.remove('member-editor-expanded','member-editor-minimized');update();};
}
let openGameMemberEditor;
function attachMemberEditorLifecycle(){
 const form=$('#editorForm'),modal=$('#modal');let session=null;
 const resetWindow=attachMemberEditorWindow(()=>{
  const s=session;if(!s?.host)return;
  const minimized=modal.classList.contains('member-editor-minimized');
  if(s.host.classList.contains('minimized')===minimized)return;
  s.host.close();s.host.classList.toggle('minimized',minimized);
  // A minimized editor must stay inside the active parent dialog's top layer.
  (minimized?s.parent:document.body).append(s.host);
  if(minimized)s.host.show();else s.host.showModal();
 });
 const invalidate=()=>{
  const previous=session;session=null;
  previous?.request.abort();previous?.parent?.removeEventListener('close',previous.close);
  resetWindow();cancelMemberImageUpload(form);window.jQuery(form.querySelector('[name=game_addiction_time]')).data('DateTimePicker')?.destroy();
  if(previous?.host){previous.anchor.replaceWith(modal);previous.host.close();previous.host.remove();}
 };
 const current=s=>session===s&&location.hash===s.route&&pageLoadGeneration===s.generation&&(!s.parent||(s.parent.isConnected&&s.parent.open));
 const displayed=s=>current(s)&&!modal.hidden&&form.dataset.edit===s.path&&s.fields?.isConnected;
 const begin=(id,context={})=>{
  modal.hidden=true;invalidate();
  const s={route:location.hash,generation:pageLoadGeneration,path:'members/'+id,busy:false,request:new AbortController(),...context};session=s;
  s.close=()=>{if(session===s){modal.hidden=true;invalidate();}};
  s.parent?.addEventListener('close',s.close);
  (async()=>{
   try{
    const row=await api('/'+s.path,{signal:s.request.signal});
     if(!current(s)||s.trigger&&!s.trigger.isConnected){s.close();return;}
    if(s.gameId!==undefined&&Number(row.game_id)!==Number(s.gameId))throw Error('会员不属于当前游戏');
    $('#formFields').innerHTML=renderMemberEditor(row);
    const dateInput=form.querySelector('[name=game_addiction_time]');
    dateInput.parentElement.classList.add('member-date-field');
    window.jQuery(dateInput).datetimepicker({format:'YYYY-MM-DD HH:mm:ss',locale:'zh-cn',useCurrent:true,showTodayButton:true,showClose:true,
     icons:{time:'fa fa-clock-o',date:'fa fa-calendar',up:'fa fa-chevron-up',down:'fa fa-chevron-down',previous:'fa fa-chevron-left',next:'fa fa-chevron-right',today:'fa fa-history',clear:'fa fa-trash',close:'fa fa-remove'}});
    $('#formFields [data-member-tab-button="basic"]')?.click();
    form.removeAttribute('aria-busy');form.dataset.edit=s.path;form.dataset.create='';
    s.fields=form.querySelector('.member-edit-fields');
    if(s.parent){
     s.anchor=document.createComment('member-editor');modal.before(s.anchor);
     s.host=document.createElement('dialog');s.host.className='game-member-editor-host';s.host.setAttribute('aria-label','编辑会员');
     document.body.append(s.host);s.host.append(modal);
     s.host.addEventListener('cancel',event=>{event.preventDefault();s.close();});
     s.host.addEventListener('close',()=>{if(!s.host.open)s.close();});
      modal.hidden=false;s.host.showModal();
    }
    modal.hidden=false;
    }catch(error){if(current(s)&&error.name!=='AbortError'){s.close();if(s.onError)s.onError(error);else alert(error.message);}}
  })();
  return {close:s.close};
 };
 openGameMemberEditor=(id,gameId,parent,onSaved,onError)=>begin(id,{gameId,parent,onSaved,onError});
 document.addEventListener('click',async event=>{
  const trigger=event.target.closest('button[data-edit],[data-detail],#createButton,#closeModal,#cancelModal');
  if(!trigger)return;
  invalidate();
  if(!trigger.matches('[data-edit]')||state.view!=='members')return;
  event.preventDefault();event.stopImmediatePropagation();
  begin(trigger.dataset.edit,{trigger});
 },true);
 window.addEventListener('hashchange',()=>{if(session){modal.hidden=true;invalidate();}});
 form.addEventListener('submit',async event=>{
  if(!form.dataset.edit?.startsWith('members/'))return;
  event.preventDefault();event.stopImmediatePropagation();
  const s=session;if(!s||!displayed(s)||s.busy||form.memberImageUpload)return;
  const initial=JSON.parse(form.dataset.memberSnapshot||'{}');
  const body=Object.fromEntries([...new FormData(form)].filter(([key,value])=>value!==initial[key]));
  for(const radio of form.querySelectorAll('input[type=radio]:checked')){
   if(Object.hasOwn(body,radio.name))body[radio.name]=Number(radio.value);
  }
  if(!Object.keys(body).length){modal.hidden=true;invalidate();return;}
  s.busy=true;const errorBox=form.querySelector('.member-edit-error');errorBox.textContent='';
  const controls=[...form.querySelectorAll('input,select,button')].filter(control=>!control.disabled);
  controls.forEach(control=>control.disabled=true);form.setAttribute('aria-busy','true');
  try{
   await api('/'+s.path,{method:'PATCH',body:JSON.stringify(body)});
   if(displayed(s)){form.dataset.edit='';modal.hidden=true;invalidate();if(s.onSaved)await s.onSaved();else await load();}
  }catch(error){if(displayed(s))errorBox.textContent=error.message;}
  finally{
   s.busy=false;
   // Restore only this form instance; a later editor may already occupy the modal.
   if(s.fields.isConnected){controls.forEach(control=>control.disabled=false);form.removeAttribute('aria-busy');}
  }
 },true);
}
attachMemberEditorLifecycle();
$('#editorForm').addEventListener('submit',async event=>{
 const form=event.currentTarget;
 if(form.dataset.create!=='1'||state.view!=='members')return;
 event.preventDefault();event.stopImmediatePropagation();
 const fields=form.querySelector('.detail-grid');if(!fields||fields.dataset.saving==='1')return;
 const route=location.hash,generation=pageLoadGeneration;
 const current=()=>fields.isConnected&&!$('#modal').hidden&&location.hash===route&&pageLoadGeneration===generation;
 const body=Object.fromEntries(new FormData(form));
 fields.dataset.saving='1';form.setAttribute('aria-busy','true');
 const controls=[...form.querySelectorAll('input,select,button')].filter(el=>!el.disabled);controls.forEach(el=>el.disabled=true);
 try{
  await api(form.dataset.path,{method:'POST',body:JSON.stringify(body)});
  if(current()){form.dataset.create='';$('#modal').hidden=true;await load();}
 }catch(error){if(current())alert(error.message);}
 finally{delete fields.dataset.saving;if(fields.isConnected){controls.forEach(el=>el.disabled=false);form.removeAttribute('aria-busy');}}
},true);
document.addEventListener('click',event=>{const button=event.target.closest('[data-member-tab-button]');if(!button)return;const root=button.closest('#modal');if(!root)return;const tab=button.dataset.memberTabButton;root.querySelectorAll('[data-member-tab-button]').forEach(item=>{const active=item===button;item.classList.toggle('active',active);item.setAttribute('aria-selected',String(active));});root.querySelectorAll('[data-member-tab]').forEach(item=>item.hidden=item.dataset.memberTab!==tab);});
document.addEventListener('keydown',event=>{const button=event.target.closest('[data-member-tab-button]');if(!button||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;const tabs=[...button.parentElement.querySelectorAll('[data-member-tab-button]')];const current=tabs.indexOf(button);const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:Math.max(0,Math.min(tabs.length-1,current+(event.key==='ArrowRight'?1:-1)));event.preventDefault();tabs[next].focus();tabs[next].click();});
document.addEventListener('click',event=>{const button=event.target.closest('[data-member-image-choose]');if(!button)return;button.closest('.member-image-control').querySelector('[data-member-image-file]').click();});
document.addEventListener('click',event=>{const button=event.target.closest('[data-member-image-select]');if(!button)return;const error=button.closest('form')?.querySelector('.member-edit-error');if(error)error.textContent='附件选择无权限';});
document.addEventListener('input',event=>{
 const input=event.target.closest('.member-image-control [name=image_url]');if(!input)return;
 cancelMemberImageUpload(input.closest('form'));
 const preview=input.closest('.member-image-control').querySelector('[data-member-image-preview]');
 preview.src=input.value;preview.hidden=!input.value;
});
function cancelMemberImageUpload(form){
 const pending=form.memberImageUpload;if(!pending)return;
 pending.controller.abort();form.memberImageUpload=null;
 if(!form.hasAttribute('aria-busy'))form.querySelector('[type=submit]')?.removeAttribute('disabled');
}
document.addEventListener('change',async event=>{
 const file=event.target.closest('[data-member-image-file]')?.files?.[0];if(!file)return;
 const box=event.target.closest('.member-image-control'),form=box.closest('form'),input=box.querySelector('[name=image_url]'),preview=box.querySelector('[data-member-image-preview]'),error=form.querySelector('.member-edit-error');
 cancelMemberImageUpload(form);
 if(!file.type.startsWith('image/')){error.textContent='请选择图片文件';return;}
 if(file.size>2*1024*1024){error.textContent='图片不能超过 2MB';event.target.value='';return;}
 const pending={controller:new AbortController(),box,route:location.hash};form.memberImageUpload=pending;
 const current=()=>form.memberImageUpload===pending&&box.isConnected&&!$('#modal').hidden&&location.hash===pending.route;
 error.textContent='';box.setAttribute('aria-busy','true');form.querySelector('[type=submit]').disabled=true;
 try{
  const result=await api('/member-images',{method:'POST',headers:{'Content-Type':file.type},body:file,signal:pending.controller.signal});
  if(!current())return;
  input.value=result.url;preview.src=result.url;preview.hidden=false;
 }catch(err){if(current()&&err.name!=='AbortError')error.textContent=err.message;}
 finally{box.removeAttribute('aria-busy');if(form.memberImageUpload===pending){form.memberImageUpload=null;if(!form.hasAttribute('aria-busy'))form.querySelector('[type=submit]').disabled=false;}event.target.value='';}
});
$('#editorForm').addEventListener('reset',event=>{
 const form=event.currentTarget;cancelMemberImageUpload(form);
 const dateInput=form.querySelector('[name=game_addiction_time]');
 requestAnimationFrame(()=>{if(event.defaultPrevented||!dateInput?.isConnected)return;const picker=window.jQuery(dateInput).data('DateTimePicker');if(picker){picker.date(dateInput.value||null);picker.hide();}});
 const input=form.querySelector('[name=image_url]'),preview=form.querySelector('[data-member-image-preview]');
 requestAnimationFrame(()=>{if(event.defaultPrevented||!input?.isConnected||!preview?.isConnected)return;preview.src=input.value;preview.hidden=!input.value;form.querySelector('.member-edit-error').textContent='';});
});
document.addEventListener('click',event=>{if(event.target.closest('[data-member-tab-button],[data-member-window]'))window.jQuery('#member-edit-game_addiction_time').data('DateTimePicker')?.hide();});
function openMemberCoinDialog(id){return openMemberValueDialog(id,'coins');}
function openMemberRebindDialog(id){return openMemberValueDialog(id,'rebind');}
document.addEventListener('click',event=>{const button=event.target.closest('[data-member-rebind]');if(button&&state.view==='members')openMemberRebindDialog(button.dataset.memberRebind);});
async function openMemberValueDialog(id,kind){
 document.querySelectorAll('#memberCoinDialog,#memberRebindDialog').forEach(d=>d.close());
 const rebind=kind==='rebind',keys=rebind?['parent_id','ht_id','ht_top_id']:['coin','freeze_coin'];
 const fields=rebind?[['id','当前ID'],['parent_id','上级ID'],['ht_id','归属ID'],['ht_top_id','源头ID']]:[['coin','可用金币'],['freeze_coin','冻结金币']];
 const route=location.hash,generation=pageLoadGeneration,dialog=document.createElement('dialog');dialog.id=rebind?'memberRebindDialog':'memberCoinDialog';dialog.className='member-coin-dialog';
 dialog.innerHTML=`<header><strong>${rebind?'改绑关系':'修改金币'}</strong><button type="button" data-close aria-label="关闭">×</button></header><form>${fields.map(([key,label])=>`<label><span>${label}:</span><input name="${key}" inputmode="${rebind?'numeric':'decimal'}" ${key==='id'?'disabled':'required'}></label>`).join('')}<div role="alert"></div><footer><button type="submit" class="button primary" disabled>确定</button><button type="reset" class="button ghost" disabled>重置</button></footer></form>`;
 document.body.append(dialog);dialog.showModal();
 const maximize=document.createElement('button');maximize.type='button';maximize.className='member-coin-maximize';maximize.setAttribute('aria-label','最大化');maximize.textContent='□';dialog.querySelector('header').insertBefore(maximize,dialog.querySelector('[data-close]'));
 const minimize=document.createElement('button');minimize.type='button';minimize.className='member-coin-minimize';minimize.setAttribute('aria-label','最小化');minimize.textContent='−';dialog.querySelector('header').insertBefore(minimize,maximize);
 const updateWindowButtons=()=>{const restore=dialog.classList.contains('expanded')||dialog.classList.contains('minimized');maximize.setAttribute('aria-label',restore?'还原':'最大化');maximize.textContent=restore?'▣':'□';};
 minimize.onclick=()=>{dialog.close();dialog.classList.add('minimized');dialog.show();updateWindowButtons();};
 maximize.onclick=()=>{if(dialog.classList.contains('minimized')){dialog.close();dialog.classList.remove('minimized');dialog.showModal();}else dialog.classList.toggle('expanded');updateWindowButtons();};
 const header=dialog.querySelector('header');let drag=null,shiftX=0,shiftY=0;
 header.onpointerdown=event=>{
  if(event.button!==0||event.target.closest('button')||dialog.classList.contains('expanded')||dialog.classList.contains('minimized'))return;
  const rect=dialog.getBoundingClientRect();drag={id:event.pointerId,x:event.clientX,y:event.clientY,left:rect.left,top:rect.top,width:rect.width,height:rect.height,shiftX,shiftY};
  header.setPointerCapture(event.pointerId);event.preventDefault();
 };
 header.onpointermove=event=>{
  if(!drag||drag.id!==event.pointerId)return;
  const left=Math.min(Math.max(0,drag.left+event.clientX-drag.x),Math.max(0,innerWidth-drag.width));
  const top=Math.min(Math.max(0,drag.top+event.clientY-drag.y),Math.max(0,innerHeight-drag.height));
  shiftX=drag.shiftX+left-drag.left;shiftY=drag.shiftY+top-drag.top;dialog.style.transform=`translate(${shiftX}px,${shiftY}px)`;
 };
 const endDrag=event=>{if(drag?.id===event.pointerId){drag=null;if(header.hasPointerCapture(event.pointerId))header.releasePointerCapture(event.pointerId);}};
 header.onpointerup=endDrag;header.onpointercancel=endDrag;header.onlostpointercapture=()=>{drag=null;};
 const form=dialog.querySelector('form'),errorBox=form.querySelector('[role=alert]'),submit=form.querySelector('[type=submit]'),reset=form.querySelector('[type=reset]');
 const close=()=>dialog.close();window.addEventListener('hashchange',close);dialog.querySelector('[data-close]').onclick=close;
 dialog.addEventListener('close',()=>{if(dialog.open)return;window.removeEventListener('hashchange',close);dialog.remove();});
 const current=()=>dialog.isConnected&&dialog.open&&location.hash===route&&generation===pageLoadGeneration;
 let busy=false;
 try{
  const row=await api('/members/'+encodeURIComponent(id));if(!current()){close();return;}
  for(const [key] of fields){const input=form.elements[key];input.value=String(row[key]??0);input.defaultValue=input.value;}
  submit.disabled=false;reset.disabled=false;
 }catch(error){if(current())errorBox.textContent=error.message;return;}
 form.onreset=()=>{errorBox.textContent='';};
 form.onsubmit=async event=>{
  event.preventDefault();if(busy)return;if(!current()){close();return;}
  const values=Object.fromEntries(keys.map(key=>[key,form.elements[key].value.trim()]));
  if(Object.values(values).some(value=>value===''||!Number.isFinite(Number(value))||(rebind&&!Number.isSafeInteger(Number(value))))){errorBox.textContent=rebind?'请输入有效的整数ID':'请输入有效的金币数值';return;}
  busy=true;submit.disabled=true;reset.disabled=true;errorBox.textContent='';
  try{await api('/members/'+encodeURIComponent(id),{method:'PATCH',body:JSON.stringify(Object.fromEntries(Object.entries(values).map(([key,value])=>[key,Number(value)])))});const refresh=current();close();if(refresh)await load();}
  catch(error){if(current())errorBox.textContent=error.message;}
  finally{busy=false;submit.disabled=false;reset.disabled=false;}
 };
}
function memberFilterMarkup(){
 const fields=[['id','Id'],['username','\u8d26\u53f7'],['parent_id','\u4e0a\u7ea7Id'],['game_name','\u6e38\u620f\u540d\u79f0'],['vip','VIP'],['agent_name','\u4ee3\u7406\u5546\u540d\u79f0'],['name','\u6635\u79f0'],['status','\u72b6\u6001'],['ip','\u6ce8\u518cIP'],['create_time','\u521b\u5efa\u65f6\u95f4']];
 return '<div class="member-filters">'+fields.map(([key,label])=>{
  const value=state.memberFilters[key]||'';
  const options=key==='vip'?Array.from({length:3},(_,i)=>[String(i),'V'+i]):key==='status'?[['1','\u542f\u7528'],['0','\u7981\u7528']]:null;
  const control=options?`<select data-mf="${key}"><option value="">\u9009\u62e9</option>${options.map(([v,l])=>`<option value="${v}" ${value===v?'selected':''}>${l}</option>`).join('')}</select>`:`<input data-mf="${key}" placeholder="${label}" value="${esc(value)}">`;
  return `<label><span>${label}</span>${control}</label>`;
 }).join('')+'<span class="filter-actions"><button type="button" class="button primary" id="memberFilterSubmit">\u63d0\u4ea4</button><button type="button" class="button ghost" id="memberFilterReset">\u91cd\u7f6e</button></span></div>';
}
function memberPaginationMarkup(total,size){
 const count=size==='All'?Math.max(1,total):size,pages=Math.max(1,Math.ceil(total/count));
 const first=total?(state.page-1)*count+1:0,last=Math.min(state.page*count,total);
 const choices=[10,15,20,25,50,'All'].filter((n,i,a)=>n===size||i===0||total>(a[i-1]==='All'?total:a[i-1]));
 const numbers=new Set([1,pages]);for(let i=Math.max(1,state.page-2);i<=Math.min(pages,state.page+2);i++)numbers.add(i);
 let previous=0;const links=[...numbers].sort((a,b)=>a-b).map(n=>{const gap=previous&&n>previous+1?'<li class="disabled"><span>…</span></li>':'';previous=n;return gap+`<li class="${n===state.page?'active':''}"><button type="button" data-member-page="${n}" ${n===state.page?'aria-current="page"':''}>${n}</button></li>`;}).join('');
 return `<div class="member-pagination" ${total===0?'hidden':''}><div class="member-pagination-detail"><span>显示第 ${first} 到第 ${last} 条记录，总共 ${total} 条记录</span> <label ${total<=10?'hidden':''}>每页显示 <select id="memberPageSize" aria-label="每页显示条数">${choices.map(n=>`<option value="${n}" ${String(n)===String(size)?'selected':''}>${n==='All'?'全部':n}</option>`).join('')}</select> 条记录</label></div><nav aria-label="会员分页" ${pages<=1?'hidden':''}><ul class="member-page-links"><li><button type="button" id="prevPage">上一页</button></li>${links}<li><button type="button" id="nextPage">下一页</button></li><li class="member-page-jump"><input type="text" inputmode="numeric" aria-label="跳转页码"><button type="button" id="memberPageJump">跳转</button></li></ul></nav></div>`;
}
function attachMemberPagination(total,size){
 const root=document.querySelector('.member-pagination');if(!root)return;
 const pages=Math.max(1,Math.ceil(total/(size==='All'?Math.max(1,total):size)));
 const jump=()=>{const input=root.querySelector('[aria-label="跳转页码"]');if(!/^\d+$/.test(input.value))return;const n=Number(input.value);if(Number.isSafeInteger(n)&&n>=1&&n<=pages&&n!==state.page){state.page=n;load();}};
 root.onclick=event=>{
  const button=event.target.closest('button');if(!button)return;event.stopPropagation();
  if(button.id==='memberPageJump'){jump();return;}
  const n=button.id==='prevPage'?(state.page===1?pages:state.page-1):button.id==='nextPage'?(state.page===pages?1:state.page+1):Number(button.dataset.memberPage);
  if(n>=1&&n<=pages&&n!==state.page){state.page=n;load();}
 };
 root.querySelector('[aria-label="跳转页码"]').onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();jump();}};
 root.querySelector('#memberPageSize').onchange=event=>{state.memberPageSize=event.target.value==='All'?'All':Number(event.target.value);state.page=1;load();};
}
const memberColumnSchema=[
 ['id','Id',true],['image_url','头像',false],['username','账号',true],
 ['parent_id','上级Id',false],['parent_username','上级账号',false],['parent_name','上级昵称',true],
 ['game_name','游戏名称',true],['vip','VIP',true],['agent_name','代理商名称',false],['name','昵称',false],
 ['receive_name','支付宝姓名',true],['coin_user','累计金币收益',true],['coin_user_month','本月金币收益',true],
 ['coin_user_day','今日金币收益',true],['coin','可用金币',true],['freeze_coin','冻结金币',true],
 ['game_addiction_enable','达标',false],['game_addiction_time','达标时间',false],['exchange_enable','兑换',false],
 ['is_white','白名单',true],['status','状态',true],['ip','注册IP',true],
 ['last_login_device_id','最后登陆设备号',false],['last_login_ip','最后登陆IP',false],
 ['last_login_time','最后登陆时间',false],['created_at','创建时间',true],['operate','操作',true]
];
function attachMemberColumns(toolbar,table){
 if(!state.memberVisibleColumns)state.memberVisibleColumns=memberColumnSchema.filter(c=>c[2]).map(c=>c[0]);
 const menu=document.createElement('details');menu.className='member-columns';menu.dataset.memberToolbar='';
 menu.innerHTML='<summary aria-label="显示列" title="显示列"><i class="fa fa-th-list" aria-hidden="true"></i><span aria-hidden="true"> ▾</span></summary><div class="member-columns-menu"></div>';
 const list=menu.querySelector('.member-columns-menu');
 for(const [key,label] of memberColumnSchema){
  const item=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.dataset.memberColumn=key;
  item.append(input,document.createTextNode(label));list.append(item);
 }
 const apply=()=>{
  const visible=new Set(state.memberVisibleColumns);
  table?.querySelectorAll('[data-field]').forEach(cell=>cell.hidden=!visible.has(cell.dataset.field));
  list.querySelectorAll('input').forEach(input=>{input.checked=visible.has(input.dataset.memberColumn);input.disabled=input.checked&&visible.size===1;});
 };
 list.onchange=event=>{
  const input=event.target;if(!input.matches('[data-member-column]'))return;
  const visible=new Set(state.memberVisibleColumns);
  if(input.checked)visible.add(input.dataset.memberColumn);else if(visible.size>1)visible.delete(input.dataset.memberColumn);
  state.memberVisibleColumns=[...visible];apply();
 };
 menu.addEventListener('keydown',event=>{if(event.key==='Escape'){menu.open=false;menu.querySelector('summary').focus();}});
 menu.addEventListener('focusout',event=>{if(!menu.contains(event.relatedTarget))menu.open=false;});
 toolbar.append(menu);apply();
}
function attachMemberView(toolbar,table){
 const button=document.createElement('button');button.type='button';button.id='memberViewToggle';button.dataset.memberToolbar='';button.className='button member-view-toggle';button.title='切换视图';button.setAttribute('aria-label','切换卡片视图');
 toolbar.insertBefore(button,toolbar.querySelector('.member-columns'));
 if(table){
  const labels=Object.fromEntries(memberColumnSchema.map(c=>[c[0],c[1]]));
  table.querySelectorAll('tbody td[data-field]').forEach(cell=>{
   const label=document.createElement('span'),value=document.createElement('span');label.className='member-card-label';label.textContent=labels[cell.dataset.field];
   value.className='member-card-value';value.append(...cell.childNodes);cell.append(label,value);
  });
 }
 const apply=()=>{table?.classList.toggle('member-card-table',!!state.memberCardView);button.setAttribute('aria-pressed',String(!!state.memberCardView));};
 button.onclick=()=>{state.memberCardView=!state.memberCardView;apply();};apply();
}
function attachMemberToolbar(){
 document.querySelectorAll('[data-member-toolbar]').forEach(element=>element.remove());
 const toolbar=document.querySelector('.topbar .toolbar'),table=document.querySelector('#content .table'),filters=document.querySelector('.member-filters');
 if(!toolbar||!filters)return;
 const memberPermissions={create:false,edit:true,delete:false,batch_status:false,rebind:true,behavior:true,coin:true,...(state.memberPermissions||{})};
 attachMemberLookups(filters);
 table?.querySelectorAll('tbody tr').forEach(row=>{
  const cell=row.querySelector('[data-field="operate"]'),behavior=cell?.querySelector('[data-member-behavior]');if(!cell)return;if(!behavior){cell.replaceChildren();return;}
  const id=behavior.dataset.memberId,gameId=behavior.dataset.gameId;
  cell.innerHTML=`<button type="button" class="button member-action-warning" data-member-rebind="${esc(id)}">改绑关系</button> <button type="button" class="button member-action-success" data-member-behavior="single" data-member-id="${esc(id)}" data-game-id="${esc(gameId)}">单APP行为</button> <button type="button" class="button member-action-warning" data-coin="${esc(id)}">修改金币</button> <button type="button" class="button member-action-success member-action-edit" data-edit="${esc(id)}" aria-label="编辑" title="编辑"></button>`;
 });
 if(memberPermissions.behavior===false)table?.querySelectorAll('[data-member-behavior]').forEach(button=>button.closest('[data-field="operate"]')?.replaceChildren());
 if(memberPermissions.edit===false)table?.querySelectorAll('[data-edit]').forEach(button=>button.remove());
 if(memberPermissions.rebind===false)table?.querySelectorAll('[data-member-rebind]').forEach(button=>button.remove());
 if(memberPermissions.coin===false)table?.querySelectorAll('[data-coin]').forEach(button=>button.remove());
 const edit=document.createElement('button');edit.type='button';edit.id='memberSelectionEdit';edit.dataset.memberToolbar='';edit.className='button member-selection-edit';edit.textContent='编辑';edit.disabled=true;
 edit.hidden=memberPermissions.edit===false;
 toolbar.insertBefore(edit,toolbar.querySelector('#createButton'));
 const more=document.createElement('details');more.dataset.memberToolbar='';more.className='member-batch-menu';
 // The reference account receives no batch-status capability on this page.
 more.hidden=memberPermissions.batch_status===false;
 more.innerHTML='<summary aria-disabled="true">更多 ▾</summary><div><button type="button" data-member-batch-status="1" disabled>启用</button><button type="button" data-member-batch-status="0" disabled>禁用</button></div>';
 toolbar.insertBefore(more,toolbar.querySelector('#createButton'));
 const createButton=toolbar.querySelector('#createButton');
 if(createButton)createButton.hidden=memberPermissions.create===false;
 let batchBusy=false;
 more.querySelector('summary').onclick=event=>{if(batchBusy||more.querySelector('summary').getAttribute('aria-disabled')==='true')event.preventDefault();};
 const syncBatch=()=>{const selected=table?[...table.querySelectorAll('[data-select]:checked')]:[];more.querySelector('summary').setAttribute('aria-disabled',String(batchBusy||!selected.length));more.querySelectorAll('button').forEach(b=>b.disabled=batchBusy||!selected.length);};
 table?.addEventListener('change',syncBatch);
 table?.addEventListener('click',()=>queueMicrotask(syncBatch));
 more.onclick=async event=>{
  const button=event.target.closest('[data-member-batch-status]');if(!button||batchBusy||!table?.isConnected)return;
  const ids=[...table.querySelectorAll('[data-select]:checked')].map(b=>Number(b.dataset.select));if(!ids.length)return;
  if(ids.length>200){alert('一次最多处理 200 条会员记录');return;}
  const route=location.hash,generation=pageLoadGeneration,scope=state.agentScope;
  batchBusy=true;syncBatch();more.open=false;
  try{await api('/members/batch-status'+(scope?'?agent_id='+encodeURIComponent(scope):''),{method:'POST',body:JSON.stringify({ids,status:Number(button.dataset.memberBatchStatus)})});
   if(table.isConnected&&location.hash===route&&generation===pageLoadGeneration)await load();
  }catch(error){if(table.isConnected&&location.hash===route&&generation===pageLoadGeneration)alert(error.message);}
  finally{batchBusy=false;if(table.isConnected)syncBatch();}
 };
 const search=document.createElement('button');search.type='button';search.id='memberSearchToggle';search.dataset.memberToolbar='';search.className='button member-search-toggle';search.setAttribute('aria-label','普通搜索');search.title='普通搜索';
 filters.id='memberFilters';search.setAttribute('aria-controls','memberFilters');toolbar.append(search);
 attachReviewDates(filters,'input[data-mf="create_time"]',{applyLabel:'应用',monthNames:Array.from({length:12},(_,i)=>(i+1)+'月')});
 const applyFilters=()=>{filters.hidden=!!state.memberFiltersCollapsed;search.setAttribute('aria-expanded',String(!filters.hidden));};
 search.onclick=()=>{state.memberFiltersCollapsed=!state.memberFiltersCollapsed;applyFilters();};applyFilters();
 attachMemberColumns(toolbar,table);
 attachMemberView(toolbar,table);toolbar.append(search);
 if(!table)return;
 if(memberPermissions.edit===false)table.querySelectorAll('[data-edit]').forEach(button=>button.remove());
 if(memberPermissions.rebind===false)table.querySelectorAll('[data-member-rebind]').forEach(button=>button.remove());
 if(memberPermissions.coin===false)table.querySelectorAll('[data-coin]').forEach(button=>button.remove());
 const all=table.querySelector('thead input[type=checkbox]'),boxes=[...table.querySelectorAll('[data-select]')];
 all.setAttribute('aria-label','全选本页会员');
 const update=()=>{const selected=boxes.filter(box=>box.checked);all.checked=selected.length>0&&selected.length===boxes.length;all.indeterminate=selected.length>0&&selected.length<boxes.length;all.disabled=boxes.length===0;edit.disabled=selected.length!==1;boxes.forEach(box=>{const row=box.closest('tr');row.classList.toggle('selected',box.checked);row.setAttribute('aria-selected',String(box.checked));});};
 all.onchange=()=>{boxes.forEach(box=>box.checked=all.checked);update();};boxes.forEach(box=>box.onchange=update);update();
 table.querySelector('tbody').onclick=event=>{if(event.target.closest('button,a,input,select,textarea,label'))return;const row=event.target.closest('tr'),box=row?.querySelector('[data-select]');if(!box||box.disabled)return;box.checked=!box.checked;update();};
 edit.onclick=()=>{const selected=boxes.filter(box=>box.checked);if(selected.length!==1||!table.isConnected)return;selected[0].closest('tr').querySelector('[data-edit]')?.click();};
}
function attachMemberSorting(){
 for(const key of ['id','coin_user','coin','freeze_coin','created_at','game_addiction_time']){
  const heading=document.querySelector(`#content th[data-field="${key}"]`);if(!heading)continue;
  const active=(state.memberSort||'id')===key,order=state.memberOrder||'desc';
  const label=heading.textContent,button=document.createElement('button'),icon=document.createElement('span');
  heading.setAttribute('aria-sort',active?(order==='asc'?'ascending':'descending'):'none');
  button.type='button';button.className='member-sort';button.dataset.memberSort=key;button.textContent=label;
  icon.setAttribute('aria-hidden','true');icon.textContent=active?(order==='asc'?'▲':'▼'):'▴▾';button.append(icon);
  heading.replaceChildren(button);
  button.onclick=()=>{state.memberSort=key;state.memberOrder=active&&order==='asc'?'desc':'asc';state.page=1;load();};
 }
}
function memberCell(row,key,value){
 if(state.view!=='members')return esc(value);
 if(['username','parent_id','game_name','agent_name','name','ip'].includes(key))return value==null||value===''?'':`<button type="button" class="member-cell-search" data-member-search-field="${key}" data-member-search-value="${esc(value)}" title="点击搜索 ${esc(value)}">${esc(value)}</button>`;
 if(key==='image_url'){
  if(!value)return '';
  try{const url=new URL(value,location.origin);if(!['http:','https:'].includes(url.protocol))return '';return `<a href="${esc(url.href)}" target="_blank" rel="noopener"><img class="member-avatar" src="${esc(url.href)}" alt="头像" loading="lazy"></a>`;}catch{return '';}
 }
 if(key==='exchange_enable')return value==null?'':`<button type="button" role="switch" aria-label="兑换" aria-checked="${String(value)==='1'}" class="member-switch ${String(value)==='1'?'on':''}" data-member-exchange="${esc(row.id)}" data-next-exchange="${String(value)==='1'?0:1}">${String(value)==='1'?'是':'否'}</button>`;
 if(key==='game_addiction_enable')return value==null?'':`<span class="member-boolean ${String(value)==='1'?'on':''}">${String(value)==='1'?'是':'否'}</span>`;
 if(['created_at','updated_at','last_login_time'].includes(key))return esc(profileLogTime(value));
 if(key==='username')return esc(value);
 if(key==='vip')return value==null?'':`<button type="button" class="member-cell-search" data-member-search-field="vip" data-member-search-value="${esc(value)}" title="VIP: V${esc(value)}"><span class="vip-badge vip-${esc(value)}">V${esc(value)}</span></button>`;
 if(key==='status'||key==='is_white'){
  const on=String(row[key])==='1', white=key==='is_white';
  return `<button type="button" role="switch" aria-checked="${on}" aria-label="${white?'\u767d\u540d\u5355':'\u72b6\u6001'}" class="member-switch ${on?'on':''}" ${white?'data-white':'data-toggle'}="${esc(row.id)}" ${white?'data-next-white':'data-next-status'}="${on?0:1}">${on?'\u5f00':'\u5173'}</button>`;
 }
 return esc(value);
}
document.addEventListener('click',async event=>{
 const button=event.target.closest('.member-switch[data-member-exchange],.member-switch[data-white],.member-switch[data-toggle]');if(!button||state.view!=='members')return;
 event.stopImmediatePropagation();event.preventDefault();if(button.disabled)return;
 const field=button.hasAttribute('data-white')?'is_white':button.hasAttribute('data-toggle')?'status':'exchange_enable';
 const id=button.dataset.white||button.dataset.toggle||button.dataset.memberExchange;
 const value=Number(button.dataset.nextWhite??button.dataset.nextStatus??button.dataset.nextExchange);
 const route=location.hash,generation=pageLoadGeneration;
 const current=()=>location.hash===route&&generation===pageLoadGeneration&&button.isConnected;
 button.disabled=true;
 try{
  await api('/members/'+encodeURIComponent(id),{method:'PATCH',body:JSON.stringify({[field]:value})});
  if(current())await load();
 }catch(error){if(current()){button.disabled=false;alert(error.message);}}
},true);
document.addEventListener('click',event=>{
 const button=event.target.closest('[data-member-search-field]');if(!button||state.view!=='members')return;
 const key=button.dataset.memberSearchField;if(!['username','parent_id','game_name','agent_name','name','ip','vip'].includes(key))return;
 state.memberFilters={...(state.memberFilters||{}),[key]:button.dataset.memberSearchValue};
 if(key==='game_name')delete state.memberFilters.game_id;
 if(key==='agent_name')delete state.memberFilters.agent_id;
 state.page=1;load();
});

