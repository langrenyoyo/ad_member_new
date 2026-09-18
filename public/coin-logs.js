const coinTypes={'10':'抽奖','30':'兑换','40':'分销','50':'签到','60':'VIP','70':'任务','80':'其它','100':'后台'};
const coinState={tableState:null,controller:null};
function coinDefaults(){return {game_ad_status:'0',created_range:adsDefaults().watched_range};}
const coinColumns=[['id','Id'],['user_id','会员ID','search'],['username','用户账号','search'],['game_name','游戏名称'],
 ['game_ad_status','广告状态',{0:'正常',1:'封禁'},false],['agent_name','代理商名称'],['coin_before','金币变动前','sort'],
 ['coin','金币变动','sort'],['coin_after','金币变动后','sort'],['type','类型',coinTypes],['remark','备注','search'],['created_at','创建时间','date']];
function coinLabelColor(key,value){return key==='game_ad_status'?(Number(value)===0?'success':'danger'):({10:'success',30:'warning',40:'danger',50:'info',60:'primary',70:'success',100:'info'})[value]||'primary';}

function coinCell(row,column,interactive){
 const key=column[0],value=row[key];if(value==null)return '';
 let text=key==='created_at'?profileLogTime(value):['coin_before','coin','coin_after'].includes(key)?Number(value):value;
 if(key==='type')text=coinTypes[value]||'';
 if(key==='game_ad_status')text=({0:'正常',1:'封禁'})[value]||'';
 let html=esc(text);
 if(!interactive)return html;
 if(key==='type'||key==='game_ad_status'){
  const color=coinLabelColor(key,value);
  html=`<span class="coin-label ${color}">${html}</span>`;
 }
 return ['user_id','username','game_name','agent_name','type','game_ad_status'].includes(key)?`<button class="game-user-cell-search" data-coin-search="${key}" data-value="${esc(value)}" title="点击搜索 ${esc(text)}">${html}</button>`:html;
}

function coinExportCell(row,column){
 const key=column[0],html=coinCell(row,column,false);
 if(['type','game_ad_status'].includes(key)&&row[key]!=null)return `<a><span class="label label-${coinLabelColor(key,row[key])}">${html}</span></a>`;
 return ['user_id','username','game_name','agent_name'].includes(key)&&row[key]!=null?`<a>${html}</a>`:html;
}

function mountCoinActions(panel,s){
 const section=panel.querySelector('section'),form=panel.querySelector('form');
 section.classList.add('coin-panel');form.id='coinFilters';form.hidden=false;
 panel.querySelector('[role=alert]').id='coinError';
 panel.querySelector('.game-user-results').id='coinTable';
 panel.querySelector('.game-user-pagination').id='coinPagination';
 const refresh=panel.querySelector('[data-action=refresh]');refresh.id='coinRefresh';refresh.title='刷新';
 refresh.insertAdjacentHTML('afterend','<span id="coinSummary">金币变动：<span>-</span></span>');
 attachFilterLookups(form,s.filters);
 form.querySelectorAll('.sp_container').forEach(container=>container.style.width='');
 const nameField={game_name:'game_name_exact',agent_name:'agent_name'};
 const lookupFor=key=>form.querySelector(`[data-filter-lookup="${key==='game_name'?'game_id':'agent_id'}"]`);
 const setName=(key,value)=>{
  const input=lookupFor(key),entry=memberLookupEntries.find(item=>item.input===input),plugin=window.jQuery(input).data('selectPageObject');
  if(entry)entry.responseVersion++;
  plugin.afterInit(plugin,{id:value,name:value});plugin.elem.hidden.attr('name',nameField[key]);
 };
 for(const [key,field] of Object.entries(nameField))if(s.filters[field])setName(key,s.filters[field]);
 for(const [selector,icon] of [['[data-action=cards]','list-alt'],['[data-action=search]','search'],['.game-user-columns summary','th'],['.game-user-export summary','export']]){
  const control=panel.querySelector(selector);control.title=control.getAttribute('aria-label');
  control.innerHTML=`<i class="glyphicon glyphicon-${icon}" aria-hidden="true"></i>${control.tagName==='SUMMARY'?' <span class="caret"></span>':''}`;
 }
 panel.querySelector('.game-user-results').addEventListener('click',event=>{
  const button=event.target.closest('[data-coin-search]');if(!button||panel.querySelector('.game-user-results').hasAttribute('aria-busy'))return;
  const key=button.dataset.coinSearch,value=button.dataset.value;
  if(nameField[key])setName(key,value);else form.elements.namedItem(key).value=value;
  form.hidden=false;panel.querySelector('[data-action=search]').setAttribute('aria-expanded','true');form.requestSubmit();
 });
 return {
  paint(){panel.querySelectorAll('.game-user-cards article>div').forEach(row=>{
   const title=row.querySelector('strong');title.textContent=title.textContent.slice(0,-1);row.hidden=row.querySelector('span').textContent==='';
  });},
  reset(){for(const key of Object.keys(nameField))window.jQuery(lookupFor(key)).selectPageClear();}
 };
}

async function renderCoinLogs(){
 if(!['coin-logs','profit'].includes(state.view))return;
 coinState.controller?.destroy();
 $('#content').innerHTML='<div id="coinHost"></div>';
 const tab={endpoint:'/coin-logs',absolute:true,state:coinState.tableState,initialFilters:coinDefaults(),resetFilters:coinDefaults,filtersExpanded:true,
  columns:coinColumns,cell:coinCell,mountActions:mountCoinActions,exportSkipFirst:true,
  exportCell:coinExportCell,exportXmlCell:cell=>cell.querySelector('a>.label')||cell.textContent,
  exportFileName:()=>'export_'+new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date()),
  filterColumns:[['user_id','会员ID','search'],['username','用户账号','search'],['game_id','游戏名称','search'],['game_ad_status','广告状态',{0:'正常',1:'封禁'}],
   ['agent_id','代理商名称','search'],['type','类型',coinTypes],['remark','备注','search'],['created_at','创建时间','date']],
  onLoad(data,panel){panel.querySelector('#coinSummary span').textContent=data.summary?.change??'-';}};
 coinState.controller=mountGameUserTable($('#coinHost'),null,tab);coinState.tableState=coinState.controller.state;
 await coinState.controller.refresh();
}
window.addEventListener('hashchange',()=>{
 if(!/^#(?:coin-logs|profit)(?:$|[?&])/.test(location.hash)){coinState.controller?.destroy();coinState.controller=null;}
});
