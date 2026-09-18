const gameUserTabs = [
 {id:'first',label:'抽奖列表',endpoint:'lottery-records',columns:[
  ['id','Id'],['user_id','会员ID','search'],['username','用户账号','search'],['game_name','游戏名称'],
  ['lottery_price','金币','sort'],['ecpm','ECPM'],['adn_name','类型','search'],['ip','公网IP','search'],
  ['network_status','内网',{0:'是',1:'否'}],['tag','是否风控'],['is_white','白名单',{0:'否',1:'是'}],
  ['status','状态',{0:'失败',1:'成功'}],['created_at','抽奖时间','date'],
  ['ad_network_rit_id','广告代码位'],['request_id','广告request_id'],['trans_id','交易trans_id']
 ]},
 {id:'second',label:'风控历史',endpoint:'/risk/history',absolute:true,columns:[
  ['id','Id'],['user_id','会员ID','search'],['username','用户账号','search'],['game_name','游戏名称'],
  ['ip','IP','search'],['network_status','内网',{0:'是',1:'否'}],['tags','标签','search'],['created_at','创建时间','date']
 ]},
 {id:'four',label:'用户列表',endpoint:'/members',absolute:true,columns:[
  ['id','Id'],['image_url','头像','image',false],['username','账号','search'],
  ['parent_id','上级Id','search',false],['parent_username','上级账号',null,false],['parent_name','上级昵称'],['game_name','游戏名称'],['name','昵称','search',false],
  ['coin_user','累计金币收益','sort'],['coin_user_month','本月金币收益'],['coin_user_day','今日金币收益'],
  ['coin','可用金币','sort'],['freeze_coin','冻结金币','sort'],['is_true','内部号',{0:'否',1:'是'}],
  ['game_addiction_enable','达标',{0:'否',1:'是'}],
  ['game_addiction_time','达标时间','date',false],
  ['exchange_enable','兑换',{0:'否',1:'是'},false,'toggle'],['is_white','白名单',{0:'否',1:'是'},true,'toggle'],['status','状态',{0:'禁用',1:'启用'},true,'toggle'],
  ['last_login_device_id','最后登陆设备号',null,false],['last_login_ip','最后登陆IP',null,false],['last_login_time','最后登陆时间','datetime',false],
  ['created_at','创建时间','date'],['member_actions','操作']
 ]},
 {id:'third',label:'提现记录',endpoint:'/withdrawals',absolute:true,columns:[
  ['id','Id'],['user_id','会员ID','search'],['username','账号','search'],
  ['parent_id','上级Id','search',false],['parent_username','上级账号',null,false],['parent_name','上级昵称'],['behavior','用户行为'],['game_name','游戏名称'],['good_name','商品名称','search'],
  ['exchange_value','金额','sort'],['receive_name','收件人','search'],['receive_tel','联系方式','search'],
  ['receive_address','收货地址',null,false],['delivery_name','快递名称',null,false],['delivery_no','快递单号',null,false],['remark','备注',null,false],
  ['is_true','内部号',{0:'否',1:'是'}],['status','状态',{0:'申请中',1:'审核通过',2:'审核失败',4:'审核失败'}],['reason','拒绝原因',null,false],
  ['check_status','作弊审查','check'],['created_at','申请时间','date'],['updated_at','更新时间','date',false]
 ]},
 {id:'five',label:'登陆历史',endpoint:'login-logs',columns:[
  ['id','Id'],['user_id','会员ID','search'],['username','用户账号','search'],['game_name','游戏名称'],
  ['device_id','设备号'],['ip','IP','search'],['created_at','登陆时间','date']
 ]},
 {id:'six',label:'每日活跃',endpoint:'daily-activity',columns:[['id','Id'],['game_name','游戏名称'],['num','日活','sort'],['date','时间','date']]},
 {id:'seven',label:'数据统计',endpoint:'statistics',stats:true,columns:[]}
];
gameUserTabs.sort((a,b)=>['first','second','third','four','five','six','seven'].indexOf(a.id)-['first','second','third','four','five','six','seven'].indexOf(b.id));

function gameUserCell(row, column, interactive=false) {
 const [key,,kind] = column, value = row[key];
 if(key==='behavior')return row.game_id?`<button class="game-member-behavior" data-member-behavior="single" data-member-id="${esc(row.user_id)}" data-game-id="${esc(row.game_id)}">单APP行为</button>`:'';
 if(key==='member_actions')return interactive?`${memberBehaviorButtons(row.id,row.game_id)}<button class="game-member-coins" data-member-coins="${esc(row.id)}">修改金币</button> <button class="game-member-edit" data-game-member-edit="${esc(row.id)}" aria-label="编辑" title="编辑"><i class="shell-icon" aria-hidden="true">&#xf040;</i></button>`:'';
 if(value == null) return '';
 if(key==='exchange_value')return esc(Number(value)/10)+'元';
 if(key==='game_addiction_time')return esc(value);
 if(kind === 'date'||kind==='datetime') return esc(profileLogTime(value));
 if(kind==='image')return interactive&&/^(https?:\/\/|\/)/i.test(value)?`<a href="${esc(value)}" target="_blank" rel="noopener"><img class="game-member-avatar" src="${esc(value)}" alt="头像"></a>`:esc(value);
 if(interactive&&column[4]==='toggle')return `<button class="game-member-toggle ${Number(value)===1?'enabled':''}" type="button" role="switch" aria-label="${esc(column[1])}" aria-checked="${Number(value)===1}" data-member-toggle="${key}" data-member-id="${esc(row.id)}"><i class="shell-icon" aria-hidden="true">&#xf205;</i></button>`;
 if(kind==='check')return esc(({1:'正常',2:'金币异常',3:'ecpm异常'})[value]??'');
 if(kind && typeof kind === 'object') {
  const label = kind[value];
  if(label == null) return '';
  const badge = `<span class="game-user-label value-${Number(value)} ${key==='network_status'&&Number(value)===0?'warning':''}">${esc(label)}</span>`;
  return interactive ? `<button class="game-user-cell-search game-user-label-search" data-search-field="${key}" data-search-value="${esc(String(value))}">${badge}</button>` : badge;
 }
 if(kind === 'search' && key !== 'adn_name') return `<button class="game-user-cell-search" data-search-field="${key}" data-search-value="${esc(String(value))}">${esc(value)}</button>`;
 return esc(value);
}

function gameUserQuery(filters, page, size, sort, order) {
 const query = new URLSearchParams({limit:size,offset:(page-1)*size,sort,order});
 for(const [key,value] of Object.entries(filters)) {
  if(value === '') continue;
  if(!['created_range','updated_range','date_range','game_addiction_range'].includes(key)) {query.set(key,value);continue;}
  const parts = value.split(' - ');
  if(parts.length !== 2 || parts.some(part=>!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(part))) throw Error('时间范围无效');
  const dates = parts.map(part=>new Date(part.replace(' ','T')+'+08:00'));
  if(dates.some(date=>Number.isNaN(date.getTime())) || dates[0]>dates[1]) throw Error('时间范围无效');
  // Date silently rolls invalid days into the next month; reject that normalization.
  if(dates.some((date,index)=>new Date(date.getTime()+8*3600000).toISOString().slice(0,19).replace('T',' ')!==parts[index])) throw Error('时间范围无效');
  if(key==='game_addiction_range'){query.set('game_addiction_time',value);continue;}
  if(key==='date_range'){query.set('date_from',parts[0].slice(0,10));query.set('date_to',parts[1].slice(0,10));}else{const prefix=key.replace('_range','');query.set(prefix+'_from',dates[0].toISOString());query.set(prefix+'_to',dates[1].toISOString());}
 }
 return query;
}

let gameMapReady;
async function loadGameMap(){
 if(!gameMapReady)gameMapReady=(async()=>{
  if(!echarts.getMap('china'))await loadReviewScript('/vendor/china-map.js');
  if(!echarts.getMap('china'))throw Error('地图加载失败');
 })().catch(error=>{gameMapReady=undefined;throw error;});
 return gameMapReady;
}

