const tutorialState={tableState:null,controller:null,dialogs:new Set(),windowIndex:0};
let tutorialSanitizerReady;
function tutorialCell(row,column,interactive){
 if(column[0]==='tutorial_actions')return interactive?`<button type="button" class="tutorial-detail" data-tutorial="${esc(row.id)}" title="详情"><i class="shell-icon" aria-hidden="true">&#xf03a;</i> 详情</button>`:'';
 if(column[2]==='date')return row[column[0]]?esc(profileLogTime(row[column[0]])):'无';
 return esc(row[column[0]]??'');
}
function mountTutorialActions(panel,s){
 const form=panel.querySelector('form'),results=panel.querySelector('.game-user-results'),selected=new Set();
 panel.querySelector('section').classList.add('tutorial-panel');form.id='tutorialFilters';results.id='tutorialList';
 panel.querySelector('[role=alert]').id='tutorialError';panel.querySelector('.game-user-pagination').id='tutorialPagination';
 panel.querySelector('[data-action=refresh]').id='tutorialRefresh';panel.querySelector('[data-action=search]').id='tutorialSearch';
 for(const [selector,icon] of [['[data-action=cards]','list-alt'],['[data-action=search]','search'],['.game-user-columns summary','th'],['.game-user-export summary','export']]){
  const control=panel.querySelector(selector);control.title=control.getAttribute('aria-label');
  control.innerHTML=`<i class="glyphicon glyphicon-${icon}" aria-hidden="true"></i>${control.tagName==='SUMMARY'?' <span class="caret"></span>':''}`;
 }
 panel.querySelector('.game-user-table-tools').append(panel.querySelector('[data-action=search]'));
 const sync=()=>{
  const boxes=[...results.querySelectorAll('[data-tutorial-select]')],all=results.querySelector('[data-tutorial-all]');
  boxes.forEach(box=>{box.checked=selected.has(Number(box.dataset.tutorialSelect));box.closest('tr,article').classList.toggle('selected',box.checked);});
  if(all){all.checked=boxes.length>0&&boxes.every(box=>box.checked);all.indeterminate=boxes.some(box=>box.checked)&&!all.checked;all.disabled=!boxes.length;}
 };
 results.onclick=event=>{
  if(results.hasAttribute('aria-busy'))return;
  const button=event.target.closest('[data-tutorial]');
  if(button){openTutorial(Number(button.dataset.tutorial));return;}
  if(!event.target.closest('button,a,input,select,textarea,label,summary'))event.target.closest('tr,article')?.querySelector('[data-tutorial-select]')?.click();
 };
 return {
  selectedItems:()=>s.items.filter(row=>selected.has(row.id)),loaded:()=>selected.clear(),
  paint(){
   const table=results.querySelector('table'),containers=table?[...table.tBodies[0].rows]:[...results.querySelectorAll('article')];
   if(table){table.classList.add('tutorial-table');table.tHead.rows[0].insertAdjacentHTML('afterbegin','<th><input type="checkbox" data-tutorial-all aria-label="全选本页教程"></th>');if(!s.items.length)table.tBodies[0].rows[0].cells[0].colSpan++;}
   else results.querySelectorAll('article>div').forEach(row=>{row.querySelector('strong').textContent=row.querySelector('strong').textContent.slice(0,-1);});
   s.items.forEach((row,index)=>containers[index].insertAdjacentHTML('afterbegin',`<${table?'td':'div'} class="tutorial-selection"><input type="checkbox" data-tutorial-select="${esc(row.id)}" aria-label="选择教程 ${esc(row.id)}"></${table?'td':'div'}>`));
   results.querySelectorAll('[data-tutorial-select]').forEach(box=>box.onchange=()=>{box.checked?selected.add(Number(box.dataset.tutorialSelect)):selected.delete(Number(box.dataset.tutorialSelect));sync();});
   results.querySelector('[data-tutorial-all]')?.addEventListener('change',event=>{s.items.forEach(row=>event.target.checked?selected.add(row.id):selected.delete(row.id));sync();});sync();
  },
  destroy(){selected.clear();}
 };
}
async function renderBook(){
 tutorialState.controller?.destroy();for(const dialog of tutorialState.dialogs)dialog.close();
 $('#content').innerHTML='<div id="tutorialHost"></div>';
 tutorialState.controller=mountGameUserTable($('#tutorialHost'),null,{endpoint:'/tutorials',absolute:true,state:tutorialState.tableState,
  columns:[['id','Id'],['name','标题'],['created_at','创建时间','date'],['updated_at','更新时间','date',false],['tutorial_actions','操作']],
  cell:tutorialCell,mountActions:mountTutorialActions,exportExcludeFields:['tutorial_actions'],
  exportFileName:()=>'export_'+new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date())});
 tutorialState.tableState=tutorialState.controller.state;await tutorialState.controller.refresh();
}
function openTutorial(id){
 const dialog=document.createElement('dialog');dialog.id='tutorialDialog'+(++tutorialState.windowIndex);dialog.className='tutorial-dialog';dialog.setAttribute('aria-label','详情');
 dialog.innerHTML='<header><span>详情</span><button type="button" data-tutorial-minimize aria-label="最小化" title="最小化"></button><button type="button" data-tutorial-maximize aria-label="最大化" title="最大化"></button><button type="button" data-tutorial-close aria-label="关闭" title="关闭"></button></header><main></main>';
 document.body.append(dialog);dialog.show();tutorialState.dialogs.add(dialog);
 const focus=()=>{dialog.style.zIndex=String(100+(++tutorialState.windowIndex));};dialog.addEventListener('pointerdown',focus);focus();
 const main=dialog.querySelector('main'),header=dialog.querySelector('header'),maximize=dialog.querySelector('[data-tutorial-maximize]');
 let closed=false,request,version=0,drag=null,shiftX=0,shiftY=0;
 const close=()=>dialog.close(),updateWindow=()=>{const label=dialog.classList.contains('expanded')||dialog.classList.contains('minimized')?'还原':'最大化';maximize.title=label;maximize.setAttribute('aria-label',label);};
 dialog.querySelector('[data-tutorial-close]').onclick=close;
 const positionDock=()=>{if(!dialog.classList.contains('minimized'))return;const slot=Number(dialog.dataset.dockSlot),columns=Math.max(1,Math.floor(innerWidth/181));dialog.style.setProperty('--tutorial-dock-left',(slot%columns)*181+'px');dialog.style.setProperty('--tutorial-dock-bottom',Math.floor(slot/columns)*46+'px');};
 dialog.querySelector('[data-tutorial-minimize]').onclick=()=>{
  const used=new Set([...tutorialState.dialogs].filter(item=>item.classList.contains('minimized')).map(item=>Number(item.dataset.dockSlot)));let slot=0;while(used.has(slot))slot++;
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
  const top=[...tutorialState.dialogs].filter(item=>item.open).sort((a,b)=>Number(b.style.zIndex)-Number(a.style.zIndex))[0];
  if(top===dialog){event.preventDefault();close();}
 };
 document.addEventListener('keydown',escape);
 window.addEventListener('resize',positionDock);
 dialog.addEventListener('close',()=>{if(dialog.open)return;closed=true;request?.abort();drag=null;window.removeEventListener('hashchange',close);window.removeEventListener('resize',positionDock);document.removeEventListener('keydown',escape);dialog.remove();tutorialState.dialogs.delete(dialog);});
 async function load(){
  request?.abort();request=new AbortController();const generation=++version;main.innerHTML='<p class="tutorial-loading" role="status">加载中</p>';
  try{
   if(!tutorialSanitizerReady)tutorialSanitizerReady=loadReviewScript('/vendor/purify.min.js').catch(error=>{tutorialSanitizerReady=null;throw error;});
   const [row]=await Promise.all([api('/tutorials/'+id,{signal:request.signal}),tutorialSanitizerReady]);
   if(closed||generation!==version)return;
   const fragment=DOMPurify.sanitize(row.content||'',{RETURN_DOM_FRAGMENT:true,USE_PROFILES:{html:true},FORBID_TAGS:['style','form','input','button','textarea','select','link','meta'],FORBID_ATTR:['srcdoc','srcset','autofocus']});
   fragment.querySelectorAll('a').forEach(link=>{link.rel='noopener noreferrer';link.target='_blank';});
   const content=document.createElement('div');content.append(fragment);
   const frame=document.createElement('iframe');frame.title='教程正文';frame.className='tutorial-frame';
   frame.setAttribute('sandbox','allow-same-origin allow-popups allow-popups-to-escape-sandbox');
   frame.onload=()=>{if(closed)return;frame.contentDocument.addEventListener('pointerdown',focus);frame.contentDocument.addEventListener('keydown',escape);};
   frame.srcdoc='<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/vendor/bootstrap.min.css"><link rel="stylesheet" href="/tutorial-content.css"></head><body><article class="tutorial-content">'+content.innerHTML+'</article></body></html>';
   main.replaceChildren(frame);
  }catch(error){if(!closed&&generation===version&&error.name!=='AbortError'){
   main.innerHTML='<div class="tutorial-loading"><p role="alert"></p><button type="button">重试</button></div>';main.querySelector('[role=alert]').textContent=error.message;main.querySelector('button').onclick=load;
  }}
 }
 load();return dialog;
}
window.addEventListener('hashchange',()=>{if(!/^#book(?:$|[?&])/.test(location.hash)){tutorialState.controller?.destroy();for(const dialog of tutorialState.dialogs)dialog.close();}});
