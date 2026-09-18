/* Dedicated game lifecycle editor for the global and scoped game tables. */
const gameFormState={request:null,sequence:0,session:null};
const gameFormLabels={
 agent_id:'主体',name:'游戏名称',game_icon:'游戏 Icon',game_key:'游戏 key',game_url:'游戏链接',game_type:'游戏类型',
 status:'上架状态',ad_status:'广告状态',lucky_enable:'抽奖开关',is_landscape:'屏幕方向',is_game:'游戏类型开关',is_mobile:'移动端',is_imei:'IMEI 校验',
 raffle_num:'抽奖次数',star_countdown:'开始倒计时',over_countdown:'结束倒计时',star_coin:'开始奖励金币',over_coin:'结束奖励金币',coin_get:'金币上限',exchange_num:'兑换数量',
 commission_status:'独立分佣',commission_source:'分佣来源',commission_rate:'分佣比例',tixian_price:'提现价格',tixian_coin:'提现金币',tixian_wx:'微信提现',
 wx_appid:'微信 AppID',wx_secert:'微信 Secret',other_url:'其它链接',settings_json:'高级配置 JSON'
};
const gameFormDefaults={agent_id:0,name:'',game_icon:'',game_key:'',game_url:'',game_type:0,status:1,ad_status:1,lucky_enable:1,is_landscape:0,is_game:1,is_mobile:0,is_imei:0,raffle_num:500,star_countdown:30,over_countdown:50,star_coin:.01,over_coin:.01,coin_get:1000000,exchange_num:10,commission_status:0,commission_source:0,commission_rate:0,tixian_price:'',tixian_coin:'',tixian_wx:0,wx_appid:'',wx_secert:'',other_url:'',settings_json:'{}'};
const gameFormNumberFields=new Set(['agent_id','game_type','status','ad_status','lucky_enable','is_landscape','is_game','is_mobile','is_imei','raffle_num','star_countdown','over_countdown','star_coin','over_coin','coin_get','exchange_num','commission_status','commission_source','commission_rate','tixian_wx']);
const gameFormIntegerFields=new Set(['agent_id','game_type','status','ad_status','lucky_enable','is_landscape','is_game','is_mobile','is_imei','raffle_num','exchange_num','commission_status','commission_source','tixian_wx']);
const gameFormOptions={
 game_type:[['0','安卓 APP'],['1','抖音小程序'],['2','微信小程序']],
 status:[['1','上架'],['0','下架']],ad_status:[['1','启用'],['0','禁用']],lucky_enable:[['1','开启'],['0','关闭']],
 is_landscape:[['0','竖屏'],['1','横屏']],is_game:[['1','是'],['0','否']],is_mobile:[['0','否'],['1','是']],is_imei:[['0','否'],['1','是']],
 commission_status:[['1','启用'],['0','禁用']],commission_source:[['0','代理'],['1','下级']],tixian_wx:[['0','关闭'],['1','开启']]
};
const gameFormSections=[
 {title:'基础信息',fields:['agent_id','name','game_icon','game_key','game_url','game_type']},
 {title:'运行配置',fields:['status','ad_status','lucky_enable','is_landscape','is_game','is_mobile','is_imei','raffle_num','star_countdown','over_countdown','star_coin','over_coin','coin_get','exchange_num']},
 {title:'分佣与提现',fields:['commission_status','commission_source','commission_rate','tixian_price','tixian_coin','tixian_wx']},
 {title:'微信与高级配置',fields:['wx_appid','wx_secert','other_url','settings_json']}
];