function mountGameStatistics(panel,gameId){
 let closed=false,request,generation=0;const charts=[];
 const dispose=()=>{observer.disconnect();charts.splice(0).forEach(chart=>chart.dispose());};
 const observer=new ResizeObserver(()=>charts.forEach(chart=>{if(panel.hidden)return;chart.resize();const key=chart.getDom().dataset.statChart,compact=chart.getWidth()<600;if(key==='region-map'){chart.setOption({series:[{label:{show:!compact}}]});return;}if(key==='region-bars')return;chart.setOption({title:{textStyle:{fontSize:compact?14:18}},legend:{type:compact?'scroll':'plain',top:compact?28:0,left:compact?0:'center',right:compact?0:'auto'},toolbox:{top:compact?52:0},grid:compact?{left:40,right:25,top:100,bottom:45}:key==='metrics'?{left:'10%',right:'10%',top:60,bottom:60}:{left:'left',top:'top',right:10,bottom:30}});}));
 async function refresh(){
  const version=++generation;request?.abort();request=new AbortController();dispose();panel.innerHTML='<section class="game-user-stats" aria-busy="true">加载中</section>';
  try{
   const data=await api(`/games/${gameId}/statistics`,{signal:request.signal});await loadStatisticsCharts();if(closed||version!==generation)return;await loadGameMap();if(closed||version!==generation)return;
   const money=[['total_income','总金额',true],['year_income','本年金额',true],['previous_month_income','上月金额',false],['month_income','本月金额',true],['yesterday_income','昨日金额',false]],update=data.update_date?`（更新日期${esc(data.update_date)}）`:'';
   const counters=[['total_members','总会员数','&#xf007;'],['today_new','今日新增','&#xf234;'],['today_login','今日登陆','&#xf0f0;']];
   panel.innerHTML=`<section class="game-user-stats"><div class="game-stat-cards">${money.map(([key,label,showDate])=>`<article><div>${label}${showDate?update:''}</div><strong>¥${Number(data[key]??0).toFixed(2)}</strong><span>预估收益API</span></article>`).join('')}</div><div class="game-stat-chart-panel"><div data-stat-chart="metrics"></div></div><div class="game-stat-counters">${counters.map(([key,label,icon])=>`<article><i class="shell-icon" aria-hidden="true">${icon}</i><div><strong>${esc(data[key]??0)}</strong><span>${label}</span></div></article>`).join('')}</div><div class="game-stat-region-grid"><div class="game-stat-chart-panel"><div data-stat-chart="region-map"></div></div><div class="game-stat-chart-panel"><div data-stat-chart="region-bars"></div></div></div><div class="game-stat-chart-panel"><div data-stat-chart="registrations"></div></div></section>`;
   panel.querySelector('[data-stat-chart="region-map"]').insertAdjacentHTML('afterend','<small class="game-map-attribution"><a href="https://github.com/echarts-maps/echarts-countries-js" target="_blank" rel="noopener">echarts-maps / pissang</a> · <a href="/vendor/china-map-LICENSE" target="_blank" rel="noopener">ODbL</a></small>');
   const metricRows=data.metric_series||data.metrics||[],registrationRows=data.registration_series||data.registrations||[];
   const specs=[['metrics',metricRows,[['income','预估收益API','line'],['clicks','点击量','line'],['coin','金币','bar'],['activity','日活','bar']]],['registrations',registrationRows,[['count','注册用户数','line']]]];
   for(const [key,rows,series] of specs){
    const element=panel.querySelector(`[data-stat-chart="${key}"]`),chart=echarts.init(element,'walden');charts.push(chart);
    chart.setOption({title:{text:key==='metrics'?'金额统计':''},tooltip:{trigger:'axis'},legend:{data:series.map(([,name])=>name)},toolbox:{show:key==='metrics',feature:{dataView:{show:true,readOnly:false},magicType:{show:true,type:['line','bar']},restore:{show:true},saveAsImage:{show:true}}},grid:{left:55,right:25,top:70,bottom:45},xAxis:{type:'category',boundaryGap:key==='metrics',data:rows.map(row=>row.date)},yAxis:{type:'value'},series:series.map(([field,name,type])=>({name,type,data:rows.map(row=>row[field]??null),...(key==='metrics'?{markPoint:{data:[{type:'max',name:'最大值'},{type:'min',name:'最小值'}]},markLine:{data:[{type:'average',name:'平均值'}]}}:{smooth:true,areaStyle:{},lineStyle:{width:1.5}})}))});observer.observe(element);
    if(key==='registrations')chart.setOption({color:['#18d1b1','#3fb1e3','#626c91','#a0a7e6','#c4ebad','#96dee8']});
   }
   const mapElement=panel.querySelector('[data-stat-chart="region-map"]'),map=echarts.init(mapElement,'macarons');charts.push(map);
   map.setOption({title:{text:'账号分布',left:'left'},tooltip:{trigger:'item',formatter:point=>{const row=point.data||{},shown=value=>value==null||!Number.isFinite(Number(value))?'':esc(value);return `${esc(row.name||point.name||'')} : ( ${shown(row.rate)}% )<br/>账号数量 : ${shown(row.value)}个<br/>累计收益 : ${shown(row.coin)}个<br/>`; }},visualMap:{min:0,max:Math.max(0,...(data.mapdata||[]).map(row=>Number(row.value)||0))||5,left:'left',top:'bottom',text:['高','低'],calculable:true,inRange:{color:['#f1f1f1','#ff5200']}},toolbox:{show:true,orient:'vertical',left:'right',top:'center',feature:{mark:{show:true},dataView:{show:true,readOnly:false},restore:{show:true},saveAsImage:{show:true}}},series:[{name:'账号分布',type:'map',mapType:'china',selectedMode:'single',roam:false,zoom:1.2,label:{show:true,color:'#990000'},data:data.mapdata||[]}]});observer.observe(mapElement);
   map.setOption({legend:{orient:'vertical',left:'left',data:[]},series:[{emphasis:{label:{show:true,color:'#323232'}}}]});
   const barElement=panel.querySelector('[data-stat-chart="region-bars"]'),bar=echarts.init(barElement,'walden');charts.push(bar);
   bar.setOption({title:{text:'账号分布',left:'center',bottom:'5%',textStyle:{fontSize:14}},tooltip:{trigger:'item'},grid:{left:'3%',right:'4%',bottom:'15%'},xAxis:{type:'value',boundaryGap:[0,0.01]},yAxis:{show:false,type:'category',data:data.mapdata1||[]},series:[{type:'bar',label:{show:true,formatter:'{b}'},data:data.mapdata2||[]}]});observer.observe(barElement);
  }catch(error){if(!closed&&version===generation&&error.name!=='AbortError'){dispose();panel.innerHTML='<section class="game-user-stats"><p role="alert"></p><button type="button">重试</button></section>';panel.querySelector('[role=alert]').textContent=error.message;panel.querySelector('button').onclick=refresh;}}
 }
 return {refresh,suspend(){generation++;request?.abort();dispose();},destroy(){closed=true;generation++;request?.abort();dispose();}};
}

