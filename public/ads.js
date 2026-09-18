function adsDefaults(){const day=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());return {is_fu:'0',watched_range:`${day} 00:00:00 - ${day} 23:59:59`}}
const adsPageSizes=[10,15,20,25,50,'All'];
const adsSortFields={ecpm:'pre_ecpm',coin:'estimate_income',ad_network_platform_name:'ad_network_platform_name',watched_at:'create_time',request_id:'request_id'};
function adsHeader([key,label]){
 const field=adsSortFields[key];if(!field)return esc(label);
 const active=adsState.sort===field;
 return `<button type="button" class="ads-sort" data-ads-sort="${field}">${esc(label)}<span aria-hidden="true">${active?(adsState.order==='asc'?'▲':'▼'):'▴▾'}</span></button>`;
}
function attachAdsSorting(){
 document.querySelectorAll('[data-ads-sort]').forEach(button=>{
  button.closest('th').setAttribute('aria-sort',button.dataset.adsSort===adsState.sort?(adsState.order==='asc'?'ascending':'descending'):'none');
  button.onclick=()=>{const field=button.dataset.adsSort;adsState.order=adsState.sort===field&&adsState.order==='desc'?'asc':'desc';adsState.sort=field;adsState.page=1;loadAdsData();};
 });
}
function showAdsLoadError(error){
 const box=$('#adsError');if(!box)return;
 const retry=document.createElement('button');retry.id='adsRetry';retry.type='button';retry.textContent='重试';
 retry.onclick=()=>{retry.disabled=true;loadAdsData();};
 box.replaceChildren(document.createTextNode(error.message+' '),retry);
}
function adsPageSize(){try{const saved=localStorage.getItem('pagesize'),size=saved==='All'?'All':Number(saved);return adsPageSizes.includes(size)?size:10;}catch{return 10;}}
const adsState={page:1,size:adsPageSize(),filters:adsDefaults(),visible:new Set(),generation:0};
function renderAdsPagination(total,count){
 const panel=$('#adsPagination'),s=adsState,size=s.size==='All'?Math.max(1,total):s.size,last=Math.max(1,Math.ceil(total/size));
 panel.style.display=total?'flex':'none';
 let pages;
 if(last<=7)pages=Array.from({length:last},(_,i)=>i+1);
 else if(s.page<=4)pages=[1,2,3,4,5,last];
 else if(s.page>=last-3)pages=[1,...Array.from({length:5},(_,i)=>last-4+i)];
 else pages=[1,s.page-1,s.page,s.page+1,last];
 panel.innerHTML=`<div class="ads-pagination-info"><span>显示第 ${(s.page-1)*size+1} 到第 ${(s.page-1)*size+count} 条记录，总共 ${total} 条记录</span><span class="ads-page-size" ${total<=10?'hidden':''}>每页显示 <details id="adsPageSizeMenu"><summary aria-label="每页记录数">${s.size} <span class="caret"></span></summary><div>${adsPageSizes.map(n=>`<button type="button" data-ads-size="${n}" ${n===s.size?'aria-current="true"':''}>${n}</button>`).join('')}</div></details> 条记录</span></div><nav aria-label="广告分页" ${last===1?'hidden':''}><button data-ads-page="${s.page===1?last:s.page-1}" aria-label="上一页">上一页</button>${pages.map((n,i)=>`${i&&n>pages[i-1]+1?'<span class="ads-page-gap">...</span>':''}<button data-ads-page="${n}" ${n===s.page?'aria-current="page"':''}>${n}</button>`).join('')}<button data-ads-page="${s.page===last?1:s.page+1}" aria-label="下一页">下一页</button><span class="ads-page-jump"><input type="text" inputmode="numeric" aria-label="跳转页码"><button data-ads-jump title="跳转">跳转</button></span></nav>`;
 const move=n=>{if(Number.isInteger(n)&&n>=1&&n<=last&&n!==s.page){s.page=n;loadAdsData();}};
 panel.querySelectorAll('[data-ads-page]').forEach(b=>b.onclick=()=>move(Number(b.dataset.adsPage)));
 panel.querySelectorAll('[data-ads-size]').forEach(button=>button.onclick=()=>{s.size=button.dataset.adsSize==='All'?'All':Number(button.dataset.adsSize);s.page=1;panel.querySelector('details').open=false;try{localStorage.setItem('pagesize',String(s.size));}catch{}loadAdsData();});
 panel.querySelector('details').onkeydown=event=>{if(event.key==='Escape'){event.currentTarget.open=false;event.currentTarget.querySelector('summary').focus();}};
 const jump=()=>move(Number(panel.querySelector('input').value));
 panel.querySelector('[data-ads-jump]').onclick=jump;
 panel.querySelector('input').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();jump();}};
}
const adCols=[['id','Id'],['parent_id','上级Id'],['parent_payment_name','上级支付宝姓名'],['user_id','会员ID'],['user_account','用户账号'],['receive_name','支付宝姓名'],['game_name','游戏名称'],['agent_name','代理商名称'],['ecpm','ECPM'],['coin','金币'],['ad_network_platform_name','广告平台'],['is_lottery','抽奖'],['is_rw','任务'],['reward_type','奖励类型'],['ad_type','广告类型'],['sub_ad_type','副广类型'],['status','状态'],['watched_at','观看时间'],['ad_code','广告代码位'],['request_id','广告request_id'],['trans_id','交易trans_id']];
if(!adsState.visible.size)adCols.forEach(([key])=>{if(key!=='agent_name')adsState.visible.add(key)});
function attachAdsTools(){
 const tools=document.querySelector('.ads-tools'),filters=document.querySelector('#adsFilters'); if(!tools||!filters)return;
 const [listButton,columnButton,exportButton,searchButton]=tools.querySelectorAll(':scope>button');
 listButton.id='adsViewToggle'; columnButton.id='adsColumnsToggle'; searchButton.id='adsSearchToggle';
 exportButton.id='adsExportToggle';
 for(const [button,icon,label,caret] of [[listButton,'list-alt','切换',false],[columnButton,'th','列设置',true],[exportButton,'export','导出数据',true],[searchButton,'search','普通搜索',false]]){
  button.innerHTML=`<i class="glyphicon glyphicon-${icon}" aria-hidden="true"></i>${caret?' <span class="caret"></span>':''}`;
  button.title=label;button.setAttribute('aria-label',label);
 }
 $('#adsRefresh').innerHTML='<span class="shell-icon" aria-hidden="true">&#xf021;</span> ';
 $('#adsRefresh').setAttribute('aria-label','刷新');$('#adsRefresh').title='刷新';
 $('#adsDownload').hidden=true;
 searchButton.onclick=()=>{filters.hidden=!filters.hidden;searchButton.setAttribute('aria-expanded',String(!filters.hidden));};
 listButton.onclick=()=>{adsState.cards=!adsState.cards;applyAdsView();};
 listButton.title='切换';listButton.setAttribute('aria-label','切换卡片视图');
 tools.querySelector('.ads-column-menu')?.remove();
 let menu;
 columnButton.onclick=()=>{if(menu?.isConnected){menu.remove();menu=null;columnButton.setAttribute('aria-expanded','false');return;}closeAdsMenus();menu=document.createElement('div');menu.className='ads-column-menu';menu.innerHTML=adCols.map(([key,label])=>`<label><input type="checkbox" data-ads-column="${key}" ${adsState.visible.has(key)?'checked':''}>${label}</label>`).join('');columnButton.parentElement.append(menu);columnButton.setAttribute('aria-expanded','true');menu.querySelectorAll('input').forEach(box=>box.onchange=()=>{if(box.checked)adsState.visible.add(box.dataset.adsColumn);else if(adsState.visible.size>1)adsState.visible.delete(box.dataset.adsColumn);else{box.checked=true;return;}applyAdsColumns();menu.querySelectorAll('input').forEach(input=>input.disabled=adsState.visible.size===1&&input.checked);});};
 function applyAdsColumns(){document.querySelectorAll('#adsTable [data-ads-field]').forEach(cell=>{cell.hidden=!adsState.visible.has(cell.dataset.adsField);});const empty=document.querySelector('#adsTable .ads-empty td');if(empty)empty.colSpan=adsState.visible.size;}
 window.applyAdsColumns=applyAdsColumns;
 exportButton.disabled=!!adsState.exporting;
 exportButton.onclick=()=>{
  if(tools.querySelector('.ads-export-menu')){closeAdsMenus();return;}
  closeAdsMenus();const menu=document.createElement('div');menu.className='ads-export-menu';
  menu.innerHTML=[['json','JSON'],['xml','XML'],['csv','CSV'],['txt','TXT'],['doc','MS-Word'],['excel','MS-Excel']].map(([type,label])=>`<button type="button" data-ads-export="${type}">${label}</button>`).join('');
  tools.append(menu);exportButton.setAttribute('aria-expanded','true');
  menu.querySelectorAll('button').forEach(button=>button.onclick=()=>{closeAdsMenus();exportAdsTable(button.dataset.adsExport);});
 };
 applyAdsView();
}
function closeAdsMenus(){document.querySelectorAll('.ads-column-menu,.ads-export-menu').forEach(menu=>menu.remove());document.querySelectorAll('#adsColumnsToggle,#adsExportToggle').forEach(button=>button.setAttribute('aria-expanded','false'));}
document.addEventListener('click',event=>{if(!event.target.closest('.ads-tools'))closeAdsMenus();const sizes=$('#adsPageSizeMenu');if(sizes&&!sizes.contains(event.target))sizes.open=false;});
document.addEventListener('keydown',event=>{if(event.key==='Escape')closeAdsMenus();});
function applyAdsView(){
 const table=document.querySelector('#adsTable');if(!table)return;
 table.classList.toggle('ads-card-view',!!adsState.cards);
 document.querySelector('#adsViewToggle')?.setAttribute('aria-pressed',String(!!adsState.cards));
 table.querySelectorAll('tbody td[data-ads-field]').forEach(cell=>{
  if(cell.querySelector('.ads-card-title'))return;
  const title=document.createElement('span');title.className='ads-card-title';title.textContent=adCols.find(([key])=>key===cell.dataset.adsField)[1];
  const value=document.createElement('span');value.className='ads-card-value';while(cell.firstChild)value.append(cell.firstChild);cell.append(title,value);
 });
}
function attachAdsCellSearch(){
 document.querySelectorAll('#adsTable [data-ads-search]').forEach(link=>link.onclick=e=>{
  e.preventDefault();
  const field=link.dataset.adsSearch,value=link.dataset.value;
  if(field==='user_account')return;
  if(field==='game_name'||field==='agent_name'){
   const idField=field==='game_name'?'game_id':'agent_id';delete adsState.filters[idField];
   setAdsLookupName(field,value);
  }
  adsState.filters[field]=value;adsState.page=1;
  const input=$('#adsFilters')?.elements.namedItem(field);if(input)input.value=value;
  loadAdsData();
 });
}
function adsCell(row,key){
 if(['parent_id','user_id','user_account','game_name','agent_name'].includes(key)&&row[key]!=null)return `<a href="#" class="ads-cell-search" data-ads-search="${key}" data-value="${esc(row[key])}">${esc(row[key])}</a>`;
 if(key==='watched_at')return esc(profileLogTime(row.watched_at||row.created_at||(row.create_time?new Date(row.create_time*1000).toISOString():'')));
 if(key==='coin')return esc(row.estimate_income??row.coin??'');
 const fields={is_lottery:['is_lottery',{0:'否',1:'是'},{0:'info',1:'success'}],is_rw:['is_rw',{0:'否',1:'是'},{0:'info',1:'success'}],reward_type:['is_type',{0:'提升',1:'领取'},{0:'success',1:'warning'}],ad_type:['is_fu',{0:'激励',1:'副广'},{0:'success',1:'warning'}],sub_ad_type:['fu_type',{1:'开屏',2:'Banner',3:'插屏',4:'信息流'},{1:'info',2:'success',3:'warning',4:'danger'}],status:['is_look',{0:'失败',1:'成功'},{0:'info',1:'success'}]};
 if(fields[key]){const [field,labels,colors]=fields[key],value=row[field];if(value!=null&&labels[value]!=null){const badge=`<span class="label label-${colors[value]}">${labels[value]}</span>`;return ['ad_type','sub_ad_type','status'].includes(key)?`<a href="#" class="ads-cell-search" data-ads-search="${field}" data-value="${esc(value)}">${badge}</a>`:badge;}}
 return esc(row[key]??'');
}
async function exportAdsTable(type){
 if(adsState.exporting)return;
 const panel=$('.ads-panel'),query=adsParams(),fields=adCols.filter(([key])=>key!=='id'&&adsState.visible.has(key));
 let table;
 adsState.exporting=true;$('#adsExportToggle').disabled=true;$('#adsError').textContent='';
 try{
  await loadReviewExporter();if(!panel.isConnected)return;
  query.set('limit','200');query.set('offset','0');
  const first=await api('/ads?'+query),rows=[...first.items],total=first.total;
  while(rows.length<total){
   if(!panel.isConnected)return;
   query.set('offset',String(rows.length));const next=await api('/ads?'+query);
   if(next.total!==total||!next.items.length)throw Error('数据已变化，请刷新后重新导出');
   rows.push(...next.items);
  }
  if(!panel.isConnected)return;
  if(rows.length!==total||new Set(rows.map(row=>row.id)).size!==rows.length)throw Error('数据已变化，请刷新后重新导出');
  table=document.createElement('table');table.className='review-export-table';
  table.innerHTML='<thead><tr>'+fields.map(([,label])=>`<th>${esc(label)}</th>`).join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+fields.map(([key])=>`<td>${adsCell(row,key)}</td>`).join('')+'</tr>').join('')+'</tbody>';
  table.querySelectorAll('td>a').forEach(link=>{if(!link.querySelector('.label')&&!Number.isFinite(Number(link.textContent)))link.replaceWith(document.createTextNode(link.textContent));});
  document.body.append(table);
  window.jQuery(table).tableExport({type,preventInjection:false,fileName:'export_'+new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date()),mso:{onMsoNumberFormat:cell=>!isNaN(window.jQuery(cell).text())?'\\@':''},onBeforeSaveToFile:(data,name,mime,charset)=>{
   if(!panel.isConnected)return false;
   if(type==='xml')data=serializeExportXml(table,cell=>cell.querySelector('a>.label')||cell.textContent);
   const url=URL.createObjectURL(new Blob([(type==='csv'||type==='txt'?'\ufeff':''),data],{type:mime+';charset='+charset})),link=document.createElement('a');
   link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);return false;
  }});
 }catch(error){if(panel.isConnected)panel.querySelector('#adsError').textContent=error.message;}
 finally{table?.remove();adsState.exporting=false;const button=$('#adsExportToggle');if(button)button.disabled=false;}
}
function adsParams(){const p=new URLSearchParams({limit:adsState.size==='All'?200:adsState.size,offset:adsState.size==='All'?0:(adsState.page-1)*adsState.size,sort:adsState.sort||'id',order:adsState.order||'desc'});for(const[k,v]of Object.entries(adsState.filters))if(v&&k!=='watched_range'&&k!=='time_preset')p.set(k,v);const r=adsState.filters.watched_range;if(r){const x=r.split(' - ');if(x.length===2){p.set('watched_from',new Date(x[0].replace(' ','T')+'+08:00').toISOString());p.set('watched_to',new Date(x[1].replace(' ','T')+'+08:00').toISOString())}}return p}
async function downloadAds(){const headers=state.token?{Authorization:'Bearer '+state.token}:{};const response=await fetch('/api/v1/ads/export?'+adsParams(),{headers});if(!response.ok){const body=await response.json().catch(()=>({}));throw Error(body.detail||('HTTP '+response.status));}const blob=await response.blob();const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='ads.csv';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),0)}
async function renderAds(){
 const f=adsState.filters;
 $('#content').innerHTML=`<section class="ads-panel"><form id="adsFilters" class="ads-filters">
  <label><span>上级Id</span><input name="parent_id" placeholder="上级Id"></label>
  <label><span>会员ID</span><input name="user_id" placeholder="会员ID"></label>
  <label><span>游戏名称</span><input name="game_id" id="adsGameLookup" data-ads-lookup="game_name" placeholder="游戏名称"></label>
  <label><span>代理商名称</span><input name="agent_id" id="adsAgentLookup" data-ads-lookup="agent_name" placeholder="代理商名称"></label>
  <label><span>金币</span><div class="ads-range"><input name="estimate_income_min" placeholder="金币"><i>-</i><input name="estimate_income_max" placeholder="金币"></div></label>
  <label><span>广告平台</span><input name="ad_platform" placeholder="广告平台"></label>
  <label><span>广告类型</span><select name="is_fu"><option value="">选择</option><option value="0">激励</option><option value="1">副广</option></select></label>
  <label><span>副广类型</span><select name="fu_type"><option value="">选择</option><option value="1">开屏</option><option value="2">Banner</option><option value="3">插屏</option><option value="4">信息流</option></select></label>
  <label><span>状态</span><select name="is_look"><option value="">选择</option><option value="0">失败</option><option value="1">成功</option></select></label>
  <label class="date-field"><span>观看时间</span><input id="watchedRange" name="watched_range" placeholder="YYYY-MM-DD 00:00:00 - YYYY-MM-DD 23:59:59"></label>
  <div class="ads-filter-actions"><button type="submit" class="ads-submit">提交</button><button type="reset">重置</button></div>
 </form><div class="ads-toolbar"><button id="adsRefresh">刷新</button><div id="adsSummary"></div><div class="ads-tools"><button type="button" title="列表视图"></button><button type="button" title="列设置"></button><button type="button" title="导出数据"></button><button type="button" title="搜索"></button></div><button id="adsDownload" type="button" hidden>导出</button></div><p id="adsError" role="alert"></p><div id="adsTable"></div><div id="adsPagination"></div></section>`;
 const form=$('#adsFilters');
 attachReviewDates(form,'#watchedRange',{applyLabel:'应用',monthNames:Array.from({length:12},(_,i)=>(i+1)+'月')});
 for(const [key,value] of Object.entries(f)){const field=form.elements.namedItem(key);if(field)field.value=value;}
 attachAdsLookups(form);
 form.onsubmit=e=>{e.preventDefault();adsState.filters=Object.fromEntries(new FormData(form));adsState.page=1;loadAdsData();};
 form.onreset=e=>{e.preventDefault();adsState.filters=adsDefaults();adsState.page=1;renderAds();};
 $('#adsRefresh').onclick=()=>{adsState.page=1;loadAdsData();};
 $('#adsDownload').onclick=()=>downloadAds().catch(error=>{const node=$('#adsError');if(node)node.textContent=error.message;});
 loadAdsData();
}
async function loadAdsData(){
 const generation=++adsState.generation,panel=$('#adsTable');
 try{
  const query=adsParams(),d=await api('/ads?'+query);
  if(adsState.size==='All'){
   while(d.items.length<d.total){
    if(generation!==adsState.generation||panel!==$('#adsTable')||state.view!=='ads')return;
    query.set('offset',String(d.items.length));const next=await api('/ads?'+query);
    if(next.total!==d.total||!next.items.length)throw Error('数据已变化，请刷新后重试');
    d.items.push(...next.items);
   }
   if(d.items.length!==d.total||new Set(d.items.map(row=>row.id)).size!==d.items.length)throw Error('数据已变化，请刷新后重试');
  }
  if(generation!==adsState.generation||panel!==$('#adsTable')||state.view!=='ads')return;
  const last=adsState.size==='All'?1:Math.max(1,Math.ceil(d.total/adsState.size));if(adsState.page>last){adsState.page=last;return loadAdsData();}
  $('#adsError').textContent='';
  $('#adsSummary').innerHTML=[['ECPM',d.summary?.ecpm,''],['金币',d.summary?.coin,''],['已提现',d.summary?.withdrawn,'元'],['提现中',d.summary?.pending_withdrawal,'元']].map(([label,value,unit])=>`<span>${label}：${esc(value||0)}${unit}</span>`).join('');
  $('#adsTable').innerHTML=`<div class="table-wrap"><table class="ads-table"><thead><tr>${adCols.map(c=>`<th data-ads-field="${c[0]}" ${adsState.visible.has(c[0])?'':'hidden'}>${adsHeader(c)}</th>`).join('')}</tr></thead><tbody>${d.items.map(r=>`<tr>${adCols.map(c=>`<td data-ads-field="${c[0]}" ${adsState.visible.has(c[0])?'':'hidden'}>${adsCell(r,c[0])}</td>`).join('')}</tr>`).join('')||`<tr class="ads-empty"><td colspan="${adCols.length}">没有找到匹配的记录</td></tr>`}</tbody></table></div>`;
  renderAdsPagination(d.total,d.items.length);attachAdsSorting();attachAdsCellSearch();attachAdsTools();if(window.applyAdsColumns)window.applyAdsColumns();
 }catch(e){if(generation!==adsState.generation||panel!==$('#adsTable')||state.view!=='ads')return;showAdsLoadError(e);}
}



