function withdrawalConfirm(message){
 return new Promise(resolve=>{
  const dialog=document.createElement('dialog');dialog.className='withdrawal-confirm';
  dialog.innerHTML=`<form method="dialog"><header><span>提示</span><button value="cancel" aria-label="关闭">×</button></header><div class="withdrawal-confirm-message">${esc(message)}</div><footer><button value="confirm" class="withdrawal-confirm-ok">确定</button><button value="cancel">取消</button></footer></form>`;
  const cancel=()=>dialog.close('cancel');
  window.addEventListener('hashchange',cancel);
  dialog.addEventListener('close',()=>{const confirmed=dialog.returnValue==='confirm';window.removeEventListener('hashchange',cancel);dialog.remove();resolve(confirmed);},{once:true});
  document.body.append(dialog);dialog.showModal();dialog.querySelector('.withdrawal-confirm-ok').focus();
 });
}

function attachWithdrawalSelection(items,summary={},permissions={}){
 const panel=document.querySelector('.withdrawal-panel'),table=panel.querySelector('table');
 const sourceState=reviewStates.withdrawals,generation=sourceState.generation;
 const active=()=>panel.isConnected&&state.view==='withdrawals'&&reviewStates.withdrawals===sourceState&&sourceState.generation===generation;
 table.tHead.rows[0].insertAdjacentHTML('afterbegin','<th><input id="withdrawalSelectAll" type="checkbox" aria-label="全选本页提现"></th>');
 [...table.tBodies[0].rows].forEach((row,index)=>{
  if(!items.length){row.cells[0].colSpan++;return;}
  row.insertAdjacentHTML('afterbegin',`<td><input type="checkbox" data-withdrawal-select="${items[index].id}" aria-label="选择提现 ${items[index].id}"></td>`);
 });
 const amount=key=>summary[key]!=null&&Number.isFinite(Number(summary[key]))?esc(Number(summary[key])/10)+'元':'-';
 panel.querySelector('.withdrawal-toolbar').insertAdjacentHTML('beforeend',`<button id="withdrawalBatchRefuse" ${permissions.review===false?'hidden ':''}disabled><i class="shell-icon" aria-hidden="true">&#xf0d6;</i> 批量拒绝</button><button id="withdrawalBatchTransfer" ${permissions.transfer===false?'hidden ':''}disabled><i class="shell-icon" aria-hidden="true">&#xf0d6;</i> 批量支付宝转账(实时)</button>${[['withdrawn','已提现'],['pending','提现中'],['blacklisted','拉黑已提现']].map(([key,label])=>`<span class="withdrawal-summary" data-withdrawal-summary="${key}">${label}：${amount(key)}</span>`).join('')}`);
 const boxes=[...table.querySelectorAll('[data-withdrawal-select]')],all=panel.querySelector('#withdrawalSelectAll'),buttons=[panel.querySelector('#withdrawalBatchRefuse'),panel.querySelector('#withdrawalBatchTransfer')];
 const blacklist=document.createElement('button');blacklist.id='withdrawalBlacklist';blacklist.hidden=permissions.blacklist===false;blacklist.innerHTML='<i class="shell-icon" aria-hidden="true">&#xf007;</i> 黑名单';
 buttons[1].after(blacklist);blacklist.onclick=openWithdrawalBlacklist;
 panel.querySelectorAll('[data-withdrawal-blacklist]').forEach(button=>button.onclick=async()=>{
  const row=items.find(item=>String(item.id)===button.dataset.withdrawalBlacklist);if(!row||button.disabled||!active())return;
  button.disabled=true;
  try{
   if(!await withdrawalConfirm('确认拉黑吗')||!active())return;
   await api('/withdrawals/'+row.id+'/blacklist',{method:'POST',body:JSON.stringify({receive_name:row.receive_name||'',receive_tel:row.receive_tel||''})});
   if(active())await renderReviewPage('withdrawals');
  }catch(error){if(active())panel.querySelector('#reviewError').textContent=error.message;}
  finally{button.disabled=false;}
 });
 let busy=false;
 const update=()=>{
  const count=boxes.filter(box=>box.checked).length;
  all.checked=count>0&&count===boxes.length;all.indeterminate=count>0&&count<boxes.length;
  all.disabled=busy||boxes.length===0;boxes.forEach(box=>box.disabled=busy);buttons.forEach(button=>button.disabled=busy||count===0);
 };
 all.onchange=()=>{boxes.forEach(box=>box.checked=all.checked);update();};boxes.forEach(box=>box.onchange=update);update();
 buttons.forEach(button=>button.onclick=async()=>{
  const ids=boxes.filter(box=>box.checked).map(box=>Number(box.dataset.withdrawalSelect));
  if(busy||!ids.length)return;
  busy=true;update();
  const transfer=button.id==='withdrawalBatchTransfer';
  try{
   if(!await withdrawalConfirm(transfer?'确认批量支付宝转账(实时)吗':'确认批量拒绝吗')||!active())return;
   panel.querySelector('#reviewError').textContent='';
   await api('/withdrawals/'+(transfer?'batch-transfer':'batch-refuse'),{method:'POST',body:JSON.stringify({ids})});
   if(active())await renderReviewPage('withdrawals');
  }catch(error){if(active())panel.querySelector('#reviewError').textContent=error.message;}
  finally{busy=false;update();}
 });
}

