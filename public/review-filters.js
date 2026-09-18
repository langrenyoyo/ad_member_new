function reviewDefaultFilters(now=new Date()){
 const day=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);
 const start=new Date(day+'T00:00:00+08:00');start.setUTCDate(start.getUTCDate()-2);
 const first=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(start);
 return {created_range:`${first} 00:00:00 - ${day} 23:59:59`};
}
function reviewFilterMarkup(kind){
 const f=reviewStates[kind].filters||{};
 const fields=[['user_id','会员ID'],['username','账号'],['vip','VIP'],['parent_id','上级Id'],['game_id','游戏名称'],['agent_id','代理商名称'],['name','昵称']];
 if(kind==='withdrawals')fields.push(['good_name','商品名称'],['receive_name','收件人'],['receive_tel','联系方式'],['exchange_type','提现方式'],['status','状态'],['plan_status','定时']);
 else fields.push(['pics','申请图片'],['receive_name','收件人'],['receive_tel','联系方式'],['status','状态']);
 fields.push(['created_range','申请时间'],['updated_range','更新时间']);
 const choices={vip:[['0','V0'],['1','V1'],['2','V2']],exchange_type:[['0','默认'],['1','支付宝'],['2','微信']],plan_status:[['0','默认'],['1','转账中'],['2','已转账']]};
 choices.status=[['0','申请中'],['1','审核通过'],['4','审核失败']];
 return `<form id="reviewFilters" class="ads-filters">${fields.map(([key,label])=>`<label><span>${label}</span>${choices[key]?`<select name="${key}"><option value="">选择</option>${choices[key].map(([value,text])=>`<option value="${value}" ${f[key]===value?'selected':''}>${text}</option>`).join('')}</select>`:`<input name="${key}" value="${esc(f[key]||'')}" placeholder="${key.endsWith('_range')?'YYYY-MM-DD HH:mm:ss - YYYY-MM-DD HH:mm:ss':label}">`}</label>`).join('')}<div class="ads-filter-actions"><button type="submit">提交</button><button type="reset">重置</button></div></form>`;
}
function reviewFilterParams(kind,params){
 for(const [key,value] of Object.entries(reviewStates[kind].filters||{})){
  if(!value)continue;
  if(!key.endsWith('_range')){params.set(key,value);continue;}
  const values=value.split(' - ').map(v=>new Date(v.replace(' ','T')+'+08:00'));
  if(values.length!==2||values.some(v=>Number.isNaN(v.getTime()))||values[0]>values[1])throw Error('时间范围无效');
  const prefix=key.replace('_range','');params.set(prefix+'_from',values[0].toISOString());params.set(prefix+'_to',values[1].toISOString());
 }
}
function attachReviewFilters(kind){
 const form=$('#reviewFilters');
 attachReviewLookups(form,kind);
 attachReviewDates(form);
 const s=reviewStates[kind],button=document.createElement('button');
 button.id='reviewSearchToggle';button.type='button';button.title='普通搜索';button.setAttribute('aria-label','普通搜索');button.setAttribute('aria-controls','reviewFilters');
 button.innerHTML='<i class="glyphicon glyphicon-search" aria-hidden="true"></i>';
 const apply=()=>{form.hidden=!!s.filtersCollapsed;button.setAttribute('aria-expanded',String(!form.hidden));};
 button.onclick=()=>{s.filtersCollapsed=!s.filtersCollapsed;apply();};
 document.querySelector('.withdrawal-toolbar').append(button);apply();
 form.onsubmit=e=>{e.preventDefault();reviewStates[kind].filters=Object.fromEntries(new FormData(form));reviewStates[kind].status=reviewStates[kind].filters.status||'';reviewStates[kind].page=1;renderReviewPage(kind);};
 form.onreset=e=>{e.preventDefault();reviewStates[kind].filters=reviewDefaultFilters();reviewStates[kind].status='';reviewStates[kind].page=1;renderReviewPage(kind);};
}
