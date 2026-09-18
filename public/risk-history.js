const riskHistoryState={tableState:null,controller:null};
const riskHistoryColumns=[['id','Id'],['user_id','会员ID','search'],['username','用户账号','search'],
 ['parent_id','上级Id','search',false],['game_name','游戏名称'],['agent_name','代理商名称',null,false],
 ['tagcode','标签','search'],['tags','标签名'],['hardware_main_id','硬件主ID','search'],['ip','ip','search'],
 ['action','行为'],['risk_score','风险分数'],['risk_level','风险等级'],['created_at','创建时间','date']];
const riskHistorySearchFields=new Set(['user_id','username','parent_id','game_name','agent_name','hardware_main_id','ip']);

function riskHistoryCell(row,column,interactive){
 const key=column[0],value=row[key];if(value==null)return '';
 const text=key==='created_at'?profileLogTime(value):value,html=esc(text);
 return interactive&&riskHistorySearchFields.has(key)?`<button class="game-user-cell-search" data-risk-search="${key}" data-value="${esc(value)}" title="点击搜索 ${esc(text)}">${html}</button>`:html;
}
function riskHistoryExportCell(row,column){
 const text=riskHistoryCell(row,column,false);
 return riskHistorySearchFields.has(column[0])&&row[column[0]]!=null?`<a>${text}</a>`:text;
}
function mountRiskHistoryActions(panel,s){
 const form=panel.querySelector('form'),results=panel.querySelector('.game-user-results');
 panel.querySelector('section').classList.add('risk-history-panel');form.id='riskHistoryFilters';form.hidden=false;
 panel.querySelector('[role=alert]').id='riskHistoryError';results.id='riskHistoryTable';
 panel.querySelector('.game-user-pagination').id='riskHistoryPagination';
 panel.querySelector('[data-action=refresh]').id='riskHistoryRefresh';panel.querySelector('[data-action=search]').id='riskHistorySearch';
 attachFilterLookups(form,s.filters);form.querySelectorAll('.sp_container').forEach(container=>container.style.width='');
 const nameFields={game_name:'game_name_exact',agent_name:'agent_name'};
 const lookup=key=>form.querySelector(`[data-filter-lookup="${key==='game_name'?'game_id':'agent_id'}"]`);
 const setName=(key,value)=>{
  const input=lookup(key),entry=memberLookupEntries.find(item=>item.input===input),plugin=window.jQuery(input).data('selectPageObject');
  if(entry)entry.responseVersion++;
  plugin.afterInit(plugin,{id:value,name:value});plugin.elem.hidden.attr('name',nameFields[key]);
 };
 for(const [key,field] of Object.entries(nameFields))if(s.filters[field])setName(key,s.filters[field]);
 for(const [selector,icon] of [['[data-action=cards]','list-alt'],['[data-action=search]','search'],['.game-user-columns summary','th'],['.game-user-export summary','export']]){
  const control=panel.querySelector(selector);control.title=control.getAttribute('aria-label');
  control.innerHTML=`<i class="glyphicon glyphicon-${icon}" aria-hidden="true"></i>${control.tagName==='SUMMARY'?' <span class="caret"></span>':''}`;
 }
 results.addEventListener('click',event=>{
  const button=event.target.closest('[data-risk-search]');if(!button||results.hasAttribute('aria-busy'))return;
  const key=button.dataset.riskSearch,value=button.dataset.value;
  if(nameFields[key])setName(key,value);else form.elements.namedItem(key).value=value;
  form.hidden=false;s.filtersExpanded=true;panel.querySelector('[data-action=search]').setAttribute('aria-expanded','true');form.requestSubmit();
 });
 return {
  paint(){results.querySelectorAll('.game-user-cards article>div').forEach(row=>{
   const title=row.querySelector('strong');title.textContent=title.textContent.slice(0,-1);row.hidden=row.querySelector('span').textContent==='';
  });},
  reset(){for(const key of Object.keys(nameFields))window.jQuery(lookup(key)).selectPageClear();}
 };
}
async function renderRiskHistory(){
 if(state.view!=='risk-history')return;riskHistoryState.controller?.destroy();
 $('#content').innerHTML='<div id="riskHistoryHost"></div>';
 const tab={endpoint:'/risk/history',absolute:true,state:riskHistoryState.tableState,filtersExpanded:true,
  columns:riskHistoryColumns,cell:riskHistoryCell,mountActions:mountRiskHistoryActions,exportSkipFirst:true,
  exportCell:riskHistoryExportCell,exportFileName:()=>'export_'+new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date()),
  filterColumns:[['user_id','会员ID','search'],['username','用户账号','search'],['parent_id','上级Id','search'],['game_id','游戏名称','search'],
   ['agent_id','代理商名称','search'],['tagcode','标签','search'],['hardware_main_id','硬件主ID','search'],['ip','ip','search'],['created_at','创建时间','date']]};
 riskHistoryState.controller=mountGameUserTable($('#riskHistoryHost'),null,tab);riskHistoryState.tableState=riskHistoryState.controller.state;
 await riskHistoryState.controller.refresh();
}
window.addEventListener('hashchange',()=>{if(!/^#risk-history(?:$|[?&])/.test(location.hash)){riskHistoryState.controller?.destroy();riskHistoryState.controller=null;}});