function attachWithdrawalSorting(kind='withdrawals'){
 const s=reviewStates[kind];
 for(const key of (kind==='subsidies'?['id','tx_price','price','created_at','updated_at']:['id','exchange_value','created_at','updated_at'])){
  const heading=document.querySelector(`[data-review-column="${key}"]`);
  const label=heading.textContent,active=(s.sort||'id')===key,order=s.order||'desc';
  heading.setAttribute('aria-sort',active?(order==='asc'?'ascending':'descending'):'none');
  heading.innerHTML=`<button class="withdrawal-sort" data-withdrawal-sort="${key}">${esc(label)}<span aria-hidden="true">${active?(order==='asc'?'▲':'▼'):'▴▾'}</span></button>`;
  heading.querySelector('button').onclick=()=>{s.order=active?(order==='asc'?'desc':'asc'):'asc';s.sort=key;s.page=1;renderReviewPage(kind);};
 }
}

function attachWithdrawalColumns(columns,kind='withdrawals'){
 const s=reviewStates[kind],panel=document.querySelector('.withdrawal-panel');
 if(!s.visibleColumns)s.visibleColumns=columns.filter(([, ,visible])=>visible!==false).map(([key])=>key);
 const shown=new Set(s.visibleColumns);
 const menu=document.createElement('details');menu.className='withdrawal-columns';
 menu.innerHTML=`<summary aria-label="显示列" title="显示列"><i class="glyphicon glyphicon-th" aria-hidden="true"></i> <span class="caret"></span></summary><div class="withdrawal-column-options">${columns.map(([key,label])=>`<label><input type="checkbox" data-withdrawal-column="${key}" ${shown.has(key)?'checked':''}> ${esc(label)}</label>`).join('')}</div>`;
 panel.querySelector('.withdrawal-toolbar').append(menu);
 const apply=()=>{
  for(const [key] of columns){
   panel.querySelector(`[data-review-column="${key}"]`).hidden=!shown.has(key);
   panel.querySelectorAll(`[data-review-cell="${key}"]`).forEach(cell=>cell.hidden=!shown.has(key));
  }
  const empty=panel.querySelector('tbody td[colspan]');if(empty)empty.colSpan=shown.size+1;
  menu.querySelectorAll('input').forEach(box=>box.disabled=shown.size===1&&box.checked);
  s.visibleColumns=[...shown];
 };
 menu.querySelectorAll('input').forEach(box=>box.onchange=()=>{if(box.checked)shown.add(box.dataset.withdrawalColumn);else shown.delete(box.dataset.withdrawalColumn);apply();});
 menu.addEventListener('keydown',event=>{if(event.key==='Escape'){menu.open=false;menu.querySelector('summary').focus();}});
 // One document listener serves all renders; detached menus retain no handlers.
 if(!attachWithdrawalColumns.listening){
  document.addEventListener('click',event=>document.querySelectorAll('.withdrawal-columns[open]').forEach(open=>{if(!open.contains(event.target))open.open=false;}));
  attachWithdrawalColumns.listening=true;
 }
 apply();
}

