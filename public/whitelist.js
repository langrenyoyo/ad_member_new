const whitelistState={tableState:null,controller:null};
const whitelistColumns=[['id','Id'],['image_url','头像','image',false],['username','账号','search'],
 ['parent_id','上级Id','search',false],['parent_username','上级账号',null,false],['parent_name','上级昵称'],['game_name','游戏名称'],
 ['agent_name','代理商名称',null,false],['name','昵称','search',false],['coin_user','累计金币收益','sort'],['coin_user_month','本月金币收益'],
 ['coin_user_day','今日金币收益'],['coin','可用金币','sort'],['freeze_coin','冻结金币','sort'],
 ['game_addiction_enable','达标',{0:'否',1:'是'},false],['game_addiction_time','达标时间','sort',false],['exchange_enable','兑换',null,false],
 ['is_white','白名单'],['status','状态',{0:'禁用',1:'启用'}],['last_login_device_id','最后登陆设备号',null,false],['last_login_ip','最后登陆IP',null,false],
 ['last_login_time','最后登陆时间','datetime',false],['created_at','创建时间','date'],['member_actions','操作']];

function whitelistCell(row,column,interactive){
 const key=column[0],value=row[key];
 if(key==='member_actions')return interactive?`${memberBehaviorButtons(row.id,row.game_id)}<button class="game-member-coins" data-white-coins="${esc(row.id)}">修改金币</button> <button class="game-member-edit" data-white-edit="${esc(row.id)}" title="编辑" aria-label="编辑"><i class="shell-icon" aria-hidden="true">&#xf040;</i></button>`:'';
 if(value==null)return '';
 if(['is_white','status','exchange_enable'].includes(key))return interactive?`<button class="white-toggle" data-white-toggle="${key}" data-white-id="${esc(row.id)}" role="switch" aria-label="${esc(column[1])}" aria-checked="${Number(value)===1}" title="点击切换"><i class="shell-icon" aria-hidden="true">&#xf205;</i></button>`:esc(key==='status'?(Number(value)===1?'启用':'禁用'):(Number(value)===1?'是':'否'));
 if(key==='game_addiction_enable')return interactive?`<span class="white-label ${Number(value)===1?'success':'info'}">${Number(value)===1?'是':'否'}</span>`:esc(Number(value)===1?'是':'否');
 if(column[2]==='date'||column[2]==='datetime')return esc(profileLogTime(value));
 if(key==='image_url')return gameUserCell(row,column,interactive);
 if(interactive&&['username','parent_id','game_name','agent_name','name'].includes(key))return `<button class="game-user-cell-search" data-white-search="${key}" data-value="${esc(value)}" title="点击搜索 ${esc(value)}">${esc(value)}</button>`;
 if(interactive&&key==='last_login_ip')return `<a href="#" class="white-last-login-ip" data-white-noop="1">${esc(value)}</a>`;
 return esc(value);
}
function whitelistExportCell(row,column){
 const key=column[0],value=row[key],text=whitelistCell(row,column,false);
 if(key==='image_url')return '';
 if(value==null)return text;
 if(['is_white','status','exchange_enable'].includes(key))return `<a><i class="fa fa-toggle-on text-success text-success ${Number(value)===1?'':'fa-flip-horizontal text-gray'} fa-2x"></i></a>`;
 if(key==='game_addiction_enable')return `<a><span class="label label-${Number(value)===1?'success':'info'}">${text}</span></a>`;
 return ['username','parent_id','game_name','agent_name','name','last_login_ip'].includes(key)?`<a>${text}</a>`:text;
}