function mountGameUserTable(panel, gameId, tab) {
 const tableApi=(path,options)=>api(path,options,tab.apiPrefix||'/api/v1');
 if(tab.stats)return mountGameStatistics(panel,gameId);
 if(tab.unavailable){panel.innerHTML='<section class="game-user-unavailable"><p>暂无只证的狫历史数据</p><small>为避免从必数据推错结果，页暂未生成统数据</small></section>';return {refresh:()=>{},destroy:()=>{}};}
 const allowedSizes=[10,15,20,25,50,'All'],saved=localStorage.getItem('pagesize'),savedSize=saved==='All'?'All':Number(saved);
 const s=tab.state||{page:1,size:allowedSizes.includes(savedSize)?savedSize:10,sort:'id',order:'desc',filters:{...(tab.initialFilters||{})},visible:new Set(tab.columns.filter(c=>c[3]!==false).map(c=>c[0])),cards:false,total:0,items:[],generation:0};
 let request,exportRequest,closed=false,exportBusy=false,displayedPage=1,displayedSize=s.size;
 const path=tab.absolute?tab.endpoint:`/games/${gameId}/${tab.endpoint}`,cell=tab.cell||gameUserCell;
 const scopedQuery=(filters,page,size,sort,order)=>{
  const query=gameUserQuery(filters,page,size,sort,order);
  for(const [field,parameter] of Object.entries(tab.filterAliases||{}))if(query.has(field)){query.set(parameter,query.get(field));query.delete(field);}
  if(tab.absolute&&gameId!==null)query.set('game_id',String(gameId));
  for(const [key,value] of Object.entries(tab.query||{}))query.set(key,String(value));
  return query;
 };
 panel.innerHTML=`<section class="ads-panel game-user-panel">
<form class="ads-filters" hidden>${(tab.filterColumns||tab.columns.filter(([, ,kind])=>kind==='search'||kind==='date'||(kind && typeof kind==='object'))).map(([key,label,kind])=>`<label><span>${label}</span>${typeof kind==='object'?`<select name="${key}"><option value="">选择</option>${Object.entries(kind).map(([value,text])=>`<option value="${value}">${text}</option>`).join('')}</select>`:`<input name="${kind==='date'?(tab.endpoint==='daily-activity'||key==='date'?'date_range':key==='updated_at'?'updated_range':key==='game_addiction_time'?'game_addiction_range':'created_range'):key}" ${key==='user_id'?'inputmode="numeric"':''} placeholder="${label}">`}</label>`).join('')}<div class="ads-filter-actions"><button class="ads-submit" type="submit">提交</button><button type="reset">重置</button></div></form>
  <div class="ads-toolbar"><button class="ads-refresh" data-action="refresh" aria-label="刷新"><i class="shell-icon" aria-hidden="true">&#xf021;</i></button><div class="game-user-table-tools">
   <button data-action="search" aria-label="筛选" aria-expanded="false"><i class="shell-icon" aria-hidden="true">&#xe003;</i></button>
   <button data-action="cards" aria-label="切换视图" aria-pressed="false"><i class="shell-icon" aria-hidden="true">&#xe032;</i></button>
   <details class="game-user-columns"><summary aria-label="显示列"><i class="shell-icon" aria-hidden="true">&#xe011;</i> ▾</summary><div>${tab.columns.map(([key,label])=>`<label><input type="checkbox" data-column="${key}" ${s.visible.has(key)?'checked':''}>${label}</label>`).join('')}</div></details>
   <details class="game-user-export"><summary aria-label="导出数据"><i class="shell-icon" aria-hidden="true">&#xe066;</i> ▾</summary><div>${[['json','JSON'],['xml','XML'],['csv','CSV'],['txt','TXT'],['doc','MS-Word'],['excel','MS-Excel']].map(([key,label])=>`<button data-export="${key}">${label}</button>`).join('')}</div></details>
  </div></div><p role="alert"></p><div class="game-user-results" aria-live="polite"></div><div class="game-user-pagination"></div></section>`;
 const form=panel.querySelector('form'),errorBox=panel.querySelector('[role=alert]'),results=panel.querySelector('.game-user-results'),pagination=panel.querySelector('.game-user-pagination');
 for(const [name,value] of Object.entries(s.filters)){const field=form.elements.namedItem(name);if(field)field.value=String(value);}
 const withdrawal=tab.endpoint==='/withdrawals'?mountGameWithdrawalActions(panel,s,refresh):null;
 const members=tab.endpoint==='/members'&&!tab.readOnly?mountGameMemberActions(panel,gameId,s,refresh):null;
 const actions=tab.mountActions?.(panel,s,refresh);
 if(withdrawal){s.visible.delete('reason');panel.querySelector('[data-column=reason]').checked=false;}
 attachReviewDates(form);
 const setExpanded=value=>{s.filtersExpanded=value;form.hidden=!value;panel.querySelector('[data-action=search]').setAttribute('aria-expanded',String(value));};
 setExpanded(s.filtersExpanded??!!tab.filtersExpanded);
 panel.querySelector('[data-action=cards]').setAttribute('aria-pressed',String(s.cards));
 const paint=()=>{
  const columns=tab.columns.filter(([key])=>s.visible.has(key));
  results.innerHTML=s.cards?`<div class="game-user-cards">${s.items.map(row=>`<article>${columns.map(column=>`<div><strong>${column[1]}:</strong><span>${cell(row,column,true)}</span></div>`).join('')}</article>`).join('')||'<p>没有找到匹配的</p>'}</div>`:
   `<div class="table-wrap"><table class="ads-table"><thead><tr>${columns.map(([key,label,kind])=>`<th data-field="${key}" ${kind==='sort'||kind==='date'?`aria-sort="${s.sort===key?(s.order==='asc'?'ascending':'descending'):'none'}"`:''}>${kind==='sort'||kind==='date'?`<button data-sort="${key}">${label}</button>`:label}</th>`).join('')}</tr></thead><tbody>${s.items.map(row=>`<tr>${columns.map(column=>`<td data-field="${column[0]}">${cell(row,column,true)}</td>`).join('')}</tr>`).join('')||`<tr><td colspan="${columns.length}">没有找到匹配的记录</td></tr>`}</tbody></table></div>`;
  withdrawal?.paint();
  members?.paint();
  actions?.paint?.();
  const size=displayedSize==='All'?Math.max(1,s.total):displayedSize,page=displayedPage,last=Math.max(1,Math.ceil(s.total/size));
  let pages;
  if(last<=7)pages=Array.from({length:last},(_,i)=>i+1);
  else if(page<=4)pages=[1,2,3,4,5,last];
  else if(page>=last-3)pages=[1,...Array.from({length:5},(_,i)=>last-4+i)];
  else pages=[1,page-1,page,page+1,last];
  const sizes=allowedSizes.filter((n,i)=>i===0||allowedSizes[i-1]<s.total||n===displayedSize);
  pagination.hidden=s.total===0;
  pagination.innerHTML=`<div class="game-page-info"><span>显示第 ${s.total?(page-1)*size+1:0} 到第 ${(page-1)*size+s.items.length} 条记录，总共 ${s.total} 条记录</span><span class="game-page-size" ${s.total<=10?'hidden':''}>每页显示 <details><summary aria-label="每页记录数">${displayedSize} <span class="caret"></span></summary><div>${sizes.map(n=>`<button type="button" data-game-size="${n}" ${displayedSize===n?'aria-current="true"':''}>${n}</button>`).join('')}</div></details> 条记录</span></div><nav aria-label="分页" ${last===1?'hidden':''}><button aria-label="上一页" data-page="${page===1?last:page-1}">上一页</button>${pages.map((n,i)=>`${i&&n>pages[i-1]+1?'<span class="game-page-gap">...</span>':''}<button data-page="${n}" ${n===page?'aria-current="page"':''}>${n}</button>`).join('')}<button aria-label="下一页" data-page="${page===last?1:page+1}">下一页</button><span class="game-page-jump"><input type="text" inputmode="numeric" aria-label="跳转页码"><button type="button" data-game-jump title="跳转">跳转</button></span></nav>`;
  results.querySelectorAll('[data-sort]').forEach(button=>button.onclick=()=>{s.order=s.sort===button.dataset.sort&&s.order==='desc'?'asc':'desc';s.sort=button.dataset.sort;s.page=1;refresh();});
  results.querySelectorAll('[data-search-field]').forEach(button=>button.onclick=()=>{const input=form.elements.namedItem(button.dataset.searchField);input.value=button.dataset.searchValue;setExpanded(true);form.requestSubmit();});
  const move=n=>{if(Number.isInteger(n)&&n>=1&&n<=last&&n!==page){s.page=n;s.size=displayedSize;refresh();}};
  pagination.querySelectorAll('[data-page]').forEach(button=>button.onclick=()=>move(Number(button.dataset.page)));
  pagination.querySelectorAll('[data-game-size]').forEach(button=>button.onclick=()=>{
   s.size=button.dataset.gameSize==='All'?'All':Number(button.dataset.gameSize);s.page=1;
   pagination.querySelector('details').open=false;localStorage.setItem('pagesize',String(s.size));refresh();
  });
  pagination.querySelector('details').onkeydown=event=>{if(event.key==='Escape'){event.preventDefault();event.currentTarget.open=false;event.currentTarget.querySelector('summary').focus();}};
  const jump=()=>move(Number(pagination.querySelector('input').value));
  pagination.querySelector('[data-game-jump]').onclick=jump;
  pagination.querySelector('input').onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();jump();}};
 };
 async function refresh() {
  const generation=++s.generation;
  request?.abort();request=new AbortController();errorBox.textContent='';
  try {
   const all=s.size==='All',query=scopedQuery(s.filters,all?1:s.page,all?200:s.size,s.sort,s.order);
   results.setAttribute('aria-busy','true');
   const data=await tableApi(path+'?'+query,{signal:request.signal});
   if(closed||generation!==s.generation)return;
   if(all){
    const ids=new Set(data.items.map(row=>row.id));
    if(ids.size!==data.items.length)throw Error('数据已变化，请刷新后重试');
    while(data.items.length<data.total){
     query.set('offset',String(data.items.length));
     const next=await tableApi(path+'?'+query,{signal:request.signal});
     if(closed||generation!==s.generation)return;
     if(next.total!==data.total||!next.items.length)throw Error('数据已变化，请刷新后重试');
     for(const row of next.items){if(ids.has(row.id))throw Error('数据已变化，请刷新后重试');ids.add(row.id);}
     data.items.push(...next.items);
    }
    if(data.items.length!==data.total)throw Error('数据已变化，请刷新后重试');
   }
   const last=all?1:Math.max(1,Math.ceil(data.total/s.size));
   if(s.page>last){s.page=last;return refresh();}
   s.items=data.items;s.total=data.total;displayedPage=s.page;displayedSize=s.size;withdrawal?.loaded(data.summary);members?.loaded();actions?.loaded?.();tab.onLoad?.(data,panel,refresh);paint();
  }catch(error){if(!closed&&generation===s.generation&&error.name!=='AbortError')errorBox.textContent=error.message;}
  finally{if(generation===s.generation)results.removeAttribute('aria-busy');}
 }
 form.onsubmit=event=>{event.preventDefault();s.filters=Object.fromEntries(new FormData(form));s.page=1;refresh();};
 form.onreset=event=>{event.preventDefault();s.filters={...(tab.resetFilters?.()||{})};for(const field of form.querySelectorAll('input,select'))field.value=s.filters[field.name]??'';actions?.reset?.();s.page=1;refresh();};
 panel.querySelector('[data-action=refresh]').onclick=refresh;
 panel.querySelector('[data-action=search]').onclick=()=>setExpanded(form.hidden);
 panel.querySelector('[data-action=cards]').onclick=event=>{s.cards=!s.cards;event.currentTarget.setAttribute('aria-pressed',String(s.cards));paint();};
 const checkboxes=[...panel.querySelectorAll('[data-column]')];
 checkboxes.forEach(box=>box.disabled=s.visible.size===1&&box.checked);
 checkboxes.forEach(box=>box.onchange=()=>{if(box.checked)s.visible.add(box.dataset.column);else s.visible.delete(box.dataset.column);checkboxes.forEach(item=>item.disabled=s.visible.size===1&&item.checked);paint();});
 panel.querySelectorAll('[data-export]').forEach(button=>button.onclick=async()=>{
  if(exportBusy)return;
  exportBusy=true;exportRequest=new AbortController();const menu=button.closest('details');menu.open=false;
  menu.querySelectorAll('button').forEach(node=>node.disabled=true);errorBox.textContent='';let table;
  try{
   const query=scopedQuery(s.filters,1,200,s.sort,s.order),columns=tab.columns.filter(([key])=>s.visible.has(key)&&!['behavior','member_actions',...(tab.exportExcludeFields||[])].includes(key));
   if(tab.exportSkipFirst)columns.shift();
   await loadReviewExporter();if(closed)return;
   const selected=actions?.selectedItems?.();
   const first=selected?.length?{items:selected,total:selected.length}:await tableApi(path+'?'+query,{signal:exportRequest.signal}),rows=[...first.items];
   while(rows.length<first.total){query.set('offset',String(rows.length));const next=await tableApi(path+'?'+query,{signal:exportRequest.signal});if(next.total!==first.total||!next.items.length)throw Error('数据已变化，请刷新后重新导出');rows.push(...next.items);}
   if(rows.length!==first.total||new Set(rows.map(row=>row.id)).size!==rows.length)throw Error('数据已变化，请刷新后重新导出');
   if(closed)return;
   table=document.createElement('table');table.className='review-export-table';
   table.innerHTML='<thead><tr>'+columns.map(([,label])=>`<th>${label}</th>`).join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+columns.map(column=>`<td>${(tab.exportCell||cell)(row,column)}</td>`).join('')+'</tr>').join('')+'</tbody>';
   panel.append(table);const type=button.dataset.export;
   window.jQuery(table).tableExport({type,preventInjection:false,fileName:tab.exportFileName?.()||'export_'+tab.endpoint,
    mso:{onMsoNumberFormat:cell=>!isNaN(window.jQuery(cell).text())?'\\@':''},
    onBeforeSaveToFile:(data,name,mime,charset)=>{if(closed)return false;if(type==='xml')data=serializeExportXml(table,tab.exportXmlCell);const url=URL.createObjectURL(new Blob([(type==='csv'||type==='txt'?'\ufeff':''),data],{type:mime+';charset='+charset})),link=document.createElement('a');link.href=url;link.download=name;panel.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);return false;}
   });
  }catch(error){if(!closed&&error.name!=='AbortError')errorBox.textContent=error.message;}
  finally{table?.remove();exportBusy=false;menu.querySelectorAll('button').forEach(node=>node.disabled=false);}
 });
 return {state:s,refresh,suspend:()=>{s.generation++;request?.abort();results.removeAttribute('aria-busy');},destroy:()=>{closed=true;s.generation++;request?.abort();exportRequest?.abort();withdrawal?.destroy();members?.destroy();actions?.destroy?.();}};
}