function attachReviewCardView(columns,kind){
 const s=reviewStates[kind],panel=document.querySelector('.withdrawal-panel'),table=panel.querySelector('table');
 const labels=new Map(columns.map(([key,label])=>[key,label]));
 table.querySelectorAll('[data-review-cell]').forEach(cell=>{
  const empty=cell.innerHTML.trim()==='';
  const value=document.createElement('span');value.className='review-card-value';
  while(cell.firstChild)value.append(cell.firstChild);
  const label=document.createElement('span');label.className='review-card-title';label.textContent=labels.get(cell.dataset.reviewCell);
  cell.append(label,value);cell.classList.toggle('review-card-empty',empty);
 });
 const button=document.createElement('button');button.id='reviewViewToggle';button.title='切换';button.setAttribute('aria-label','切换卡片视图');
 const toolbar=panel.querySelector('.withdrawal-toolbar');toolbar.insertBefore(button,toolbar.querySelector('.withdrawal-columns'));
 const apply=()=>{
  table.classList.toggle('review-card-view',!!s.cardView);
  button.setAttribute('aria-pressed',String(!!s.cardView));
  button.innerHTML='<i class="glyphicon glyphicon-list-alt" aria-hidden="true"></i>';
 };
 button.onclick=()=>{s.cardView=!s.cardView;apply();};apply();
}

const reviewPageSizes=[10,15,20,25,50,'All'];
function reviewPageSize(){
 let value;try{const saved=localStorage.getItem('pagesize');value=saved==='All'?'All':Number(saved);}catch{}
 return reviewPageSizes.includes(value)?value:10;
}

function attachReviewPagination(kind,total,count){
 const s=reviewStates[kind],box=document.querySelector('.withdrawal-panel .pagination');
 const size=s.pageSize==='All'?Math.max(1,total):s.pageSize,pages=Math.max(1,Math.ceil(total/size));
 let numbers;
 if(pages<=7)numbers=Array.from({length:pages},(_,i)=>i+1);
 else if(s.page<=4)numbers=[1,2,3,4,5,pages];
 else if(s.page>=pages-3)numbers=[1,...Array.from({length:5},(_,i)=>pages-4+i)];
 else numbers=[1,s.page-1,s.page,s.page+1,pages];
 box.hidden=total===0;
 box.innerHTML=`<div class="review-page-info"><span>显示第 ${total?(s.page-1)*size+1:0} 到第 ${total?(s.page-1)*size+count:0} 条记录，总共 ${total} 条记录</span><span class="review-page-size" ${total<=10?'hidden':''}>每页显示 <details id="reviewPageSizeMenu"><summary aria-label="每页条数">${s.pageSize} <span class="caret"></span></summary><div>${reviewPageSizes.map(n=>`<button type="button" data-review-size="${n}" ${n===s.pageSize?'aria-current="true"':''}>${n}</button>`).join('')}</div></details> 条记录</span></div><nav aria-label="分页" ${pages===1?'hidden':''}><button id="reviewPrev" aria-label="上一页">上一页</button>${numbers.map((n,i)=>`${i&&n-numbers[i-1]>1?'<span class="review-page-gap">...</span>':''}<button data-review-page="${n}" ${n===s.page?'aria-current="page"':''}>${n}</button>`).join('')}<button id="reviewNext" aria-label="下一页">下一页</button><span class="review-page-jump"><input type="text" inputmode="numeric" aria-label="跳转页码"><button data-review-jump title="跳转">跳转</button></span></nav>`;
 const go=n=>{if(Number.isInteger(n)&&n>=1&&n<=pages&&n!==s.page){s.page=n;renderReviewPage(kind);}};
 box.querySelector('#reviewPrev').onclick=()=>go(s.page===1?pages:s.page-1);box.querySelector('#reviewNext').onclick=()=>go(s.page===pages?1:s.page+1);
 box.querySelectorAll('[data-review-page]').forEach(button=>button.onclick=()=>go(Number(button.dataset.reviewPage)));
 box.querySelectorAll('[data-review-size]').forEach(button=>button.onclick=()=>{
  s.pageSize=button.dataset.reviewSize==='All'?'All':Number(button.dataset.reviewSize);s.page=1;
  box.querySelector('details').open=false;
  try{localStorage.setItem('pagesize',String(s.pageSize));}catch{}
  renderReviewPage(kind);
 });
 box.querySelector('details').onkeydown=event=>{if(event.key==='Escape'){event.currentTarget.open=false;event.currentTarget.querySelector('summary').focus();}};
 const jump=()=>go(Number(box.querySelector('nav input').value));
 box.querySelector('[data-review-jump]').onclick=jump;
 box.querySelector('nav input').onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();jump();}};
}
document.addEventListener('click',event=>{const menu=document.querySelector('#reviewPageSizeMenu');if(menu&&!menu.contains(event.target))menu.open=false;});

