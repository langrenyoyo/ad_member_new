const agentAnalysisState={scope:null,tableState:null,controller:null};
const agentAnalysisColumns=[['id','Id'],['username','账号'],['game_name','游戏名称'],['agent_name','代理商名称'],['coin_user','累计金币收益','sort'],['coin_user_month','本月金币收益'],['coin_user_day','今日金币收益'],['coin','可用金币','sort'],['freeze_coin','冻结金币','sort'],['game_addiction_enable','达标'],['is_white','白名单'],['status','状态'],['created_at','创建时间','date'],['member_actions','操作']];
function agentAnalysisCell(row,column,interactive){
 const key=column[0];
 if(key==='member_actions')return `${memberBehaviorButtons(row.id,row.game_id).replace(/><button/g,'> <button')} <button type="button" class="game-member-coins" data-analysis-coins="${esc(row.id)}">修改金币</button> <button type="button" class="game-member-edit" data-analysis-edit="${esc(row.id)}" title="编辑" aria-label="编辑"><i class="shell-icon" aria-hidden="true">&#xf040;</i></button>`;
 if(['is_white','status'].includes(key))return `<button type="button" class="analysis-switch ${Number(row[key])===1?'enabled':''}" data-analysis-toggle="${key}" data-analysis-member="${esc(row.id)}" role="switch" aria-label="${column[1]}" aria-checked="${Number(row[key])===1}"><i class="shell-icon" aria-hidden="true">&#xf205;</i></button>`;
 if(key==='game_addiction_enable')return `<span class="game-user-label ${Number(row[key])===1?'value-1':''}">${Number(row[key])===1?'是':'否'}</span>`;
 if(column[2]==='date')return row[key]?esc(profileLogTime(row[key])):'无';
 return esc(row[key]??'');
}
function agentAnalysisNavigation(id){
 return `<div class="agent-dashboard-name" id="agentAnalysisName"></div><nav class="agent-dashboard-tools">${[['agent-dashboard','数据统计','tachometer'],['agent-analysis','数据分析','gamepad'],['agent-games','游戏列表','gamepad'],['members?agent_id='+id,'用户列表','user'],['withdrawals?agent_id='+id,'用户提现','money']].map(([route,label,icon])=>`<a href="#${route}" ${route==='agent-analysis'?'aria-current="page"':''}><i class="fa fa-${icon}" aria-hidden="true"></i> ${label}</a>`).join('')}</nav>`;
}
function mountAgentAnalysis(panel,id,s,refresh){
 let closed=false,chartGeneration=0,busy=false,editor;
 const charts=[],form=panel.querySelector('form'),results=panel.querySelector('.game-user-results'),errorBox=panel.querySelector('[role=alert]');
 panel.querySelector('section').classList.add('agent-analysis-panel');form.id='agentAnalysisFilters';results.id='agentAnalysisTable';errorBox.id='agentAnalysisError';panel.querySelector('.game-user-pagination').id='agentAnalysisPagination';
 form.innerHTML=[['coin_user_total','累计用户金币收益'],['coin_every','每次抽奖金币收益'],['success_percent','成功率'],['app_num','APP数量']].map(([key,label])=>`<label><span>${label}</span><div class="analysis-range"><input name="${key}_min" inputmode="decimal" aria-label="${label}开始" placeholder="${label}" value="${esc(s.filters[key+'_min']||'')}"><span>-</span><input name="${key}_max" inputmode="decimal" aria-label="${label}结束" placeholder="${label}" value="${esc(s.filters[key+'_max']||'')}"></div></label>`).join('')+`<label><span>抽奖时间</span><input name="created_range" placeholder="抽奖时间" value="${esc(s.filters.created_range||'')}"></label><div class="ads-filter-actions"><button class="ads-submit" type="submit">提交</button><button type="reset">重置</button></div>`;
 const graph=document.createElement('div');graph.className='agent-analysis-charts';
 graph.innerHTML='<div class="analysis-pies">'+[['coin','金币数据'],['success','成功率数据'],['network','网络环境'],['apps','APP数量数据']].map(([key,label])=>`<div><div data-analysis-chart="${key}" role="img" aria-label="${label}"></div><button type="button" ${key==='network'?'':'data-analysis-settings="'+key+'"'}>${key==='network'?'':'<i class="fa fa-cog" aria-hidden="true"></i> '}${label}</button></div>`).join('')+'</div><div class="analysis-large"><div><div data-analysis-chart="games" role="img" aria-label="APP来源"></div></div><div><div data-analysis-chart="scatter" role="img" aria-label="总金币平均金币散点图"></div></div></div>';
 panel.querySelector('.ads-toolbar').after(graph);
 const pieLabel=width=>width<300?{position:'inside',formatter:'{b}\n{d}%',fontSize:11}:{position:'outside',formatter:'{b}({d}%)',fontSize:12};
 const observer=new ResizeObserver(()=>charts.forEach(chart=>{chart.resize();if(['coin','success','network','apps'].includes(chart.getDom().dataset.analysisChart))chart.setOption({series:[{label:pieLabel(chart.getWidth())}]});}));
 const dispose=()=>{observer.disconnect();charts.splice(0).forEach(chart=>chart.dispose());};
 const draw=async data=>{
  const version=++chartGeneration;dispose();
  try{
   await loadStatisticsCharts();if(closed||version!==chartGeneration)return;
   const d=data.echart_data||{},mapping={coin:'echart_coin_data',success:'echart_success_percent_data',network:'echart_ip_data',apps:'echart_app_num_data'};
   for(const [key,field] of Object.entries(mapping)){
    const node=graph.querySelector(`[data-analysis-chart=${key}]`),chart=echarts.init(node,'walden');charts.push(chart);
    chart.setOption({title:{show:false},tooltip:{trigger:'item'},legend:{show:false},series:[{type:'pie',radius:'70%',label:{show:true,...pieLabel(node.clientWidth)},data:d[field]||[],emphasis:{itemStyle:{shadowBlur:10,shadowOffsetX:0,shadowColor:'rgba(0, 0, 0, 0.5)'}}}]});observer.observe(node);
   }
   for(const key of ['games','scatter']){
    const node=graph.querySelector(`[data-analysis-chart=${key}]`),chart=echarts.init(node,'walden');charts.push(chart);
    chart.setOption(key==='games'?{title:{text:'APP来源',left:'center',bottom:'5%',textStyle:{fontSize:14}},tooltip:{trigger:'item'},legend:{show:false},grid:{left:'3%',right:'4%',bottom:'15%'},xAxis:{type:'value',boundaryGap:[0,0.01]},yAxis:{show:false,type:'category',data:d.echart_game_data?.name||[]},series:[{type:'bar',label:{show:true,formatter:'{b}'},data:d.echart_game_data?.value||[]}]}:{title:{text:'总金币平均金币散点图',left:'center',bottom:'5%',textStyle:{fontSize:14}},grid:{right:'4%',bottom:'15%'},xAxis:{scale:true},yAxis:{scale:true},series:[{type:'scatter',data:d.echart_scatter_data||[]}]});observer.observe(node);
   }
  }catch(error){if(!closed&&version===chartGeneration)errorBox.textContent=error.message;}
 };
 graph.querySelectorAll('[data-analysis-settings]').forEach(button=>button.onclick=()=>{if(!closed)openAgentAnalysisSettings(id,button.dataset.analysisSettings,()=>{if(!closed)refresh();});});
 results.addEventListener('click',async event=>{
  if(closed||busy||results.hasAttribute('aria-busy'))return;
  const button=event.target.closest('[data-analysis-toggle],[data-analysis-coins],[data-analysis-edit]');if(!button)return;
  const memberId=Number(button.dataset.analysisMember||button.dataset.analysisCoins||button.dataset.analysisEdit),row=s.items.find(row=>row.id===memberId);if(!row)return;
  if(button.hasAttribute('data-analysis-coins')){editor?.close();editor=openGameCoinDialog(row.id,row.game_id,()=>{if(!closed)refresh();});return;}
  if(button.hasAttribute('data-analysis-edit')){editor?.close();editor=openGameMemberEditor(row.id,row.game_id,null,()=>{if(!closed)refresh();},error=>{if(!closed)errorBox.textContent=error.message;});return;}
  busy=true;button.disabled=true;errorBox.textContent='';
  try{await api('/members/'+row.id,{method:'PATCH',body:JSON.stringify({[button.dataset.analysisToggle]:Number(row[button.dataset.analysisToggle])===1?0:1})});if(!closed)await refresh();}
  catch(error){if(!closed)errorBox.textContent=error.message;}
  finally{busy=false;if(button.isConnected)button.disabled=false;}
 });
 return {paint(){},loaded(){},load(data){
  if(closed)return;document.querySelector('#agentAnalysisName').textContent='代理商名称：'+data.agent_name;
  graph.querySelectorAll('[data-analysis-settings]').forEach(button=>button.disabled=!data.can_configure);draw(data);
 },destroy(){closed=true;chartGeneration++;dispose();editor?.close();document.querySelectorAll('.agent-analysis-settings').forEach(dialog=>dialog.close());}};
}
async function renderAgentAnalysis(){
 const id=Number(sessionStorage.getItem('agent-dashboard-id'));
 if(!Number.isInteger(id)||id<=0){location.hash='agents';return;}
 agentAnalysisState.controller?.destroy();if(agentAnalysisState.scope!==id){agentAnalysisState.scope=id;agentAnalysisState.tableState=null;}
 $('#content').innerHTML=`<section class="agent-analysis">${agentAnalysisNavigation(id)}<div id="agentAnalysisHost"></div></section>`;
 let actions;
 const controller=mountGameUserTable($('#agentAnalysisHost'),null,{endpoint:'/agents/'+id+'/analysis',absolute:true,state:agentAnalysisState.tableState,columns:agentAnalysisColumns,cell:agentAnalysisCell,filterColumns:[],filtersExpanded:true,
  mountActions:(panel,s,refresh)=>(actions=mountAgentAnalysis(panel,id,s,refresh)),onLoad:data=>actions.load(data)});
 agentAnalysisState.controller=controller;agentAnalysisState.tableState=controller.state;
 const form=$('#agentAnalysisFilters'),submit=form.onsubmit;
 form.onsubmit=event=>{
  for(const key of ['coin_user_total','coin_every','success_percent','app_num']){
   const lower=form.elements[key+'_min'].value.trim(),upper=form.elements[key+'_max'].value.trim();
   if([lower,upper].some(value=>value!==''&&(!Number.isFinite(Number(value))||Number(value)<0||(key==='success_percent'&&Number(value)>100)||(key==='app_num'&&!Number.isInteger(Number(value)))))||(lower!==''&&upper!==''&&Number(lower)>Number(upper))){event.preventDefault();$('#agentAnalysisError').textContent='筛选范围无效';return;}
  }
  submit(event);
 };
 await controller.refresh();
}
window.addEventListener('hashchange',()=>{if(!/^#agent-analysis(?:$|[?&])/.test(location.hash)){agentAnalysisState.controller?.destroy();agentAnalysisState.controller=null;}});

async function openAgentAnalysisSettings(id,kind,onSaved){
 const {dialog,body}=createAgentWindow({coin:'金币数据',success:'成功率数据',apps:'APP数量数据'}[kind],'agent-analysis-settings');
 body.innerHTML='<p role="status">加载中</p>';
 let closed=false,busy=false,config;const request=new AbortController(),close=()=>dialog.close();
 dialog.addEventListener('close',()=>{if(dialog.open)return;closed=true;request.abort();});
 const render=()=>{
  body.innerHTML='<form><div class="analysis-setting-label">配置项:</div><div class="analysis-setting-rows"><div class="analysis-setting-head"><span>名称</span><span>开始(&gt;=)</span><span>结束(&lt;=)</span><span></span></div><div data-bucket-rows></div><button type="button" data-bucket-add><i class="fa fa-plus" aria-hidden="true"></i> 追加</button></div><p role="alert"></p><footer><button type="submit">提交</button><button type="reset">重置</button></footer></form>';
  const form=body.querySelector('form'),rows=form.querySelector('[data-bucket-rows]');
  let dragging;
  const add=(value={name:'',minimum:'',maximum:''})=>{
   const row=document.createElement('div');row.className='analysis-setting-row';row.innerHTML=`<input name="name" aria-label="名称" value="${esc(value.name)}" required><input name="minimum" inputmode="decimal" aria-label="开始" value="${esc(value.minimum)}" required><input name="maximum" inputmode="decimal" aria-label="结束" value="${esc(value.maximum)}" required><button type="button" data-bucket-remove aria-label="删除" title="删除"><i class="fa fa-times" aria-hidden="true"></i></button><button type="button" data-bucket-move draggable="true" aria-label="调整顺序" title="调整顺序"><i class="fa fa-arrows" aria-hidden="true"></i></button>`;
   row.querySelector('[data-bucket-remove]').onclick=()=>{if(!busy)row.remove();};
   const move=row.querySelector('[data-bucket-move]');move.ondragstart=event=>{if(busy){event.preventDefault();return;}dragging=row;event.dataTransfer.setData('text/plain','bucket');};move.ondragend=()=>dragging=null;
   row.ondragover=event=>{if(!busy&&dragging&&dragging!==row){event.preventDefault();const bounds=row.getBoundingClientRect();rows.insertBefore(dragging,event.clientY>bounds.y+bounds.height/2?row.nextSibling:row);}};row.ondrop=event=>{event.preventDefault();dragging=null;};
   move.onkeydown=event=>{if(busy)return;if(event.key==='ArrowUp'&&row.previousElementSibling){event.preventDefault();rows.insertBefore(row,row.previousElementSibling);move.focus();}if(event.key==='ArrowDown'&&row.nextElementSibling){event.preventDefault();rows.insertBefore(row.nextElementSibling,row);move.focus();}};rows.append(row);
  };
  config[kind].forEach(add);form.querySelector('[data-bucket-add]').onclick=()=>{if(!busy)add();};form.onreset=event=>{event.preventDefault();if(!busy)render();};
  form.onsubmit=async event=>{
   event.preventDefault();if(busy||closed)return;
   const buckets=[...rows.children].map(row=>({name:row.querySelector('[name=name]').value,minimum:Number(row.querySelector('[name=minimum]').value),maximum:Number(row.querySelector('[name=maximum]').value)}));
   if(buckets.some(row=>!row.name.trim()||!Number.isFinite(row.minimum)||!Number.isFinite(row.maximum)||row.minimum<0||row.maximum<row.minimum)){form.querySelector('[role=alert]').textContent='分组名称或范围无效';return;}
   busy=true;const controls=[...form.querySelectorAll('input,button')];controls.forEach(node=>node.disabled=true);form.querySelector('[role=alert]').textContent='';
   try{await api('/agents/'+id+'/analysis-settings',{method:'PATCH',body:JSON.stringify({[kind]:buckets})});if(!closed){close();onSaved();}}
   catch(error){if(!closed)form.querySelector('[role=alert]').textContent=error.message;}
   finally{busy=false;if(!closed)controls.forEach(node=>node.disabled=false);}
  };
 };
 async function load(){
  try{config=await api('/agents/'+id+'/analysis-settings',{signal:request.signal});if(!closed)render();}
  catch(error){if(!closed&&error.name!=='AbortError'){body.innerHTML='<p role="alert"></p><button type="button">重试</button>';body.querySelector('[role=alert]').textContent=error.message;body.querySelector('button').onclick=load;}}
 }
 await load();
}