function mountGameMemberActions(panel,gameId,s,refresh){
 const selected=new Set(),results=panel.querySelector('.game-user-results'),errorBox=panel.querySelector('[role=alert]');
 let busy=false,closed=false,editor;
 const actionRow=event=>{
  if(busy||closed||results.hasAttribute('aria-busy')||event.target.closest('button,a,input,select,textarea,label,summary'))return null;
  return event.target.closest('tbody tr,.game-user-cards article');
 };
 results.onclick=event=>actionRow(event)?.querySelector('[data-member-select]')?.click();
 results.ondblclick=event=>actionRow(event)?.querySelector('[data-game-member-edit]')?.click();
 const menu=document.createElement('details');menu.className='game-member-more';
 menu.innerHTML='<summary aria-disabled="true">更多 ▾</summary><div><button data-member-batch="1" disabled>启用</button><button data-member-batch="0" disabled>禁用</button></div>';
 menu.hidden=true;
 panel.querySelector('.game-user-table-tools').before(menu);
 const sync=()=>{
  menu.hidden=!selected.size;
  menu.querySelector('summary').setAttribute('aria-disabled',String(busy||!selected.size));
  menu.querySelectorAll('button').forEach(button=>button.disabled=busy||!selected.size);
  results.querySelectorAll('[data-member-toggle],[data-member-coins],[data-game-member-edit]').forEach(button=>button.disabled=busy);
  const boxes=[...results.querySelectorAll('[data-member-select]')],all=results.querySelector('[data-member-select-all]');
  boxes.forEach(box=>{box.checked=selected.has(Number(box.dataset.memberSelect));box.disabled=busy;});
  if(all){all.checked=boxes.length>0&&selected.size===boxes.length;all.indeterminate=selected.size>0&&selected.size<boxes.length;all.disabled=busy||!boxes.length;}
 };
 menu.querySelector('summary').onclick=event=>{if(busy||!selected.size)event.preventDefault();};
 const update=async(path,method,body)=>{
  if(busy||closed)return;
  busy=true;sync();errorBox.textContent='';const generation=s.generation;
  try{await api(path,{method,body:JSON.stringify(body)});if(!closed){selected.clear();await refresh();}}
  catch(error){if(!closed&&generation===s.generation)errorBox.textContent=error.message;}
  finally{busy=false;if(!closed)sync();}
 };
 menu.querySelectorAll('[data-member-batch]').forEach(button=>button.onclick=()=>{
  const ids=[...selected];if(!ids.length)return;menu.open=false;
  update(`/games/${gameId}/members/batch-status`,'POST',{ids,status:Number(button.dataset.memberBatch)});
 });
 return {
  loaded(){selected.clear();},
  paint(){
   const checkbox=row=>`<input type="checkbox" data-member-select="${esc(row.id)}" aria-label="选择会员 ${esc(row.id)}">`;
   if(s.cards)results.querySelectorAll('article').forEach((article,i)=>article.insertAdjacentHTML('afterbegin',checkbox(s.items[i])));
   else{
    const table=results.querySelector('table');table.tHead.rows[0].insertAdjacentHTML('afterbegin','<th><input type="checkbox" data-member-select-all aria-label="全选本页会员"></th>');
    [...table.tBodies[0].rows].forEach((row,i)=>{if(s.items.length)row.insertAdjacentHTML('afterbegin',`<td>${checkbox(s.items[i])}</td>`);else row.cells[0].colSpan++;});
   }
   results.querySelectorAll('[data-member-select]').forEach(box=>box.onchange=()=>{const id=Number(box.dataset.memberSelect);if(box.checked)selected.add(id);else selected.delete(id);sync();});
   const all=results.querySelector('[data-member-select-all]');if(all)all.onchange=()=>{selected.clear();if(all.checked)s.items.forEach(row=>selected.add(row.id));sync();};
   results.querySelectorAll('[data-member-toggle]').forEach(button=>button.onclick=()=>{
    const id=Number(button.dataset.memberId),key=button.dataset.memberToggle,row=s.items.find(item=>item.id===id);
    if(row)update('/members/'+id,'PATCH',{[key]:Number(row[key])===1?0:1});
   });
   results.querySelectorAll('[data-member-coins]').forEach(button=>button.onclick=()=>{
    if(busy||closed)return;editor?.close();
    editor=openGameCoinDialog(Number(button.dataset.memberCoins),gameId,async()=>{if(!closed)await refresh();});
   });
   results.querySelectorAll('[data-game-member-edit]').forEach(button=>button.onclick=()=>{
    if(busy||closed)return;editor?.close();errorBox.textContent='';
    editor=openGameMemberEditor(Number(button.dataset.gameMemberEdit),gameId,panel.closest('dialog'),async()=>{if(!closed)await refresh();},error=>{if(!closed)errorBox.textContent=error.message;});
   });sync();
  },
  destroy(){closed=true;editor?.close();selected.clear();}
 };
}