function mountWithdrawalBlacklistActions(panel,s,refresh){
 const results=panel.querySelector('.game-user-results'),errorBox=panel.querySelector('[role=alert]'),selected=new Set();
 for(const [selector,icon] of [['[data-action=cards]','list-alt'],['[data-action=search]','search'],['.game-user-columns summary','th'],['.game-user-export summary','export']]){
  const control=panel.querySelector(selector);
  control.title=control.getAttribute('aria-label');
  control.innerHTML=`<i class="glyphicon glyphicon-${icon}" aria-hidden="true"></i>${control.tagName==='SUMMARY'?' <span class="caret"></span>':''}`;
 }
 let busy=false,closed=false;
 const sync=()=>{
  const boxes=[...results.querySelectorAll('[data-blacklist-select]')],all=results.querySelector('[data-blacklist-all]');
  boxes.forEach(box=>{box.checked=selected.has(Number(box.dataset.blacklistSelect));box.disabled=busy;});
  if(all){all.checked=boxes.length>0&&boxes.every(box=>box.checked);all.indeterminate=boxes.some(box=>box.checked)&&!all.checked;all.disabled=busy||!boxes.length;}
  results.querySelectorAll('[data-blacklist-toggle]').forEach(button=>button.disabled=busy);
 };
 results.addEventListener('click',event=>{
  if(busy||results.hasAttribute('aria-busy')||event.target.closest('button,a,input,select,textarea,label,summary'))return;
  event.target.closest('tr,article')?.querySelector('[data-blacklist-select]')?.click();
 });
 return {
  loaded(){selected.clear();},
  selectedItems(){return s.items.filter(row=>selected.has(row.id));},
  paint(){
   const table=results.querySelector('table');
   if(table){
    table.tHead.rows[0].insertAdjacentHTML('afterbegin','<th><input type="checkbox" data-blacklist-all aria-label="全选本页黑名单"></th>');
    if(!s.items.length)table.tBodies[0].rows[0].cells[0].colSpan++;
   }
   const containers=table?[...table.tBodies[0].rows]:[...results.querySelectorAll('article')];
   s.items.forEach((row,index)=>containers[index].insertAdjacentHTML('afterbegin',`<${table?'td':'div'}><input type="checkbox" data-blacklist-select="${esc(row.id)}" aria-label="选择黑名单 ${esc(row.id)}"></${table?'td':'div'}>`));
   results.querySelector('[data-blacklist-all]')?.addEventListener('change',event=>{s.items.forEach(row=>event.target.checked?selected.add(row.id):selected.delete(row.id));sync();});
   results.querySelectorAll('[data-blacklist-select]').forEach(box=>box.onchange=()=>{box.checked?selected.add(Number(box.dataset.blacklistSelect)):selected.delete(Number(box.dataset.blacklistSelect));sync();});
   results.querySelectorAll('[data-blacklist-toggle]').forEach(button=>button.onclick=async()=>{
    if(busy||closed||results.hasAttribute('aria-busy'))return;
    busy=true;sync();errorBox.textContent='';const generation=s.generation;
    try{
     await api('/withdrawal-blacklist/'+button.dataset.blacklistToggle,{method:'PATCH',body:JSON.stringify({status:button.getAttribute('aria-checked')==='true'?0:1})});
     if(!closed&&generation===s.generation)await refresh();
    }catch(error){if(!closed&&generation===s.generation)errorBox.textContent=error.message;}
    finally{busy=false;if(!closed)sync();}
   });
   sync();
  },
  destroy(){closed=true;selected.clear();}
 };
}