function gameFormValue(row,key){const value=row?.[key];return value===null||value===undefined?gameFormDefaults[key]??'':value;}
function gameFormSelect(key,value){const current=String(value??'');return `<select name="${key}">${gameFormOptions[key].map(([option,label])=>`<option value="${esc(option)}" ${current===option?'selected':''}>${esc(label)}</option>`).join('')}</select>`;}
function gameFormInput(key,value){
 const current=gameFormValue({[key]:value},key),escaped=esc(current),numeric=gameFormNumberFields.has(key);
 if(gameFormOptions[key])return gameFormSelect(key,current);
 if(key==='settings_json')return `<textarea name="${key}" rows="5" spellcheck="false">${escaped}</textarea>`;
 return `<input name="${key}" type="${numeric?'number':'text'}" value="${escaped}" ${numeric?`step="${gameFormIntegerFields.has(key)?'1':'any'}"`:''} autocomplete="off">`;
}
async function gameFormAgents(selected,signal){
 const options=[['0','无主体']];let offset=0;
 while(true){const data=await api('/member-filter-options/agents?limit=100&offset='+offset,{signal});for(const row of data.items||[])options.push([String(row.id),`${row.name}（${row.id}）`]);offset+=(data.items||[]).length;if(!data.items?.length||offset>=data.total)break;}
 if(!options.some(([id])=>id===String(selected))&&selected!==0&&selected!=='0')options.unshift([String(selected),`主体 ${selected}`]);
 return options.length?options:[['0','无主体']];
}
function gameFormAgentControl(row,scopedAgentId){
 const selected=scopedAgentId==null?gameFormValue(row,'agent_id'):scopedAgentId;
 if(scopedAgentId!=null)return `<input type="hidden" name="agent_id" value="${esc(selected)}"><div class="game-form-readonly">当前主体：${esc(selected)}</div>`;
 return gameFormSelect('agent_id',selected);
}
function gameFormControl(row,key,scopedAgentId){return key==='agent_id'?gameFormAgentControl(row,scopedAgentId):gameFormInput(key,gameFormValue(row,key));}
function gameFormMarkup(row,scopedAgentId){
 return `<div class="game-form-scroll"><div class="game-form-fields">${gameFormSections.map(section=>`<section class="game-form-section"><h3>${section.title}</h3><div class="game-form-grid">${section.fields.map(key=>`<label class="game-form-field ${key==='settings_json'?'game-form-field-full':''}"><span>${gameFormLabels[key]}${key==='name'?' *':''}</span>${gameFormControl(row,key,scopedAgentId)}</label>`).join('')}</div></section>`).join('')}</div><div class="game-form-error" role="alert"></div></div><div class="modal-actions"><button type="submit" class="button primary">保存</button><button type="button" class="button ghost" data-game-form-cancel>取消</button></div>`;
}
async function openAgentGameForm(gameId,scopedAgentId=null){
 const modal=$('#modal'),form=$('#editorForm');if(!modal||!form)return;
 gameFormState.request?.abort();const request=new AbortController();gameFormState.request=request;const sequence=++gameFormState.sequence,creating=gameId==null;
 const scoped=scopedAgentId==null?null:Number(scopedAgentId);
 const session={sequence,route:location.hash,scoped,request,saving:false};gameFormState.session=session;
 const current=()=>gameFormState.session===session&&!modal.hidden&&location.hash===session.route&&!request.signal.aborted;
 modal.hidden=false;form.setAttribute('aria-busy','true');form.dataset.agentForm='';form.dataset.gameForm='1';form.dataset.create=creating?'1':'';form.dataset.edit=creating?'':'games/'+gameId;form.dataset.path='/games';
 $('#modalTitle').textContent=creating?'新建游戏':'编辑游戏';$('#formFields').innerHTML='<div class="game-form-loading" role="status">正在加载...</div>';
 try{
  if(scoped!==null&&(!Number.isSafeInteger(scoped)||scoped<=0))throw Error('主体范围无效');
  const row=creating?{...gameFormDefaults,agent_id:scoped??0}:await api('/games/'+gameId,{signal:request.signal});
  if(!current())return;
  if(!creating&&scoped!==null&&Number(row.agent_id)!==scoped)throw Error('游戏不属于当前主体');
  if(scoped==null){const agents=await gameFormAgents(row.agent_id,request.signal);if(!current())return;gameFormOptions.agent_id=agents;}
  $('#formFields').innerHTML=gameFormMarkup(row,scoped);form.removeAttribute('aria-busy');
  session.fields=form.querySelector('.game-form-fields');
 }catch(error){
  if(error.name==='AbortError'||!current())return;
  $('#formFields').innerHTML=`<div class="game-form-error" role="alert">${esc(error.message)}</div><div class="modal-actions"><button type="button" class="button ghost" data-game-form-retry>重试</button></div>`;form.removeAttribute('aria-busy');form.querySelector('[data-game-form-retry]')?.addEventListener('click',()=>openAgentGameForm(gameId,scoped));
 }
}
function gameFormBody(form){
 const body=Object.fromEntries(new FormData(form));
 if(!String(body.name||'').trim())throw Error('游戏名称不能为空');body.name=String(body.name).trim();
 for(const key of gameFormNumberFields){if(!(key in body))continue;const raw=String(body[key]).trim();if(raw==='')throw Error(`${gameFormLabels[key]}不能为空`);const value=Number(raw);if(!Number.isFinite(value))throw Error(`${gameFormLabels[key]}必须是有效数字`);if(gameFormIntegerFields.has(key)&&!Number.isInteger(value))throw Error(`${gameFormLabels[key]}必须是整数`);body[key]=value;}
 try{JSON.parse(String(body.settings_json??''));}catch{throw Error('高级配置 JSON 格式无效');}
 return body;
}
document.addEventListener('click',event=>{
 const trigger=event.target.closest('#createButton,#agentGameCreate,[data-game-edit],[data-edit]');if(!trigger)return;
 const scopedPage=state.view==='agent-games',globalPage=state.view==='games';if(!scopedPage&&!globalPage)return;
 if(trigger.matches('[data-edit]')&&!globalPage)return;if(trigger.matches('#agentGameCreate,[data-game-edit]')&&!scopedPage)return;
 event.preventDefault();event.stopImmediatePropagation();
 const id=trigger.matches('[data-game-edit],[data-edit]')?Number(trigger.dataset.gameEdit||trigger.dataset.edit):null;
 openAgentGameForm(id,scopedPage?Number(sessionStorage.getItem('agent-dashboard-id')):null);
},true);
function closeGameForm(){
 if(!gameFormState.session)return;
 gameFormState.session=null;gameFormState.request?.abort();$('#modal').hidden=true;$('#editorForm').dataset.gameForm='';$('#editorForm').removeAttribute('aria-busy');
}
document.addEventListener('click',event=>{if(event.target.closest('[data-game-form-cancel],#closeModal,#cancelModal'))closeGameForm();},true);
window.addEventListener('hashchange',closeGameForm);
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&gameFormState.session){event.preventDefault();closeGameForm();}});
document.addEventListener('submit',async event=>{
 const form=event.target,session=gameFormState.session;if(form.id!=='editorForm'||form.dataset.gameForm!=='1'||!session)return;event.preventDefault();event.stopImmediatePropagation();
 const current=()=>gameFormState.session===session&&session.fields?.isConnected&&!$('#modal').hidden&&location.hash===session.route;
 if(!current()||session.saving)return;const error=form.querySelector('.game-form-error');
 let body;try{body=gameFormBody(form);}catch(errorValue){error.textContent=errorValue.message;return;}
 if(session.scoped!==null)body.agent_id=session.scoped;
 session.saving=true;form.setAttribute('aria-busy','true');error.textContent='';const controls=[...form.querySelectorAll('input,select,textarea,button')];controls.forEach(control=>control.disabled=true);
 try{await api(form.dataset.edit?'/'+form.dataset.edit:form.dataset.path,{method:form.dataset.edit?'PATCH':'POST',body:JSON.stringify(body)});if(!current())return;form.dataset.create='';form.dataset.edit='';closeGameForm();if(state.view==='agent-games')await renderAgentGames();else await load();}
 catch(errorValue){if(current()){error.textContent=errorValue.message;error.scrollIntoView({block:'nearest'});controls.forEach(control=>control.disabled=false);}}finally{session.saving=false;if(current())form.removeAttribute('aria-busy');}
},true);
