const agentState={tableState:null,controller:null};
const agentOssWindows={dialogs:new Set(),windowIndex:0};
function agentCell(row,column,interactive,permissions){
 const key=column[0];
 if(key==='agent_actions')return interactive?(permissions.edit?`<button type="button" data-edit="${esc(row.id)}" class="agent-edit">编辑</button>`:'')+(permissions.delete?` <button type="button" data-delete="${esc(row.id)}" class="agent-delete">删除</button>`:''):'';
 if(key==='buttons'){
  if(!interactive)return (permissions.oss?'OSS配置':'')+(permissions.dashboard&&!row.parent_id?(permissions.oss?'  ':'')+'进入':'');
  return (permissions.oss?`<button type="button" class="agent-oss" data-agent-oss="${esc(row.id)}">OSS配置</button>`:'')+(permissions.dashboard&&!row.parent_id?` <button type="button" class="agent-enter" data-agent-enter="${esc(row.id)}" title="游戏管理"><i class="fa fa-gamepad" aria-hidden="true"></i> 进入</button>`:'');
 }
 if(key==='status')return [0,1].includes(Number(row.status))?`<span class="agent-status ${Number(row.status)===1?'enabled':'disabled'}">${Number(row.status)===1?'启用':'禁用'}</span>`:'';
 if(column[2]==='date')return row[key]?esc(profileLogTime(row[key])):'无';
 return esc(row[key]??'');
}
function mountAgentActions(panel,s,refresh){
 const form=panel.querySelector('form'),results=panel.querySelector('.game-user-results'),errorBox=panel.querySelector('[role=alert]'),selected=new Set();
 let closed=false,busy=false;
 panel.querySelector('section').classList.add('agent-panel');form.id='agentFilters';results.id='agentList';
 errorBox.id='reviewError';panel.querySelector('.game-user-pagination').id='agentPagination';
 panel.querySelector('[data-action=refresh]').id='agentRefresh';panel.querySelector('[data-action=search]').id='agentSearchToggle';
 for(const [selector,icon] of [['[data-action=cards]','list-alt'],['[data-action=search]','search'],['.game-user-columns summary','th'],['.game-user-export summary','export']]){
  const control=panel.querySelector(selector);control.title=control.getAttribute('aria-label');
  control.innerHTML=`<i class="glyphicon glyphicon-${icon}" aria-hidden="true"></i>${control.tagName==='SUMMARY'?' <span class="caret"></span>':''}`;
 }
 panel.querySelector('.game-user-table-tools').append(panel.querySelector('[data-action=search]'));
 const more=document.createElement('details');more.className='game-member-more agent-more';
 more.innerHTML='<summary aria-disabled="true"><i class="fa fa-cog" aria-hidden="true"></i> 更多 <span class="caret"></span></summary><div><button type="button" data-agent-batch="1"><i class="fa fa-eye" aria-hidden="true"></i> 启用</button><button type="button" data-agent-batch="0"><i class="fa fa-eye-slash" aria-hidden="true"></i> 禁用</button></div>';
 panel.querySelector('#agentRefresh').after(more);
 const create=document.createElement('button');create.type='button';create.id='agentCreate';create.hidden=true;create.innerHTML='<i class="fa fa-plus" aria-hidden="true"></i> 添加';create.onclick=()=>document.querySelector('.topbar #createButton').click();more.before(create);
 const sync=()=>{
  const boxes=[...results.querySelectorAll('[data-agent-select]')],all=results.querySelector('#agentSelectAll');
  boxes.forEach(box=>{box.checked=selected.has(Number(box.dataset.agentSelect));box.disabled=busy;box.closest('tr,article').classList.toggle('selected',box.checked);});
  if(all){all.checked=boxes.length>0&&boxes.every(box=>box.checked);all.indeterminate=boxes.some(box=>box.checked)&&!all.checked;all.disabled=!boxes.length||busy;}
  const disabled=busy||!selected.size||!s.permissions?.batch_status;
  more.querySelector('summary').setAttribute('aria-disabled',String(disabled));if(disabled)more.open=false;
  more.querySelectorAll('button').forEach(button=>button.disabled=disabled);
  create.hidden=!s.permissions?.create;more.hidden=!s.permissions?.batch_status;
 };
 more.querySelector('summary').onclick=event=>{if(event.currentTarget.getAttribute('aria-disabled')==='true')event.preventDefault();};
 more.querySelectorAll('[data-agent-batch]').forEach(button=>button.onclick=async()=>{
  if(busy||!selected.size||!s.permissions?.batch_status)return;
  const ids=[...selected];if(ids.length>10000){errorBox.textContent='单次最多处理 10000 个主体';return;}
  busy=true;sync();errorBox.textContent='';
  try{await api('/agents/batch-status',{method:'POST',body:JSON.stringify({ids,status:Number(button.dataset.agentBatch)})});if(!closed)await refresh();}
  catch(error){if(!closed)errorBox.textContent=error.message;}
  finally{busy=false;if(!closed)sync();}
 });
 results.onclick=event=>{
  if(results.hasAttribute('aria-busy')||busy)return;
  const oss=event.target.closest('[data-agent-oss]'),enter=event.target.closest('[data-agent-enter]');
  if(oss){openAgentOss(Number(oss.dataset.agentOss));return;}
  if(enter){sessionStorage.setItem('agent-dashboard-id',enter.dataset.agentEnter);location.hash='agent-dashboard';return;}
  if(!event.target.closest('button,a,input,select,textarea,label,summary'))event.target.closest('tr,article')?.querySelector('[data-agent-select]')?.click();
 };
 return {
  selectedItems:()=>s.items.filter(row=>selected.has(row.id)),loaded:()=>selected.clear(),
  paint(){
   const table=results.querySelector('table'),containers=table?[...table.tBodies[0].rows]:[...results.querySelectorAll('article')];
   if(table){table.tHead.rows[0].insertAdjacentHTML('afterbegin','<th><input type="checkbox" id="agentSelectAll" aria-label="全选本页主体"></th>');const buttons=table.querySelector('th[data-field=buttons]');if(buttons)buttons.innerHTML='<span>游戏管理</span>';if(!s.items.length)table.tBodies[0].rows[0].cells[0].colSpan++;}
   else results.querySelectorAll('article>div').forEach(row=>{row.querySelector('strong').textContent=row.querySelector('strong').textContent.slice(0,-1);row.hidden=!row.querySelector('span').textContent.trim();});
   s.items.forEach((row,index)=>containers[index].insertAdjacentHTML('afterbegin',`<${table?'td':'div'} class="agent-selection"><input type="checkbox" data-agent-select="${esc(row.id)}" aria-label="选择主体 ${esc(row.id)}"></${table?'td':'div'}>`));
   results.querySelectorAll('[data-agent-select]').forEach(box=>box.onchange=()=>{box.checked?selected.add(Number(box.dataset.agentSelect)):selected.delete(Number(box.dataset.agentSelect));sync();});
   results.querySelector('#agentSelectAll')?.addEventListener('change',event=>{s.items.forEach(row=>event.target.checked?selected.add(row.id):selected.delete(row.id));sync();});sync();
  },
  destroy(){closed=true;selected.clear();document.querySelectorAll('.agent-oss-dialog').forEach(dialog=>dialog.close());}
 };
}
async function renderAgents(){
 if(state.view!=='agents')return;agentState.controller?.destroy();
 $('#content').innerHTML='<div id="agentHost"></div>';
 agentState.controller=mountGameUserTable($('#agentHost'),null,{endpoint:'/agents',absolute:true,state:agentState.tableState,
  columns:[['id','Id','sort'],['name','代理商名称'],['buttons','游戏管理'],['user_id','穿山甲user_id',null,false],['role_id','穿山甲role_id',null,false],['security_key','穿山甲security_key',null,false],['status','状态'],['created_at','创建时间','date'],['updated_at','更新时间','date',false],['agent_actions','操作']],
  filterColumns:[['name','代理商名称','search'],['status','状态',{1:'启用',0:'禁用'}],['created_at','创建时间','date'],['updated_at','更新时间','date']],
  cell:(row,column,interactive)=>agentCell(row,column,interactive,agentState.tableState?.permissions||{}),mountActions:mountAgentActions,exportExcludeFields:['agent_actions'],exportCell:agentExportCell,
  exportXmlCell:agentExportXmlCell,
  onLoad:data=>{agentState.tableState.permissions=data.permissions||{};},
  exportFileName:()=>'export_'+new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date())});
 agentState.tableState=agentState.controller.state;await agentState.controller.refresh();
}
window.addEventListener('hashchange',()=>{if(!/^#agents(?:$|[?&])/.test(location.hash)){agentState.controller?.destroy();agentState.controller=null;}});

function agentExportCell(row,column){
 const permissions=agentState.tableState?.permissions||{};
 if(column[0]==='buttons')return (permissions.oss?'<a><i class=""></i> OSS配置</a>':'')+(permissions.dashboard&&!row.parent_id?' <a><i class="fa fa-gamepad"></i> 进入</a>':'');
 if(column[0]==='status')return `<a><span class="label label-${Number(row.status)===1?'warning':'success'}">${Number(row.status)===1?'启用':'禁用'}</span></a>`;
 return agentCell(row,column,false,permissions);
}
function agentExportXmlCell(cell){
 const links=[...cell.querySelectorAll('a')];if(!links.length)return cell.textContent;
 const fragment=document.createDocumentFragment();links.forEach((link,index)=>{if(index)fragment.append(document.createTextNode(' '));for(const node of link.childNodes)fragment.append(node.cloneNode(true));});return fragment;
}

async function renderAgentDashboard(){
 const id=Number(sessionStorage.getItem('agent-dashboard-id'));
 if(!Number.isInteger(id)||id<=0){$('#content').innerHTML='<p>请从主体管理选择主体。<a href="#agents">主体管理</a></p>';return;}
 const data=await api('/agents/'+id+'/dashboard');if(state.view!=='agent-dashboard')return;
 $('#content').innerHTML=`<section class="agent-dashboard"><div class="agent-dashboard-name">代理商名称：${esc(data.agent_name)}</div><div class="agent-dashboard-tools"><button id="agentDashboardRefresh">数据统计</button></div><div class="agent-dashboard-cards"><article><i class="fa fa-user-plus"></i><div><strong>${data.today_new}</strong><span>今日新增</span></div></article><article><i class="fa fa-user-md"></i><div><strong>${data.today_login}</strong><span>今日登陆</span></div></article></div><div class="agent-dashboard-chart"><div id="agentChart" role="img" aria-label="&#27880;&#20876;&#29992;&#25143;&#25968;"></div></div></section>`;
 $('#agentDashboardRefresh').onclick=renderAgentDashboard;
 for(const [hash,text] of [['agent-analysis','\u6570\u636e\u5206\u6790'],['agent-games','\u6e38\u620f\u5217\u8868'],['members','\u7528\u6237\u5217\u8868'],['withdrawals','\u7528\u6237\u63d0\u73b0']]){const link=document.createElement('a');link.href='#'+hash+(['members','withdrawals'].includes(hash)?'?agent_id='+id:'');link.textContent=text;link.dataset.agentScoped='true';document.querySelector('.agent-dashboard-tools').append(link);}
 await mountAgentChart(data.items);
}
function createAgentWindow(title,extraClass=''){
 const dialog=document.createElement('dialog');dialog.id='agentOssDialog'+(++agentOssWindows.windowIndex);dialog.className='agent-oss-dialog'+(extraClass?' '+extraClass:'');dialog.setAttribute('aria-label',title);
 dialog.innerHTML='<header><span></span><button type="button" data-agent-oss-minimize aria-label="最小化" title="最小化"></button><button type="button" data-agent-oss-maximize aria-label="最大化" title="最大化"></button><button type="button" data-agent-oss-close aria-label="关闭" title="关闭"></button></header><main class="agent-oss-body"></main>';dialog.querySelector('header span').textContent=title;
 document.body.append(dialog);dialog.show();agentOssWindows.dialogs.add(dialog);
 const focus=()=>{dialog.style.zIndex=String(100+(++agentOssWindows.windowIndex));};dialog.addEventListener('pointerdown',focus);focus();
 const body=dialog.querySelector('main'),header=dialog.querySelector('header'),maximize=dialog.querySelector('[data-agent-oss-maximize]');
 let closed=false,drag=null,shiftX=0,shiftY=0;
 const close=()=>dialog.close(),updateWindow=()=>{const label=dialog.classList.contains('expanded')||dialog.classList.contains('minimized')?'还原':'最大化';maximize.title=label;maximize.setAttribute('aria-label',label);};
 dialog.querySelector('[data-agent-oss-close]').onclick=close;
 const positionDock=()=>{if(!dialog.classList.contains('minimized'))return;const slot=Number(dialog.dataset.dockSlot),columns=Math.max(1,Math.floor(innerWidth/181));dialog.style.setProperty('--agent-oss-dock-left',(slot%columns)*181+'px');dialog.style.setProperty('--agent-oss-dock-bottom',Math.floor(slot/columns)*46+'px');};
 dialog.querySelector('[data-agent-oss-minimize]').onclick=()=>{
  const used=new Set([...agentOssWindows.dialogs].filter(item=>item.classList.contains('minimized')).map(item=>Number(item.dataset.dockSlot)));let slot=0;while(used.has(slot))slot++;
  dialog.dataset.dockSlot=String(slot);dialog.close();dialog.classList.add('minimized');positionDock();dialog.show();updateWindow();
 };
 maximize.onclick=()=>{if(dialog.classList.contains('minimized')){dialog.close();dialog.classList.remove('minimized');delete dialog.dataset.dockSlot;dialog.show();}else dialog.classList.toggle('expanded');updateWindow();};
 header.onpointerdown=event=>{
  if(event.button!==0||event.target.closest('button')||dialog.classList.contains('expanded')||dialog.classList.contains('minimized'))return;
  const rect=dialog.getBoundingClientRect();drag={id:event.pointerId,x:event.clientX,y:event.clientY,left:rect.left,top:rect.top,width:rect.width,height:rect.height,shiftX,shiftY};header.setPointerCapture(event.pointerId);event.preventDefault();
 };
 header.onpointermove=event=>{
  if(!drag||drag.id!==event.pointerId)return;
  const left=Math.min(Math.max(0,drag.left+event.clientX-drag.x),Math.max(0,innerWidth-drag.width)),top=Math.min(Math.max(0,drag.top+event.clientY-drag.y),Math.max(0,innerHeight-drag.height));
  shiftX=drag.shiftX+left-drag.left;shiftY=drag.shiftY+top-drag.top;dialog.style.transform=`translate(${shiftX}px,${shiftY}px)`;
 };
 const endDrag=event=>{if(drag?.id!==event.pointerId)return;drag=null;if(header.hasPointerCapture(event.pointerId))header.releasePointerCapture(event.pointerId);};
 header.onpointerup=endDrag;header.onpointercancel=endDrag;header.onlostpointercapture=()=>{drag=null;};
 window.addEventListener('hashchange',close);
 const escape=event=>{
  if(event.key!=='Escape'||event.defaultPrevented||closed)return;
  const top=[...agentOssWindows.dialogs].filter(item=>item.open).sort((a,b)=>Number(b.style.zIndex)-Number(a.style.zIndex))[0];
  if(top===dialog){event.preventDefault();close();}
 };
 document.addEventListener('keydown',escape);
 window.addEventListener('resize',positionDock);
 dialog.addEventListener('close',()=>{if(dialog.open)return;closed=true;drag=null;window.removeEventListener('hashchange',close);window.removeEventListener('resize',positionDock);document.removeEventListener('keydown',escape);dialog.remove();agentOssWindows.dialogs.delete(dialog);});
 return {dialog,body};
}
async function openAgentOss(id){
 const {dialog,body}=createAgentWindow('OSS配置');
 let closed=false,request,generation=0,busy=false;
 dialog.addEventListener('close',()=>{if(dialog.open)return;closed=true;request?.abort();});
 const route=location.hash,current=version=>!closed&&dialog.open&&dialog.isConnected&&location.hash===route&&version===generation;
 async function read(){
  request?.abort();request=new AbortController();const version=++generation;body.innerHTML='<p role="status">加载中</p>';
  try{
   const data=await api('/agents/'+id+'/oss',{signal:request.signal});if(!current(version))return;
   body.innerHTML='<form>'+['ossKey','ossKeySecret','endPoint','bucket'].map(key=>`<label><span>${key}:</span><input name="${key}" type="text" autocomplete="off" value="${esc(data[key]||'')}"></label>`).join('')+'<p role="alert"></p><footer><button type="submit">确定</button><button type="reset">重置</button></footer></form>';
   const form=body.querySelector('form');form.onsubmit=async event=>{
    event.preventDefault();if(busy||!current(version))return;
    const payload=Object.fromEntries(new FormData(form)),controls=[...form.querySelectorAll('input,button')];busy=true;controls.forEach(control=>control.disabled=true);form.querySelector('[role=alert]').textContent='';
    try{await api('/agents/'+id+'/oss',{method:'PATCH',body:JSON.stringify(payload)});if(current(version))dialog.close();}
    catch(error){if(current(version))form.querySelector('[role=alert]').textContent=error.message;}
    finally{busy=false;if(current(version))controls.forEach(control=>control.disabled=false);}
   };
  }catch(error){
   if(current(version)&&error.name!=='AbortError'){body.innerHTML='<p role="alert"></p><button type="button" data-agent-oss-retry>重试</button>';body.querySelector('[role=alert]').textContent=error.message;body.querySelector('button').onclick=read;}
  }
 }
 await read();
}

document.addEventListener('DOMContentLoaded',()=>{views['agent-dashboard']=['\u6e38\u620f\u7ba1\u7406',''];});

if(document.readyState==='loading')document.write('<link rel="stylesheet" href="/agent-form.css"><script src="/agent-form.js"><\/script>');