function openGameCoinDialog(id,gameId,onSaved){
 document.querySelector('.game-coin-dialog')?.close();
 const dialog=document.createElement('dialog');dialog.className='game-coin-dialog';dialog.setAttribute('aria-label','修改金币');
 dialog.innerHTML='<header><span>修改金币</span><button type="button" aria-label="关闭">×</button></header><form><label>可用金币:<input name="coin" inputmode="decimal" required disabled></label><label>冻结金币:<input name="freeze_coin" inputmode="decimal" required disabled></label><p role="alert"></p><footer><button type="submit" disabled>确定</button><button type="reset" disabled>重置</button></footer></form>';
 const form=dialog.querySelector('form'),errorBox=dialog.querySelector('[role=alert]'),request=new AbortController();
 const keys=['coin','freeze_coin'];let closed=false,busy=false,loaded=false;
 const controls=()=>form.querySelectorAll('input,button').forEach(element=>element.disabled=busy||!loaded);
 const close=()=>dialog.close();dialog.querySelector('header button').onclick=close;
 window.addEventListener('hashchange',close);
 dialog.addEventListener('close',()=>{closed=true;request.abort();window.removeEventListener('hashchange',close);dialog.remove();},{once:true});
 form.onreset=event=>{if(busy||!loaded)event.preventDefault();else errorBox.textContent='';};
 form.onsubmit=async event=>{
  event.preventDefault();if(busy||closed||!loaded)return;
  const raw=keys.map(key=>form.elements[key].value.trim());
  if(raw.some(value=>value===''||!Number.isFinite(Number(value)))){errorBox.textContent='请输入有效的金币数值';return;}
  busy=true;controls();errorBox.textContent='';
  try{
   await api('/members/'+id,{method:'PATCH',body:JSON.stringify(Object.fromEntries(keys.map((key,i)=>[key,Number(raw[i])])))});
   if(!closed){close();await onSaved();}
  }catch(error){if(!closed)errorBox.textContent=error.message;}
  finally{busy=false;if(!closed)controls();}
 };
 document.body.append(dialog);dialog.showModal();
 api('/members/'+id,{signal:request.signal}).then(row=>{
  if(closed)return;if(Number(row.game_id)!==Number(gameId))throw Error('会员不属于当前游戏');
  keys.forEach(key=>{form.elements[key].value=String(row[key]??0);form.elements[key].defaultValue=form.elements[key].value;});loaded=true;controls();form.elements.coin.focus();
 }).catch(error=>{if(!closed&&error.name!=='AbortError')errorBox.textContent=error.message;});
 return dialog;
}

function mountGameWithdrawalActions(panel,s,refresh){
 const selected=new Set();let busy=false,closed=false,confirmation;
 const toolbar=panel.querySelector('.ads-toolbar'),results=panel.querySelector('.game-user-results');
 panel.querySelector('section').insertAdjacentHTML('afterbegin','<div class="game-withdraw-summary"><article><strong data-withdrawn>0</strong><span>已兑换金币</span></article><article><strong data-pending>0</strong><span>兑换中金币</span></article></div>');
 toolbar.querySelector('.game-user-table-tools').insertAdjacentHTML('beforebegin','<button class="game-withdraw-approve" data-game-batch="approve" disabled>批量同意</button><button class="game-withdraw-refuse" data-game-batch="refuse" disabled>批量拒绝</button>');
 const pending=row=>Number(row.status)===0;
 const sync=()=>{
  panel.querySelectorAll('[data-game-batch]').forEach(button=>button.disabled=busy||!selected.size);
  results.querySelectorAll('[data-game-select]').forEach(box=>{box.checked=selected.has(Number(box.dataset.gameSelect));box.disabled=busy||!pending(s.items.find(row=>row.id===Number(box.dataset.gameSelect)));});
  results.querySelectorAll('[data-game-review]').forEach(button=>button.disabled=busy);
  const all=results.querySelector('[data-game-select-all]'),count=s.items.filter(pending).length;
  if(all){all.disabled=busy||!count;all.checked=count>0&&selected.size===count;all.indeterminate=selected.size>0&&selected.size<count;}
 };
 const review=async(action,ids,batch)=>{
  if(busy||closed||!ids.length)return;
  busy=true;sync();const generation=s.generation;
  const dialog=document.createElement('dialog');confirmation=dialog;dialog.className='withdrawal-confirm';
  dialog.innerHTML=`<form><header><span>提示</span><button type="button" data-cancel aria-label="关闭">×</button></header><div class="withdrawal-confirm-message">确认${batch?'批量':''}${action==='approve'?'通过':'拒绝'}吗${action==='reject'?'<label class="game-withdraw-reason">拒绝原因<textarea required maxlength="500"></textarea></label>':''}</div><footer><button type="submit" class="withdrawal-confirm-ok">确定</button><button type="button" data-cancel>取消</button></footer></form>`;
  let reason='';
  const confirmed=await new Promise(resolve=>{
   dialog.querySelectorAll('[data-cancel]').forEach(button=>button.onclick=()=>dialog.close());
   dialog.querySelector('form').onsubmit=event=>{event.preventDefault();const field=dialog.querySelector('textarea');reason=field?.value.trim()||'';if(field&&!reason){field.setCustomValidity('请输入拒绝原因');field.reportValidity();return;}dialog.close('confirm');};
   const field=dialog.querySelector('textarea');if(field)field.oninput=()=>field.setCustomValidity('');
   dialog.addEventListener('close',()=>{dialog.remove();resolve(dialog.returnValue==='confirm');},{once:true});
   document.body.append(dialog);dialog.showModal();dialog.querySelector('textarea,[type=submit]').focus();
  });
  confirmation=null;
  try{
   if(!confirmed||closed||generation!==s.generation)return;
   const body=batch?{ids}:{};if(action==='reject')body.reason=reason;
   await api('/withdrawals/'+(batch?'batch-'+action:ids[0]+'/'+action),{method:'POST',body:JSON.stringify(body)});
   if(!closed){selected.clear();await refresh();}
  }catch(error){if(!closed)panel.querySelector('[role=alert]').textContent=error.message;}
  finally{busy=false;if(!closed)sync();}
 };
 toolbar.querySelectorAll('[data-game-batch]').forEach(button=>button.onclick=()=>review(button.dataset.gameBatch,[...selected],true));
 return {
  loaded(summary){selected.clear();panel.querySelector('[data-withdrawn]').textContent=summary?.withdrawn??0;panel.querySelector('[data-pending]').textContent=summary?.pending??0;},
  paint(){
   const boxes=row=>`<input type="checkbox" data-game-select="${esc(row.id)}" aria-label="选择提现 ${esc(row.id)}">`;
   const actions=row=>pending(row)?[['approve','同意'],['refuse','拒绝'],['reject','有理由拒绝']].map(([action,label])=>`<button class="game-withdraw-${action}" data-game-review="${action}" data-review-id="${esc(row.id)}">${label}</button>`).join(''):'';
   if(s.cards){results.querySelectorAll('article').forEach((article,i)=>{article.insertAdjacentHTML('afterbegin',boxes(s.items[i]));article.insertAdjacentHTML('beforeend',actions(s.items[i]));});}
   else{
    const table=results.querySelector('table');table.tHead.rows[0].insertAdjacentHTML('afterbegin','<th><input type="checkbox" data-game-select-all aria-label="全选待审核提现"></th>');table.tHead.rows[0].insertAdjacentHTML('beforeend','<th>操作</th>');
    [...table.tBodies[0].rows].forEach((row,i)=>{if(!s.items.length){row.cells[0].colSpan+=2;return;}row.insertAdjacentHTML('afterbegin',`<td>${boxes(s.items[i])}</td>`);row.insertAdjacentHTML('beforeend',`<td>${actions(s.items[i])}</td>`);});
   }
   results.querySelectorAll('[data-game-select]').forEach(box=>box.onchange=()=>{const id=Number(box.dataset.gameSelect);if(box.checked)selected.add(id);else selected.delete(id);sync();});
   const all=results.querySelector('[data-game-select-all]');if(all)all.onchange=()=>{selected.clear();if(all.checked)s.items.filter(pending).forEach(row=>selected.add(row.id));sync();};
   results.querySelectorAll('[data-game-review]').forEach(button=>button.onclick=()=>review(button.dataset.gameReview,[Number(button.dataset.reviewId)],false));sync();
  },
  destroy(){closed=true;confirmation?.close();selected.clear();}
 };
}

