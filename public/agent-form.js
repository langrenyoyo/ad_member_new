/* Dedicated agent lifecycle editor. It runs before app.js and captures agent clicks. */
const agentFormState={request:null,sequence:0};
const agentFormLabels={parent_id:'上级主体',name:'主体名称',user_name:'主体账号',password:'密码',avatar:'头像地址',user_id:'用户 ID',role_id:'角色 ID',security_key:'安全密钥',status:'主体状态',game_ad_status:'游戏广告',ht_status:'后台状态',is_gx:'GX 状态'};
const agentFormFlags={status:[['1','启用'],['0','禁用']],game_ad_status:[['1','开启'],['0','关闭']],ht_status:[['1','开启'],['0','关闭']],is_gx:[['1','是'],['0','否']]};
function agentFormControl(key,value,creating){
 const current=value===null||value===undefined?'':String(value);
 if(agentFormFlags[key])return `<select name="${key}">${agentFormFlags[key].map(([v,label])=>`<option value="${v}" ${current===v?'selected':''}>${label}</option>`).join('')}</select>`;
 const type=key==='password'?'password':'text',required=creating&&key==='name'?' required':'',placeholder=key==='password'&&!creating?' placeholder="留空则保持原密码"':'';
 return `<input name="${key}" type="${type}" value="${key==='password'?'':esc(current)}"${required}${placeholder} autocomplete="${key==='password'?'new-password':'off'}">`;
}
async function agentFormParents(selected){
 const data=await api('/member-filter-options/agents?limit=100');
 const options=[['0','无上级']];
 for(const row of data.items||[])if(String(row.id)!==String(selected))options.push([String(row.id),`${row.name}（${row.id}）`]);
 return options;
}
async function openAgentForm(id,creating){
 const modal=$('#modal'),form=$('#editorForm');agentFormState.request?.abort();const request=new AbortController();agentFormState.request=request;const sequence=++agentFormState.sequence;
 modal.hidden=false;form.setAttribute('aria-busy','true');form.dataset.agentForm='1';form.dataset.create=creating?'1':'';form.dataset.edit=creating?'':'agents/'+id;form.dataset.path='/agents';$('#modalTitle').textContent=creating?'新建主体':'编辑主体';$('#formFields').innerHTML='<div class="agent-form-loading" role="status">正在加载...</div>';
 try{
  const row=creating?{parent_id:0,name:'',user_name:'',avatar:'',user_id:'',role_id:'',security_key:'',status:1,game_ad_status:0,ht_status:0,is_gx:0}:await api('/agents/'+id,{signal:request.signal});
  const parents=await agentFormParents(row.parent_id);if(sequence!==agentFormState.sequence||request.signal.aborted)return;
  const fields=['name','user_name','password','avatar','user_id','role_id','security_key','status','game_ad_status','ht_status','is_gx'];
  const html=fields.map(key=>`<label class="agent-form-field"><span>${agentFormLabels[key]}${key==='name'?' *':''}</span>${agentFormControl(key,row[key],creating)}</label>`).join('');
  const parent=`<label class="agent-form-field"><span>${agentFormLabels.parent_id}</span><select name="parent_id">${parents.map(([value,label])=>`<option value="${value}" ${String(row.parent_id??0)===value?'selected':''}>${esc(label)}</option>`).join('')}</select></label>`;
  $('#formFields').innerHTML=`<div class="agent-form-fields">${parent}${html}</div><div class="agent-form-error" role="alert"></div><div class="modal-actions"><button type="submit" class="button primary">保存</button><button type="button" class="button ghost" data-agent-form-cancel>取消</button></div>`;form.removeAttribute('aria-busy');
 }catch(error){if(error.name==='AbortError')return;$('#formFields').innerHTML=`<div class="agent-form-error" role="alert">${esc(error.message)}</div><div class="modal-actions"><button type="button" class="button ghost" data-agent-form-retry>重试</button></div>`;form.removeAttribute('aria-busy');$('#formFields [data-agent-form-retry]').onclick=()=>openAgentForm(id,creating);}
}
document.addEventListener('click',event=>{
 const trigger=event.target.closest('#createButton,[data-edit]');if(!trigger||state.view!=='agents')return;if(trigger.matches('[data-edit]')&&!trigger.closest('#content'))return;
 event.preventDefault();event.stopImmediatePropagation();openAgentForm(trigger.id==='createButton'?null:Number(trigger.dataset.edit),trigger.id==='createButton');
},true);
document.addEventListener('click',event=>{const cancel=event.target.closest('[data-agent-form-cancel]');if(cancel){$('#modal').hidden=true;agentFormState.request?.abort();}},true);
document.addEventListener('submit',async event=>{
 const form=event.target;if(form.id!=='editorForm'||form.dataset.agentForm!=='1')return;event.preventDefault();event.stopImmediatePropagation();const fields=form.querySelector('.agent-form-fields'),error=form.querySelector('.agent-form-error');if(!fields||fields.dataset.saving==='1')return;
 const name=form.elements.name?.value.trim();if(!name){error.textContent='主体名称不能为空';form.elements.name?.focus();return;}
 const body=Object.fromEntries(new FormData(form));for(const key of ['parent_id','user_id','role_id','status','game_ad_status','ht_status','is_gx']){if(body[key]==='')delete body[key];else body[key]=Number(body[key]);}if(!body.password)delete body.password;
 fields.dataset.saving='1';form.setAttribute('aria-busy','true');error.textContent='';const controls=[...form.querySelectorAll('input,select,button')];controls.forEach(control=>control.disabled=true);
 try{await api(form.dataset.edit?'/'+form.dataset.edit:'/agents',{method:form.dataset.edit?'PATCH':'POST',body:JSON.stringify(body)});form.dataset.agentForm='';form.dataset.create='';form.dataset.edit='';$('#modal').hidden=true;await load();}
 catch(errorValue){error.textContent=errorValue.message;controls.forEach(control=>control.disabled=false);}finally{delete fields.dataset.saving;form.removeAttribute('aria-busy');}
},true);
