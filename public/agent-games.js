const agentGameStates=new Map();
async function renderAgentGames(){
 const id=Number(sessionStorage.getItem('agent-dashboard-id'));
 if(!id){$('#content').innerHTML='<a href="#agents">请先选择主体</a>';return;}
 if(!agentGameStates.has(id))agentGameStates.set(id,{page:1,filters:{},sort:'id',order:'desc',generation:0});
 const s=agentGameStates.get(id),generation=++s.generation;
 const params=new URLSearchParams({agent_id:id,limit:20,offset:(s.page-1)*20,sort:s.sort,order:s.order});
 try{
  for(const [key,value] of Object.entries(s.filters)){
   if(!value)continue;
   if(key!=='created_range'){params.set(key,value);continue;}
   const dates=value.split(' - ').map(v=>new Date(v.replace(' ','T')+'+08:00'));
   if(dates.length!==2||dates.some(v=>Number.isNaN(v.getTime()))||dates[0]>dates[1])throw Error('时间范围无效');
   params.set('created_from',dates[0].toISOString());params.set('created_to',dates[1].toISOString());
  }
  const [agent,data]=await Promise.all([api('/agents/'+id),api('/games?'+params)]);
  if(state.view!=='agent-games'||s.generation!==generation)return;
  const lastPage=Math.max(1,Math.ceil(data.total/20));if(s.page>lastPage){s.page=lastPage;return renderAgentGames();}
  $('#content').innerHTML=`<section class="agent-dashboard"><div class="agent-dashboard-name">代理商名称：${esc(agent.name)}</div><div class="agent-dashboard-tools"><a href="#agent-dashboard">数据统计</a><button>游戏列表</button></div><section class="ads-panel"><form id="agentGameFilters" class="ads-filters"><label><span>游戏名称</span><input name="name" value="${esc(s.filters.name||'')}"></label>${[['game_type','类型',{'0':'安卓APP','1':'抖音小程序','2':'微信小程序'}],['game_ad_status','广告状态',{'1':'正常', '2':'封应用', '3':'封主体'}]].map(([key,label,options])=>`<label><span>${label}</span><select name="${key}"><option value="">选择</option>${Object.entries(options).map(([value,text])=>`<option value="${value}" ${s.filters[key]===value?'selected':''}>${text}</option>`).join('')}</select></label>`).join('')}<div class="ads-filter-actions"><button type="submit">提交</button><button type="reset">重置</button></div></form><p id="agentGameError" role="alert"></p><div class="table-wrap"><table class="ads-table"><thead><tr><th>Id</th><th>游戏Icon</th><th>游戏名称</th><th>类型</th><th>广告状态</th><th><button data-agent-game-sort="game_lottery_num">金币异常概率</button></th><th>操作</th><th><button data-agent-game-sort="created_at">创建时间</button></th></tr></thead><tbody>${data.items.map(row=>`<tr><td>${row.id}</td><td>${row.game_icon?subsidyPictures(row.game_icon):''}</td><td>${esc(row.name)}</td><td>${esc(({0:'安卓APP',1:'抖音小程序',2:'微信小程序'})[row.game_type]??'')}</td><td>${row.game_ad_status!=null&&row.game_ad_status!==1?`<span class="game-ban-icon" role="img" aria-label="${esc(({2:'封应用',3:'封主体'})[row.game_ad_status]||'封禁')}">♠</span>`:esc(({1:'正常'})[row.game_ad_status]??'')}</td><td>${row.game_lottery_num==null?'':esc(row.game_lottery_num)+'%'}</td><td><button data-game-edit="${row.id}" data-game-name="${esc(row.name)}">编辑</button><button data-game-status="${row.id}" data-next="${row.status===1?0:1}">${row.status===1?'上架':'下架'}</button></td><td>${esc(profileLogTime(row.created_at))}</td></tr>`).join('')||'<tr><td colspan="8">没有找到匹配的记录</td></tr>'}</tbody></table></div><div class="pagination"><span>共 ${data.total} 条记录，第 ${s.page} 页</span><button id="agentGamePrev" ${s.page===1?'disabled':''}>上一页</button><button id="agentGameNext" ${s.page*20>=data.total?'disabled':''}>下一页</button></div></section></section>`;
  attachSubsidyPictures();attachGameUserData(data.items);const createGame=document.createElement('button');createGame.type='button';createGame.id='agentGameCreate';createGame.textContent='新建游戏';document.querySelector('.agent-dashboard-tools').append(createGame);createGame.onclick=()=>openAgentGameForm(null,id);const form=$('#agentGameFilters');
  const actions=form.querySelector('.ads-filter-actions');
  actions.insertAdjacentHTML('beforebegin',`<label><span>游戏key</span><input name="game_key" value="${esc(s.filters.game_key||'')}"></label>${[['is_landscape','横竖屏',{'0':'竖屏','1':'横屏'}],['ad_status','广告状态',{'0':'禁用','1':'启用'}]].map(([key,label,options])=>`<label><span>${label}</span><select name="${key}"><option value="">选择</option>${Object.entries(options).map(([value,text])=>`<option value="${value}" ${s.filters[key]===value?'selected':''}>${text}</option>`).join('')}</select></label>`).join('')}<label><span>创建时间</span><input name="created_range" value="${esc(s.filters.created_range||'')}"></label>`);
  attachReviewDates(form);
  form.onsubmit=event=>{event.preventDefault();s.filters=Object.fromEntries(new FormData(form));s.page=1;renderAgentGames();};
  form.onreset=event=>{event.preventDefault();s.filters={};s.page=1;renderAgentGames();};
  $('#agentGamePrev').onclick=()=>{s.page--;renderAgentGames();};$('#agentGameNext').onclick=()=>{s.page++;renderAgentGames();};
  document.querySelectorAll('[data-agent-game-sort]').forEach(button=>button.onclick=()=>{s.order=s.sort===button.dataset.agentGameSort&&s.order==='desc'?'asc':'desc';s.sort=button.dataset.agentGameSort;s.page=1;renderAgentGames();});
  document.querySelectorAll('[data-game-edit]').forEach(button=>button.onclick=()=>openAgentGameForm(Number(button.dataset.gameEdit),id));
  document.querySelectorAll('[data-game-status]').forEach(button=>button.onclick=async()=>{
   button.disabled=true;try{await api('/games/'+button.dataset.gameStatus,{method:'PATCH',body:JSON.stringify({status:Number(button.dataset.next)})});if(state.view==='agent-games')await renderAgentGames();}
   catch(error){if(button.isConnected){$('#agentGameError').textContent=error.message;button.disabled=false;}}
  });
 }catch(error){if(state.view==='agent-games'&&s.generation===generation){const box=$('#agentGameError');if(box)box.textContent=error.message;else $('#content').innerHTML=`<p role="alert">${esc(error.message)}</p>`;}}
}
document.addEventListener('DOMContentLoaded',()=>{views['agent-games']=['游戏列表',''];});