function openWithdrawalBlacklist(){
 document.querySelector('.withdrawal-blacklist-dialog')?.close();
 const dialog=document.createElement('dialog');dialog.className='withdrawal-blacklist-dialog';dialog.setAttribute('aria-label','黑名单');
 dialog.innerHTML='<header><span>黑名单</span><button type="button" data-blacklist-minimize aria-label="最小化" title="最小化"></button><button type="button" data-blacklist-maximize aria-label="最大化" title="最大化"></button><button type="button" data-blacklist-close aria-label="关闭" title="关闭"></button></header><main></main>';
 document.body.append(dialog);dialog.showModal();
 const tab={endpoint:'/withdrawal-blacklist',absolute:true,filtersExpanded:true,mountActions:mountWithdrawalBlacklistActions,
  columns:[['id','Id','sort'],['receive_name','收件人','search'],['receive_tel','联系方式','search'],['status','状态',{0:'禁用',1:'启用'}],['created_at','拉黑时间','date'],['updated_at','更新时间','date',false]],
  cell:(row,column,interactive)=>column[0]==='status'?(interactive?`<button class="blacklist-toggle" data-blacklist-toggle="${esc(row.id)}" role="switch" aria-label="黑名单状态" aria-checked="${Number(row.status)===1}" title="点击切换"><i class="shell-icon" aria-hidden="true">&#xf205;</i></button>`:esc(row.status===1?'启用':'禁用')):gameUserCell(row,column,interactive)};
 const controller=mountGameUserTable(dialog.querySelector('main'),null,tab);
 const close=()=>dialog.close(),maximize=dialog.querySelector('[data-blacklist-maximize]');
 const updateWindow=()=>{const label=dialog.classList.contains('expanded')||dialog.classList.contains('minimized')?'还原':'最大化';maximize.setAttribute('aria-label',label);maximize.title=label;};
 dialog.querySelector('[data-blacklist-close]').onclick=close;
 dialog.querySelector('[data-blacklist-minimize]').onclick=()=>{
  for(const [input,picker] of reviewDateBindings)if(dialog.contains(input))picker.hide();
  dialog.close();dialog.classList.add('minimized');dialog.show();updateWindow();
 };
 maximize.onclick=()=>{
  if(dialog.classList.contains('minimized')){dialog.close();dialog.classList.remove('minimized');dialog.showModal();}
  else dialog.classList.toggle('expanded');
  updateWindow();
 };
 const header=dialog.querySelector('header');let drag=null,shiftX=0,shiftY=0;
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
 dialog.addEventListener('click',event=>dialog.querySelectorAll('details[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;}));
 dialog.addEventListener('keydown',event=>{
  if(event.key!=='Escape')return;
  const menus=[...dialog.querySelectorAll('details[open]')],pickers=[...reviewDateBindings].filter(([input,picker])=>dialog.contains(input)&&picker.isShowing);
  if(menus.length||pickers.length){event.preventDefault();menus.forEach(menu=>menu.open=false);pickers.forEach(([,picker])=>picker.hide());}
 });
 window.addEventListener('hashchange',close);
 dialog.addEventListener('close',()=>{if(dialog.open)return;controller.destroy();drag=null;window.removeEventListener('hashchange',close);dialog.remove();});
 controller.refresh();
}