function openGameUserData(gameId) {
 const existing=document.querySelector('.game-user-dialog');if(existing)existing.close();
 const dialog=document.createElement('dialog');dialog.className='game-user-dialog';dialog.setAttribute('aria-label','用户数据');
 dialog.innerHTML=`<header><span>用户数据</span><div><button data-dialog-maximize aria-label="最大化"><i class="shell-icon" aria-hidden="true">&#xf065;</i></button><button data-dialog-close aria-label="关闭">×</button></div></header><div class="game-user-body"><nav role="tablist" aria-label="用户数据">${gameUserTabs.map((tab,index)=>`<button role="tab" id="game-user-tab-${tab.id}" aria-controls="game-user-pane-${tab.id}" aria-selected="${index===0}" tabindex="${index===0?0:-1}" data-tab="${tab.id}">${tab.label}</button>`).join('')}</nav>${gameUserTabs.map((tab,index)=>`<div role="tabpanel" id="game-user-pane-${tab.id}" aria-labelledby="game-user-tab-${tab.id}" ${index===0?'':'hidden'}></div>`).join('')}</div>`;
 const controllers=new Map(),tabs=[...dialog.querySelectorAll('[role=tab]')];let activeTab;
 const activate=key=>{
  if(activeTab)controllers.get(activeTab)?.suspend?.();
  activeTab=key;
  for(const [input,picker] of reviewDateBindings)if(dialog.contains(input))picker.hide();
  dialog.querySelectorAll('details[open]').forEach(menu=>menu.open=false);
  tabs.forEach(button=>{const active=button.dataset.tab===key;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;dialog.querySelector('#'+button.getAttribute('aria-controls')).hidden=!active;});
  if(!controllers.has(key)){const tab=gameUserTabs.find(item=>item.id===key);controllers.set(key,mountGameUserTable(dialog.querySelector('#game-user-pane-'+key),gameId,tab));}
  controllers.get(key).refresh();
 };
 tabs.forEach(button=>button.onclick=()=>activate(button.dataset.tab));
 dialog.querySelector('[role=tablist]').onkeydown=event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();let index=tabs.indexOf(document.activeElement);index=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;tabs[index].focus();activate(tabs[index].dataset.tab);};
 const close=()=>dialog.close();
 dialog.addEventListener('click',event=>dialog.querySelectorAll('details[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;}));
 dialog.addEventListener('keydown',event=>{
  if(event.key!=='Escape')return;
  const menus=[...dialog.querySelectorAll('details[open]')];
  const pickers=[...reviewDateBindings].filter(([input,picker])=>dialog.contains(input)&&picker.isShowing);
  if(menus.length||pickers.length){event.preventDefault();menus.forEach(menu=>menu.open=false);pickers.forEach(([,picker])=>picker.hide());}
 });
 dialog.querySelector('[data-dialog-close]').onclick=close;
 dialog.querySelector('[data-dialog-maximize]').onclick=event=>{const maximized=dialog.classList.toggle('maximized');event.currentTarget.setAttribute('aria-label',maximized?'还原':'最大化');};
 window.addEventListener('hashchange',close);
 dialog.addEventListener('close',()=>{controllers.forEach(controller=>controller.destroy());window.removeEventListener('hashchange',close);dialog.remove();},{once:true});
 document.body.append(dialog);dialog.showModal();activate(gameUserTabs[0].id);
}

function openGameProfitData(gameId){
 openGameUserData(gameId);
 const tab=document.querySelector('.game-user-dialog [data-tab="seven"]');
 if(tab)tab.click();
}

function memberBehaviorButtons(userId,gameId){
 return `<button class="game-member-behavior" data-member-behavior="single" data-member-id="${esc(userId)}" data-game-id="${esc(gameId)}">单APP行为</button><button class="game-member-behavior multi" data-member-behavior="multiple" data-member-id="${esc(userId)}" data-game-id="${esc(gameId)}">多APP行为</button>`;
}
document.addEventListener('click',event=>{
 const button=event.target.closest('[data-member-behavior]');if(!button)return;
 const userId=Number(button.dataset.memberId),gameId=Number(button.dataset.gameId);
 if(Number.isInteger(userId)&&userId>0&&Number.isInteger(gameId)&&gameId>0)openMemberBehavior(userId,gameId,button.dataset.memberBehavior);
});

function memberBehaviorTabs(userId,scope){
 const identity=[['id','Id'],['user_id','会员ID'],['username','用户账号'],['game_name','游戏名称']];
 const date=['created_at','创建时间','date'];
 const tabs=[
  {id:'lottery',label:'抽奖列表',endpoint:'/lottery-records',columns:[...identity,['lottery_price','金币','sort'],['ecpm','ECPM'],['adn_name','类型','search'],['ip','公网IP','search'],['network_status','内网',{0:'是',1:'否'}],['tag','是否风控'],['is_white','白名单',{0:'否',1:'是'}],['status','状态',{0:'失败',1:'成功'}],['created_at','抽奖时间','date'],['ad_network_rit_id','广告代码位'],['request_id','广告request_id'],['trans_id','交易trans_id']]},
  {id:'risk',label:'风控历史',endpoint:'/risk/history',columns:[...identity,['ip','ip','search'],['network_status','内网',{0:'是',1:'否'}],['tags','标签','search'],date]},
  {id:'income',label:'每日收益',endpoint:'/member-daily-income',columns:[...identity,['coin','收益','sort'],['date','时间','date']]},
  {id:'coins',label:'金币流水',endpoint:'/coin-logs',columns:[...identity,['coin_before','金币变动前','sort'],['coin','金币变动','sort'],['coin_after','金币变动后','sort'],['type','类型',{10:'抽奖',30:'兑换',40:'分销',50:'签到',100:'后台'}],['remark','备注','search'],date],onLoad(data,panel){
   let balances=panel.querySelector('.behavior-balances');
   if(!balances){balances=document.createElement('div');balances.className='behavior-balances';panel.querySelector('.game-user-panel').prepend(balances);}
   balances.innerHTML=[['coin_user','累计收益'],['coin','可用金币'],['freeze_coin','冻结金币']].map(([key,label])=>`<article><strong>${esc(data.member_summary?.[key]??'')}</strong><span>${label}</span></article>`).join('');
   let summary=panel.querySelector('.behavior-coin-summary');
   if(!summary){summary=document.createElement('span');summary.className='behavior-coin-summary';panel.querySelector('[data-action=refresh]').after(summary);}
   summary.innerHTML='<i class="shell-icon" aria-hidden="true">&#xf155;</i> 金币变动：'+esc(data.summary?.change??'');
  }},
  {id:'withdrawals',label:'提现记录',endpoint:'/withdrawals',columns:[...identity.slice(0,2),['username','账号'],identity[3],['good_name','商品名称','search'],['exchange_value','金额','sort'],['receive_name','收件人','search'],['receive_tel','联系方式','search'],['receive_address','收货地址',null,false],['delivery_name','快递名称',null,false],['delivery_no','快递单号',null,false],['remark','备注',null,false],['status','状态',{0:'申请中',1:'审核通过',4:'审核失败'}],['reason','拒绝原因',null,false],['created_at','申请时间','date'],['updated_at','更新时间','date',false]]},
  {id:'members',label:'分销用户',endpoint:'/members',columns:[['id','Id'],['username','账号','search'],identity[3],['coin_user','累计金币收益','sort'],['coin','可用金币','sort'],['freeze_coin','冻结金币','sort'],['is_white','白名单',{0:'否',1:'是'}],['status','状态',{0:'禁用',1:'正常'}],date]},
  {id:'logins',label:'登陆历史',endpoint:'/login-logs',columns:[...identity,['device_id','设备号'],['ip','IP','search'],['created_at','登陆时间','date']]},
  {id:'addresses',label:'收货地址',endpoint:'/member-addresses',columns:[...identity,['receive_name','收件人','search'],['receive_tel','联系方式','search'],['receive_postcode','邮箱编号','search'],['receive_address','详细地址','search'],['default_status','默认地址',{0:'否',1:'是'}],date]}
 ];
 for(const tab of tabs){
  tab.absolute=true;tab.readOnly=true;
  tab.query={[tab.id==='members'?'parent_id':tab.id==='risk'?'member_id':'user_id']:userId};
   if(scope==='multiple'){
   if(tab.id==='risk')tab.columns=tab.columns.filter(([key])=>key!=='user_id');
   tab.columns=tab.columns.map(column=>['user_id','game_name'].includes(column[0])?[column[0],column[1],'search',...column.slice(3)]:column);
   tab.filterAliases={user_id:'filter_user_id',...(tab.id==='members'?{game_name:'game_name_contains'}:{})};
   if(tab.columns.some(([key])=>key==='user_id'))tab.initialFilters={user_id:String(userId)};
  }
  tab.filterColumns=tab.columns.filter(([key,,kind])=>key!=='default_status'&&(kind==='search'||kind==='date'||kind&&typeof kind==='object'));
  tab.cell=(row,column,interactive)=>{
   const [key,,kind]=column,value=row[key];
   if(key==='date')return esc(value??'');
   const searchLinks=['ip',...(tab.id==='withdrawals'?['receive_name','receive_tel']:[]),...(scope==='multiple'?['user_id','game_name']:[])];
   if(kind==='search'&&!searchLinks.includes(key))return esc(value??'');
   if(kind&&typeof kind==='object'){
    const label=kind[value]??(key==='status'&&Number(value)===2&&tab.id==='withdrawals'?'审核失败':undefined);
    if(label===undefined)return '';
    const tone=key==='type'?({10:'success',30:'warning',40:'danger',50:'info',100:'info'})[value]:key==='network_status'?(Number(value)===0?'warning':'success'):key==='is_white'&&tab.id==='lottery'?(Number(value)===1?'warning':'success'):Number(value)===1?'success':Number(value)===4||Number(value)===2||tab.id==='lottery'&&key==='status'?'danger':tab.id==='members'?'warning':'info';
    return `<span class="game-user-label behavior-${tone}">${esc(label)}</span>`;
   }
   return gameUserCell(row,column,interactive);
  };
 }
 tabs[0].onLoad=(data,panel,refresh)=>renderMemberLotterySummary(data.member_summary,panel,userId,scope,refresh);
 return tabs;
}

function renderMemberLotterySummary(summary,panel,userId,scope,refresh){
 const root=document.createElement('div');root.className='behavior-lottery-summary'+(scope==='multiple'?' multiple':'');
 const device=summary?.device||{},shown=value=>esc(value??''),flag=value=>value==null?'':Number(value)===1?'是':'否';
 const counters=fields=>fields.map(([key,label])=>`<div><strong>${shown(summary?.[key])}</strong><span>${label}</span></div>`).join('');
 const ban=(target,label)=>{
  const identifier=target==='imei'?device.imei:device.device_id,key=target==='imei'?'imei_id_ban':'device_id_ban',banned=Number(device[key])===1;
  return `<div>${label}：${identifier?(banned?'封禁':'正常'):''}<button type="button" data-device-ban="${target}" data-available="${Boolean(identifier?.trim())}" ${!identifier?.trim()||panel.behaviorDeviceSaving?'disabled':''}>${banned?'解禁':'封禁'}</button></div>`;
 };
 root.innerHTML=`<div class="behavior-lottery-counters">${counters([['coin','可用金币'],['today_lottery_coin','今日抽奖获得金币'],['today_average_coin','今日平均每次金币']])}</div><div class="behavior-lottery-counters">${counters([['total_clicks','总点击数'],['today_clicks','今日点击次数'],['today_failed','今日失败次数']])}</div><div class="behavior-device-info"><div><div>安卓版本：${shown(device.android_version)}</div><div>手机型号：${shown(device.model)}</div><div>APP应用：<button type="button" data-app-usage>查看详情</button></div><div>IP所在地：${shown(device.ip_address)}</div><div>当前版本：${shown(device.app_version)}</div>${scope==='single'?ban('imei','设备IMEI'):''}</div><div><div>是否风控：${flag(device.risk_flag)}</div><div>USB调试：${flag(device.usb_debugging)}</div><div>是否越狱：${flag(device.rooted)}</div>${ban('device','设备风控')}${scope==='single'?`<div>SIM卡：${shown(device.sim_info)}</div>`:''}</div></div>`;
 const previous=panel.querySelector('.behavior-lottery-summary');if(previous)previous.replaceWith(root);else panel.querySelector('.game-user-panel').prepend(root);
 root.querySelector('[data-app-usage]').onclick=()=>openMemberAppUsage(userId,scope==='single'?panel.closest('dialog').dataset.gameId:null,panel.closest('dialog'));
 root.querySelectorAll('[data-device-ban]').forEach(button=>button.onclick=async()=>{
  if(panel.behaviorDeviceSaving)return;
  const parent=panel.closest('dialog'),target=button.dataset.deviceBan,key=target==='imei'?'imei_id_ban':'device_id_ban';
  const body={target,banned:Number(device[key])!==1,expected_identifier:target==='imei'?device.imei:device.device_id};
  const error=panel.querySelector('[role=alert]');panel.behaviorDeviceSaving=true;error.textContent='';
  root.querySelectorAll('[data-device-ban]').forEach(control=>control.disabled=true);
  try{
   const saved=await api('/members/'+userId+'/device-ban',{method:'PATCH',body:JSON.stringify(body)});
   if(parent.isConnected&&parent.open){
    renderMemberLotterySummary({...summary,device:saved.device},panel,userId,scope,refresh);
    if(!panel.hidden)await refresh();
   }
  }
  catch(err){if(parent.isConnected&&parent.open)error.textContent=err.message;}
  finally{panel.behaviorDeviceSaving=false;if(panel.isConnected)panel.querySelectorAll('[data-device-ban]').forEach(control=>control.disabled=control.dataset.available!=='true');}
 });
}

function openMemberAppUsage(userId,gameId,parent){
 document.querySelectorAll('.member-app-usage-dialog').forEach(previous=>previous.close());
 const dialog=document.createElement('dialog');dialog.className='member-app-usage-dialog';dialog.setAttribute('aria-label','APP应用');
 dialog.innerHTML='<header><span>APP应用</span><button type="button" data-usage-minimize aria-label="最小化" title="最小化"></button><button type="button" data-usage-maximize aria-label="最大化" title="最大化"></button><button type="button" data-usage-close aria-label="关闭" title="关闭"></button></header><main></main>';
 document.body.append(dialog);dialog.showModal();
 const main=dialog.querySelector('main'),request=new AbortController();let closed=false;
 const close=()=>dialog.close();dialog.querySelector('[data-usage-close]').onclick=close;parent.addEventListener('close',close);
 window.addEventListener('hashchange',close);
 const maximize=dialog.querySelector('[data-usage-maximize]');
 const updateWindow=()=>{const label=dialog.classList.contains('expanded')||dialog.classList.contains('minimized')?'还原':'最大化';maximize.setAttribute('aria-label',label);maximize.title=label;};
 dialog.querySelector('[data-usage-minimize]').onclick=()=>{
  dialog.close();dialog.classList.add('minimized');parent.append(dialog);dialog.show();updateWindow();
 };
 maximize.onclick=()=>{
  if(dialog.classList.contains('minimized')){dialog.close();dialog.classList.remove('minimized');document.body.append(dialog);dialog.showModal();}
  else dialog.classList.toggle('expanded');
  updateWindow();
 };
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
 const endDrag=event=>{if(drag?.id!==event.pointerId)return;drag=null;if(header.hasPointerCapture(event.pointerId))header.releasePointerCapture(event.pointerId);};
 header.onpointerup=endDrag;header.onpointercancel=endDrag;header.onlostpointercapture=()=>{drag=null;};
 dialog.addEventListener('close',()=>{
  if(dialog.open)return;
  closed=true;request.abort();drag=null;parent.removeEventListener('close',close);window.removeEventListener('hashchange',close);dialog.remove();
 });
 async function load(){
  main.innerHTML='<p class="behavior-loading">加载中</p>';
  try{
   const query=new URLSearchParams({limit:200,offset:0});if(gameId!==null)query.set('game_id',String(gameId));
   const data=await api('/members/'+userId+'/app-usage?'+query,{signal:request.signal});if(closed)return;
   const ids=new Set(data.items.map(row=>row.id));
   while(data.items.length<data.total){
    query.set('offset',String(data.items.length));const next=await api('/members/'+userId+'/app-usage?'+query,{signal:request.signal});if(closed)return;
    if(next.total!==data.total||!next.items.length)throw Error('数据已变化，请重新加载');
    for(const row of next.items){if(ids.has(row.id))throw Error('数据已变化，请重新加载');ids.add(row.id);}data.items.push(...next.items);
   }
   if(data.items.length!==data.total||ids.size!==data.items.length)throw Error('数据已变化，请重新加载');
   main.innerHTML='<div class="table-wrap"><table class="app-usage-table"><thead><tr>'+['APP名称','次数','包名','使用时间','当天第一次使用时间','最后一次使用时间'].map(label=>`<th>${label}</th>`).join('')+'</tr></thead><tbody>'+data.items.map(row=>`<tr><td>${esc(row.app_name)}</td><td>${esc(row.count)}</td><td>${esc(row.package_name)}</td><td>${esc(row.duration_seconds)}秒</td><td>${row.first_used_at?esc(profileLogTime(row.first_used_at)):''}</td><td>${row.last_used_at?esc(profileLogTime(row.last_used_at)):''}</td></tr>`).join('')+(data.items.length?'':'<tr><td colspan="6">没有找到匹配的记录</td></tr>')+'</tbody></table></div>';
  }catch(error){if(!closed&&error.name!=='AbortError'){main.innerHTML='<p role="alert"></p><button type="button" data-retry>重试</button>';main.querySelector('[role=alert]').textContent=error.message;main.querySelector('[data-retry]').onclick=load;}}
 }
 load();
}

function openMemberBehavior(userId, gameId, scope='single') {
 const tabs=memberBehaviorTabs(userId,scope);
 document.querySelector('.member-behavior-dialog')?.close();
 const parent=document.querySelector('.game-user-dialog[open]');
 const dialog=document.createElement('dialog');dialog.className='member-behavior-dialog';
 dialog.dataset.gameId=String(gameId);
 dialog.setAttribute('aria-label',scope==='single'?'单APP行为':'多APP行为');
 dialog.innerHTML=`<header><span>${scope==='single'?'单APP行为':'多APP行为'}</span><button type="button" data-behavior-close aria-label="关闭">×</button></header><main class="game-user-body"><nav role="tablist">${tabs.map(({id,label},i)=>`<button role="tab" data-behavior-tab="${id}" aria-selected="${i===0}" tabindex="${i===0?0:-1}" id="behavior-tab-${id}" aria-controls="behavior-pane-${id}">${label}</button>`).join('')}</nav>${tabs.map(({id},i)=>`<div id="behavior-pane-${id}" role="tabpanel" aria-labelledby="behavior-tab-${id}" ${i===0?'':'hidden'}></div>`).join('')}</main>`;
 document.body.append(dialog);dialog.showModal();
 const controllers=new Map();let active;
 const buttons=[...dialog.querySelectorAll('[role=tab]')];
 const activate=button=>{
  if(active)controllers.get(active)?.suspend();
  active=button.dataset.behaviorTab;
  for(const [input,picker] of reviewDateBindings)if(dialog.contains(input))picker.hide();
  dialog.querySelectorAll('details[open]').forEach(menu=>menu.open=false);
  buttons.forEach(item=>{const selected=item===button;item.setAttribute('aria-selected',String(selected));item.tabIndex=selected?0:-1;dialog.querySelector('#behavior-pane-'+item.dataset.behaviorTab).hidden=!selected;});
  if(!controllers.has(active))controllers.set(active,mountGameUserTable(dialog.querySelector('#behavior-pane-'+active),scope==='single'?gameId:null,tabs.find(tab=>tab.id===active)));
  controllers.get(active).refresh();
 };
 buttons.forEach(button=>button.onclick=()=>activate(button));
 dialog.querySelector('nav').onkeydown=event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();let i=buttons.indexOf(document.activeElement);i=event.key==='Home'?0:event.key==='End'?buttons.length-1:(i+(event.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;buttons[i].focus();buttons[i].click();};
 const close=()=>dialog.close();
 dialog.querySelector('[data-behavior-close]').onclick=close;
 dialog.addEventListener('click',event=>dialog.querySelectorAll('details[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;}));
 dialog.addEventListener('keydown',event=>{
  if(event.key!=='Escape')return;
  const menus=[...dialog.querySelectorAll('details[open]')],pickers=[...reviewDateBindings].filter(([input,picker])=>dialog.contains(input)&&picker.isShowing);
  if(menus.length||pickers.length){event.preventDefault();menus.forEach(menu=>menu.open=false);pickers.forEach(([,picker])=>picker.hide());}
 });
 parent?.addEventListener('close',close);
 window.addEventListener('hashchange',close);
 dialog.addEventListener('close',()=>{controllers.forEach(controller=>controller.destroy());parent?.removeEventListener('close',close);window.removeEventListener('hashchange',close);dialog.remove();},{once:true});
 activate(buttons[0]);
}

function attachGameUserData(items) {
 const table=document.querySelector('.agent-dashboard .ads-table');if(!table)return;
 table.tHead.rows[0].insertAdjacentHTML('beforeend','<th>数据查看</th>');
 [...table.tBodies[0].rows].forEach((row,index)=>{
  if(!items.length){row.cells[0].colSpan++;return;}
  const cell=row.insertCell(),button=document.createElement('button');button.className='game-user-open';button.dataset.gameUser=items[index].id;button.textContent='用户数据';button.onclick=()=>openGameUserData(items[index].id);cell.append(button);
  const profit=document.createElement('button');profit.className='game-profit-open';profit.textContent='收益数据';profit.onclick=()=>openGameProfitData(items[index].id);cell.append(profit);
 });
}