function mountWhitelistActions(panel,s,refresh,{gameLookup=true,selectionLabel='全选本页白名单'}={}){
 const form=panel.querySelector('form'),results=panel.querySelector('.game-user-results'),errorBox=panel.querySelector('[role=alert]');
 panel.querySelector('section').classList.add('whitelist-panel');form.id='whitelistFilters';results.id='whitelistTable';errorBox.id='whitelistError';
 panel.querySelector('.game-user-pagination').id='whitelistPagination';panel.querySelector('[data-action=refresh]').id='whitelistRefresh';
 const search=panel.querySelector('[data-action=search]');search.id='whitelistSearch';
 form.hidden=false;attachFilterLookups(form,s.filters);form.querySelectorAll('.sp_container').forEach(container=>container.style.width='');form.hidden=!s.filtersExpanded;
 const lookup=key=>form.querySelector(`[data-filter-lookup="${key==='game_name'?'game_id':'agent_id'}"]`);
 const nameFields=gameLookup?['game_name','agent_name']:['agent_name'];
 const setName=(key,value)=>{
  const input=lookup(key),entry=memberLookupEntries.find(item=>item.input===input),plugin=window.jQuery(input).data('selectPageObject');
  if(entry)entry.responseVersion++;plugin.afterInit(plugin,{id:value,name:value});plugin.elem.hidden.attr('name',key);
 };
 for(const key of nameFields)if(s.filters[key])setName(key,s.filters[key]);
 for(const [selector,icon] of [['[data-action=cards]','list-alt'],['[data-action=search]','search'],['.game-user-columns summary','th'],['.game-user-export summary','export']]){
  const control=panel.querySelector(selector);control.title=control.getAttribute('aria-label');
  control.innerHTML=`<i class="glyphicon glyphicon-${icon}" aria-hidden="true"></i>${control.tagName==='SUMMARY'?' <span class="caret"></span>':''}`;
 }
 const selected=new Set();let busy=false,closed=false,editor;
 const sync=()=>{
  const boxes=[...results.querySelectorAll('[data-white-select]')],all=results.querySelector('[data-white-all]');
  boxes.forEach(box=>{box.checked=selected.has(Number(box.dataset.whiteSelect));box.disabled=busy;});
  if(all){all.checked=boxes.length>0&&boxes.every(box=>box.checked);all.indeterminate=boxes.some(box=>box.checked)&&!all.checked;all.disabled=busy||!boxes.length;}
  results.querySelectorAll('[data-white-toggle],[data-white-edit],[data-white-coins]').forEach(button=>button.disabled=busy);
 };
 const current=generation=>!closed&&panel.isConnected&&generation===s.generation;
 const edit=row=>{
  if(busy||closed)return;editor?.close();errorBox.textContent='';const generation=s.generation;
  editor=openGameMemberEditor(row.id,row.game_id,null,async()=>{if(current(generation))await refresh();},error=>{if(current(generation))errorBox.textContent=error.message;});
 };
 results.addEventListener('click',async event=>{
  if(busy||closed||results.hasAttribute('aria-busy'))return;
  if(event.target.closest('[data-white-noop]')){event.preventDefault();return;}
  const button=event.target.closest('[data-white-search],[data-white-toggle],[data-white-edit],[data-white-coins]');
  if(!button){if(!event.target.closest('button,a,input,select,textarea,label,summary'))event.target.closest('tr,article')?.querySelector('[data-white-select]')?.click();return;}
  if(button.dataset.whiteSearch){
   const key=button.dataset.whiteSearch;if(key==='game_name'&&!gameLookup){button.closest('tr,article')?.querySelector('[data-white-select]')?.click();return;}
   if(nameFields.includes(key))setName(key,button.dataset.value);else form.elements.namedItem(key).value=button.dataset.value;
   form.hidden=false;s.filtersExpanded=true;search.setAttribute('aria-expanded','true');form.requestSubmit();return;
  }
  const id=Number(button.dataset.whiteId||button.dataset.whiteEdit||button.dataset.whiteCoins),row=s.items.find(item=>item.id===id);if(!row)return;
  if(button.hasAttribute('data-white-edit')){edit(row);return;}
  if(button.hasAttribute('data-white-coins')){editor?.close();openMemberCoinDialog(id);const dialog=document.querySelector('#memberCoinDialog');editor={close:()=>dialog?.close()};return;}
  busy=true;sync();errorBox.textContent='';const generation=s.generation;
  try{await api('/members/'+id,{method:'PATCH',body:JSON.stringify({[button.dataset.whiteToggle]:Number(row[button.dataset.whiteToggle])===1?0:1})});if(current(generation))await refresh();}
  catch(error){if(current(generation))errorBox.textContent=error.message;}
  finally{busy=false;if(!closed)sync();}
 });
 results.addEventListener('dblclick',event=>{
  if(busy||closed||results.hasAttribute('aria-busy')||event.target.closest('button,a,input,select,textarea,label,summary'))return;
  const button=event.target.closest('tr,article')?.querySelector('[data-white-edit]'),row=s.items.find(item=>String(item.id)===button?.dataset.whiteEdit);if(row)edit(row);
 });
 return {
  selectedItems(){return s.items.filter(row=>selected.has(row.id));},loaded(){selected.clear();},
  paint(){
   const table=results.querySelector('table'),containers=table?[...table.tBodies[0].rows]:[...results.querySelectorAll('article')];
   if(table){table.tHead.rows[0].insertAdjacentHTML('afterbegin',`<th><input type="checkbox" data-white-all aria-label="${esc(selectionLabel)}"></th>`);if(!s.items.length)table.tBodies[0].rows[0].cells[0].colSpan++;}
   if(!table)results.querySelectorAll('article>div').forEach(row=>{row.querySelector('strong').textContent=row.querySelector('strong').textContent.slice(0,-1);row.hidden=!row.querySelector('span').innerHTML;});
   s.items.forEach((row,index)=>containers[index].insertAdjacentHTML('afterbegin',`<${table?'td':'div'} class="white-selection"><input type="checkbox" data-white-select="${esc(row.id)}" aria-label="选择会员 ${esc(row.id)}"></${table?'td':'div'}>`));
   results.querySelectorAll('[data-white-select]').forEach(box=>box.onchange=()=>{box.checked?selected.add(Number(box.dataset.whiteSelect)):selected.delete(Number(box.dataset.whiteSelect));sync();});
   results.querySelector('[data-white-all]')?.addEventListener('change',event=>{s.items.forEach(row=>event.target.checked?selected.add(row.id):selected.delete(row.id));sync();});sync();
  },
  reset(){for(const key of nameFields)window.jQuery(lookup(key)).selectPageClear();},
  destroy(){closed=true;editor?.close();selected.clear();}
 };
}
async function renderWhitelist(){
 if(state.view!=='risk-whitelist')return;whitelistState.controller?.destroy();
 $('#content').innerHTML='<div id="whitelistHost"></div>';
 const tab={endpoint:'/risk/whitelist',absolute:true,state:whitelistState.tableState,columns:whitelistColumns,cell:whitelistCell,mountActions:mountWhitelistActions,
  filterColumns:[['username','账号','search'],['parent_id','上级Id','search'],['game_id','游戏名称','search'],['agent_id','代理商名称','search'],['name','昵称','search'],['status','状态',{0:'禁用',1:'启用'}],['created_at','创建时间','date']],
  exportCell:whitelistExportCell,exportXmlCell:cell=>cell.querySelector('a>i,a>.label')||cell.textContent,
  exportFileName:()=>'export_'+new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date())};
 whitelistState.controller=mountGameUserTable($('#whitelistHost'),null,tab);whitelistState.tableState=whitelistState.controller.state;
 await whitelistState.controller.refresh();
}
window.addEventListener('hashchange',()=>{if(!/^#risk-whitelist(?:$|[?&])/.test(location.hash)){whitelistState.controller?.destroy();whitelistState.controller=null;}});
