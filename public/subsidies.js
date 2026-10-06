async function renderSubsidies(){await renderReviewPage('subsidies');}

function attachSubsidyCampaigns(){
 const host=document.createElement('details');host.className='subsidy-campaigns';
 host.innerHTML='<summary>补贴活动与每日名额</summary><div class="campaign-content"></div>';
 document.querySelector('#content').prepend(host);
 const content=host.querySelector('.campaign-content');let loaded=false;
 host.addEventListener('toggle',()=>{if(host.open&&!loaded){loaded=true;loadCampaigns();}});
 const current=()=>host.isConnected&&state.view==='subsidies';
 async function loadCampaigns(){
  content.textContent='正在加载活动…';
  try{
   const result=await api('/subsidy-campaigns');if(!current())return;
   content.innerHTML=`<p>每日名额按北京时间重置；拒绝或删除申请不退回当日名额。活动默认关闭，开启前请核对条件。</p>${result.can_write?'<button type="button" data-campaign-new>新建补贴活动</button>':''}<div class="table-wrap"><table class="table"><thead><tr><th>活动</th><th>游戏 ID</th><th>状态</th><th>今日已用 / 总名额</th><th>剩余</th><th>提现门槛</th><th>充值条件</th><th>补贴金额</th><th>审核时限</th><th>操作</th></tr></thead><tbody>${result.items.map(x=>`<tr><td>${esc(x.title)}</td><td>${x.game_id}</td><td>${x.enabled?'开放':'关闭'}</td><td>${x.used} / ${x.daily_quota}</td><td>${x.remaining}</td><td>${(x.withdrawal_cents/100).toFixed(2)}元</td><td>${(x.recharge_cents/100).toFixed(2)}元</td><td>${(x.reward_cents/100).toFixed(2)}元</td><td>${x.review_hours}小时</td><td>${result.can_write?`<button type="button" data-campaign-edit="${x.id}">编辑</button>`:'只读'}</td></tr>`).join('')}</tbody></table></div><div class="campaign-editor"></div>`;
   content.querySelector('[data-campaign-new]')?.addEventListener('click',()=>editCampaign(null));
   content.querySelectorAll('[data-campaign-edit]').forEach(b=>b.onclick=()=>editCampaign(result.items.find(x=>x.id===Number(b.dataset.campaignEdit))));
  }catch(error){if(current()){content.textContent=error.message;const retry=document.createElement('button');retry.textContent='重试';retry.onclick=loadCampaigns;content.append(retry);}}
 }
 function editCampaign(row){
  const defaults={game_id:'',title:'充值补贴',enabled:0,daily_quota:50,withdrawal_cents:500,recharge_cents:600,reward_cents:1200,review_hours:24,instructions:'请上传下载截图、安装来源截图和充值截图；领取补贴前请保留应用。',...row};
  const holder=content.querySelector('.campaign-editor');
  holder.innerHTML=`<form class="campaign-form"><h3>${row?'编辑':'新建'}补贴活动</h3><div class="subsidy-form-fields">${[['title','活动名称','text'],['game_id','游戏 ID','number'],['daily_quota','每日总名额','number'],['withdrawal_cents','当日已确认提现门槛（分）','number'],['recharge_cents','充值条件（分）','number'],['reward_cents','补贴金额（分）','number'],['review_hours','审核时限（小时）','number']].map(([key,label,type])=>`<label class="subsidy-form-field"><span>${label}</span><input name="${key}" type="${type}" value="${esc(defaults[key])}" ${type==='number'?'min="1" step="1"':''} ${key==='title'?'maxlength="128"':''} ${key==='game_id'&&row?'readonly':''} required></label>`).join('')}<label class="subsidy-form-field"><span>活动状态</span><select name="enabled"><option value="0" ${defaults.enabled?'':'selected'}>关闭</option><option value="1" ${defaults.enabled?'selected':''}>开放</option></select></label><label class="subsidy-form-field subsidy-form-full"><span>领取说明</span><textarea name="instructions" maxlength="4000">${esc(defaults.instructions)}</textarea></label></div><p>金额以分填写：500 分 = 5 元；提现资格以服务端已确认转账记录计算。充值条件由审核人员核对截图。</p><p class="campaign-error" role="alert"></p><button type="submit">保存</button> <button type="button" data-campaign-cancel>取消</button></form>`;
  const form=holder.querySelector('form');let busy=false;
  form.querySelector('[data-campaign-cancel]').onclick=()=>{if(!busy)holder.replaceChildren();};
  form.onsubmit=async event=>{
   event.preventDefault();if(busy)return;const body=Object.fromEntries(new FormData(form));
   for(const key of ['game_id','enabled','daily_quota','withdrawal_cents','recharge_cents','reward_cents','review_hours'])body[key]=Number(body[key]);
   busy=true;form.querySelectorAll('button,input,select,textarea').forEach(el=>el.disabled=true);
   try{await api('/subsidy-campaigns'+(row?'/'+row.id:''),{method:row?'PUT':'POST',body:JSON.stringify(body)});if(current())await loadCampaigns();}
   catch(error){if(current()&&form.isConnected)form.querySelector('.campaign-error').textContent=error.message;}
   finally{busy=false;if(form.isConnected)form.querySelectorAll('button,input,select,textarea').forEach(el=>el.disabled=false);}
  };
 }
}

function attachSubsidyPictures(){
 document.querySelectorAll('.subsidy-picture').forEach(link=>link.onclick=event=>{
  if(event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
  event.preventDefault();
  const links=[...link.closest('td').querySelectorAll('.subsidy-picture')];
  showSubsidyPictures(links.map(item=>item.href),links.indexOf(link));
 });
}

function showSubsidyPictures(urls,start){
 if(!urls.length)return;
 document.querySelector('.subsidy-gallery')?.close();
 const dialog=document.createElement('dialog');dialog.className='subsidy-gallery';dialog.setAttribute('aria-label','申请图片预览');
 dialog.innerHTML='<button class="subsidy-gallery-close" aria-label="关闭图片预览">×</button><button class="subsidy-gallery-prev" aria-label="上一张">‹</button><figure><div class="subsidy-gallery-stage"></div><figcaption aria-live="polite"></figcaption></figure><button class="subsidy-gallery-next" aria-label="下一张">›</button>';
 let index=Math.max(0,Math.min(start,urls.length-1)),generation=0;
 const stage=dialog.querySelector('.subsidy-gallery-stage'),caption=dialog.querySelector('figcaption');
 const render=()=>{
  const current=++generation;
  caption.textContent=`${index+1} / ${urls.length}`;
  const status=document.createElement('p');status.className='subsidy-gallery-status';status.setAttribute('role','status');status.textContent='正在加载图片…';
  const img=new Image();img.alt=`申请图片 ${index+1}`;
  img.onload=()=>{if(current===generation){status.remove();img.hidden=false;}};
  img.onerror=()=>{if(current===generation){status.textContent='图片加载失败';status.setAttribute('role','alert');}};
  img.hidden=true;stage.replaceChildren(status,img);img.src=urls[index];
  dialog.querySelector('.subsidy-gallery-prev').hidden=urls.length===1;
  dialog.querySelector('.subsidy-gallery-next').hidden=urls.length===1;
 };
 const move=step=>{index=(index+step+urls.length)%urls.length;render();};
 dialog.querySelector('.subsidy-gallery-prev').onclick=()=>move(-1);
 dialog.querySelector('.subsidy-gallery-next').onclick=()=>move(1);
 dialog.querySelector('.subsidy-gallery-close').onclick=()=>dialog.close();
 dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
 dialog.addEventListener('keydown',event=>{if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();move(event.key==='ArrowLeft'?-1:1);}});
 const onRoute=()=>dialog.close();window.addEventListener('hashchange',onRoute);
 dialog.addEventListener('close',()=>{generation++;window.removeEventListener('hashchange',onRoute);dialog.remove();},{once:true});
 document.body.append(dialog);dialog.showModal();render();dialog.querySelector('.subsidy-gallery-close').focus();
}

function subsidyPictures(value){
 let values=Array.isArray(value)?value:String(value||'').split(',');
 if(typeof value==='string'&&value.trim().startsWith('[')){
  try{const parsed=JSON.parse(value);if(Array.isArray(parsed))values=parsed;}catch{}
 }
 return values.map(raw=>{
  if(typeof raw!=='string'||!raw.trim())return '';
  let url;
  try{url=new URL(raw.trim(),location.origin);if(!['http:','https:'].includes(url.protocol))return '';}catch{return '';}
  return `<a class="subsidy-picture" href="${esc(url.href)}" target="_blank" rel="noopener noreferrer" aria-label="查看申请图片"><img src="${esc(url.href)}" alt="申请图片" loading="lazy"></a>`;
 }).join('');
}

function attachSubsidyBatch(items,summary={}){
 if(state.view!=='subsidies')return;
 const toolbar=document.querySelector('.withdrawal-toolbar');
 const generation=reviewStates.subsidies.generation;
 let busy=false;
 const paid=Number.isFinite(Number(summary.paid))?Number(summary.paid):items.filter(item=>Number(item.status)===1).reduce((sum,item)=>sum+Number(item.price||0),0);
 const pending=Number.isFinite(Number(summary.pending))?Number(summary.pending):items.filter(item=>Number(item.status)===0).reduce((sum,item)=>sum+Number(item.price||0),0);
 toolbar.insertAdjacentHTML('beforeend',`<button data-subsidy-batch="approve" disabled>批量同意</button><button data-subsidy-batch="reject" disabled>批量拒绝</button><span data-subsidy-summary="paid">已补贴：${paid}元</span><span data-subsidy-summary="pending">申请中：${pending}元</span>`);
 const table=document.querySelector('.withdrawal-panel table');
 table.tHead.rows[0].insertAdjacentHTML('afterbegin','<th><input id="subsidySelectAll" type="checkbox" aria-label="全选本页补贴"></th>');
 for(const [index,row] of [...table.tBodies[0].rows].entries()){
  if(!items.length){row.cells[0].colSpan++;continue;}
  row.insertAdjacentHTML('afterbegin',`<td><input type="checkbox" data-subsidy-select="${items[index].id}" aria-label="选择补贴 ${items[index].id}"></td>`);
 }
 const boxes=[...table.querySelectorAll('[data-subsidy-select]')],all=$('#subsidySelectAll');
 const update=()=>{
  const count=boxes.filter(box=>box.checked).length;
  all.checked=boxes.length>0&&count===boxes.length;all.indeterminate=count>0&&count<boxes.length;
  all.disabled=busy||boxes.length===0;boxes.forEach(box=>box.disabled=busy);
  document.querySelectorAll('[data-subsidy-batch]').forEach(button=>button.disabled=busy||count===0);
 };
 all.disabled=boxes.length===0;
 all.onchange=()=>{boxes.forEach(box=>box.checked=all.checked);update();};
 boxes.forEach(box=>box.onchange=update);
 document.querySelectorAll('[data-subsidy-batch]').forEach(button=>button.onclick=async()=>{
  const ids=boxes.filter(box=>box.checked).map(box=>Number(box.dataset.subsidySelect));
  const action=button.dataset.subsidyBatch;
  if(busy||!ids.length)return;
  if(!await withdrawalConfirm(action==='reject'?'确认批量拒绝吗':'确认批量同意吗'))return;
  if(state.view!=='subsidies'||reviewStates.subsidies.generation!==generation)return;
  busy=true;update();
  try{await api('/subsidies/batch-'+(action==='reject'?'refuse':'approve'),{method:'POST',body:JSON.stringify({ids})});if(state.view==='subsidies'&&reviewStates.subsidies.generation===generation)await renderReviewPage('subsidies');}
  catch(error){if(state.view==='subsidies'&&reviewStates.subsidies.generation===generation&&$('#reviewError'))$('#reviewError').textContent=error.message;}
  finally{busy=false;if(state.view==='subsidies'&&reviewStates.subsidies.generation===generation)update();}
 });
}

function subsidyRowActions(row,permissions){
 return `${permissions?.edit===false?'':`<button class="review-edit" data-subsidy-edit="${esc(row.id)}" aria-label="编辑" title="编辑"><i class="shell-icon" aria-hidden="true">&#xf040;</i></button>`} ${permissions?.delete===false?'':`<button class="review-delete" data-subsidy-delete="${esc(row.id)}" aria-label="删除" title="删除"><i class="shell-icon" aria-hidden="true">&#xf1f8;</i></button>`}`;
}

function subsidyFormField(key,label,value,kind='text'){
 const current=esc(value??'');
 if(key==='status')return `<label class="subsidy-form-field"><span>${label}</span><select name="status"><option value="0" ${String(value)==='0'?'selected':''}>申请中</option><option value="1" ${String(value)==='1'?'selected':''}>审核通过</option><option value="4" ${String(value)==='2'||String(value)==='4'?'selected':''}>审核失败</option></select></label>`;
 return `<label class="subsidy-form-field"><span>${label}</span><input name="${key}" type="${kind}" value="${current}" ${kind==='number'?'step="any"':''}></label>`;
}

let subsidyEditorSession=null;
function closeSubsidyForm(){
 if(!subsidyEditorSession)return;
 subsidyEditorSession.request.abort();subsidyEditorSession=null;
 const form=$('#editorForm');form.dataset.subsidyForm='';form.dataset.edit='';form.removeAttribute('aria-busy');$('#modal').hidden=true;
}
async function openSubsidyForm(record){
 const modal=$('#modal'),form=$('#editorForm');if(!modal||!form)return;
 closeSubsidyForm();const session={request:new AbortController(),route:location.hash,busy:false};subsidyEditorSession=session;
 modal.hidden=false;form.dataset.agentForm='';form.dataset.gameForm='';form.dataset.subsidyForm='1';form.dataset.edit='subsidies/'+record.id;form.dataset.create='';$('#modalTitle').textContent='编辑补贴申请';
 const current=()=>subsidyEditorSession===session&&!modal.hidden&&location.hash===session.route;
 $('#formFields').innerHTML='<div class="subsidy-form-loading" role="status">正在加载...</div>';
 try{
  const row=await api('/subsidies/'+record.id,{signal:session.request.signal});if(!current())return;
  $('#formFields').innerHTML=`<div class="subsidy-form-fields">${subsidyFormField('tx_price','提现金额条件（元）',row.tx_price,'number')}${subsidyFormField('price','到账金额（元）',row.price,'number')}${subsidyFormField('receive_name','收件人',row.receive_name)}${subsidyFormField('receive_tel','联系方式',row.receive_tel)}${subsidyFormField('status','状态',row.status)}${subsidyFormField('pics','申请图片',row.pics)}<label class="subsidy-form-field subsidy-form-full"><span>失败原因</span><textarea name="sub_msg" rows="4">${esc(row.sub_msg||'')}</textarea></label></div><div class="subsidy-form-error" role="alert"></div><div class="modal-actions"><button type="submit" class="button primary">保存</button><button type="button" class="button ghost" data-subsidy-form-cancel>取消</button></div>`;
  if(row.campaign){
   const snapshot=document.createElement('section');snapshot.className='campaign-review-snapshot';
   snapshot.innerHTML=`<h3>${esc(row.campaign.title)}</h3><p>申请日：${esc(row.campaign.quota_date)}；当日已确认提现：${(row.campaign.confirmed_withdrawal_cents/100).toFixed(2)}元；充值条件：${(row.campaign.recharge_cents/100).toFixed(2)}元；补贴：${(row.campaign.reward_cents/100).toFixed(2)}元。</p><p>审核截止：${esc(new Date(row.campaign.review_due_at).toLocaleString())} ${row.campaign.overdue?'（已超时）':''}</p><p>${esc(row.campaign.instructions)}</p><div class="campaign-evidence">${[['download_image','下载截图'],['install_image','安装来源截图'],['recharge_image','充值截图']].map(([key,label])=>`<div><strong>${label}</strong>${subsidyPictures(row.campaign.evidence[key])}</div>`).join('')}</div><p>请核对充值金额、应用及安装来源。审核通过不等于支付渠道已确认到账。</p>`;
   form.querySelector('.subsidy-form-fields').before(snapshot);
   for(const key of ['tx_price','price','pics'])form.querySelector(`[name="${key}"]`).readOnly=true;
  }
  session.fields=form.querySelector('.subsidy-form-fields');session.initial=Object.fromEntries(new FormData(form));
 }catch(error){if(current()&&error.name!=='AbortError'){$('#formFields').innerHTML=`<div class="subsidy-form-error" role="alert">${esc(error.message)}</div><button type="button" data-subsidy-retry>重试</button>`;form.querySelector('[data-subsidy-retry]').onclick=()=>openSubsidyForm(record);}}
}

function attachSubsidyCrud(items,s,permissions){
 if(state.view==='subsidies'&&!document.querySelector('.subsidy-campaigns'))attachSubsidyCampaigns();
 const toolbar=document.querySelector('.withdrawal-toolbar'),table=document.querySelector('.withdrawal-panel table');if(!toolbar||!table)return;
 const generation=s.generation,active=()=>table.isConnected&&state.view==='subsidies'&&reviewStates.subsidies===s&&s.generation===generation;let busy=false;
 const edit=document.createElement('button');edit.id='subsidyEdit';edit.disabled=true;edit.innerHTML='<i class="shell-icon" aria-hidden="true">&#xf040;</i> 编辑';edit.hidden=permissions?.edit===false;
 const remove=document.createElement('button');remove.id='subsidyDelete';remove.disabled=true;remove.innerHTML='<i class="shell-icon" aria-hidden="true">&#xf1f8;</i> 删除';remove.hidden=permissions?.delete===false;
 if(permissions?.review===false)toolbar.querySelectorAll('[data-subsidy-batch]').forEach(button=>button.hidden=true);
 const anchor=toolbar.querySelector('[data-subsidy-batch="approve"]');if(anchor){toolbar.insertBefore(edit,anchor);toolbar.insertBefore(remove,anchor);}else toolbar.append(edit,remove);
 const selected=()=>[...table.querySelectorAll('[data-subsidy-select]:checked')].map(box=>items.find(row=>String(row.id)===box.dataset.subsidySelect)).filter(Boolean);
 const sync=()=>{const rows=selected();edit.disabled=busy||rows.length!==1;remove.disabled=busy||rows.length===0;};
 table.addEventListener('change',event=>{if(event.target.matches('[data-subsidy-select],#subsidySelectAll'))sync();});sync();
 edit.onclick=()=>{const rows=selected();if(rows.length===1)openSubsidyForm(rows[0]);};
 const destroy=async(ids)=>{
  if(busy||!active()||!ids.length)return;busy=true;sync();
  const controls=[...document.querySelector('.withdrawal-panel').querySelectorAll('button,input')].filter(el=>!el.disabled);controls.forEach(el=>el.disabled=true);
  try{
   if(!await withdrawalConfirm(ids.length===1?'确认删除这条补贴记录吗':`确认删除选中的 ${ids.length} 条补贴记录吗`)||!active())return;
   await api(ids.length===1?'/subsidies/'+ids[0]:'/subsidies/batch-delete',ids.length===1?{method:'DELETE'}:{method:'POST',body:JSON.stringify({ids})});
   if(active())await renderReviewPage('subsidies');
  }catch(error){if(active())$('#reviewError').textContent=error.message;}
  finally{busy=false;controls.forEach(el=>el.disabled=false);sync();}
 };
 remove.onclick=()=>destroy(selected().map(row=>row.id));
 document.querySelectorAll('[data-subsidy-edit]').forEach(button=>button.onclick=()=>{const row=items.find(item=>String(item.id)===button.dataset.subsidyEdit);if(row)openSubsidyForm(row);});
 document.querySelectorAll('[data-subsidy-delete]').forEach(button=>button.onclick=()=>destroy([Number(button.dataset.subsidyDelete)]));
}

document.addEventListener('click',event=>{
 if(event.target.closest('[data-subsidy-form-cancel],#closeModal,#cancelModal,[data-edit],[data-detail],#createButton'))closeSubsidyForm();
},true);
window.addEventListener('hashchange',closeSubsidyForm);
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&subsidyEditorSession){event.preventDefault();closeSubsidyForm();}});

document.addEventListener('submit',async event=>{
 const form=event.target;if(form.id!=='editorForm'||form.dataset.subsidyForm!=='1')return;
 event.preventDefault();event.stopImmediatePropagation();const session=subsidyEditorSession;
 const current=()=>subsidyEditorSession===session&&session?.fields?.isConnected&&!$('#modal').hidden&&location.hash===session.route;
 if(!current()||session.busy)return;
 const error=form.querySelector('.subsidy-form-error'),values=Object.fromEntries(new FormData(form));
 for(const key of ['tx_price','price'])if(values[key].trim()===''||!Number.isFinite(Number(values[key]))){error.textContent='金额必须是有效数字';return;}
 const body=Object.fromEntries(Object.entries(values).filter(([key,value])=>value!==session.initial[key]));
 for(const key of ['status','tx_price','price'])if(key in body)body[key]=Number(body[key]);
 if(body.status===4){body.sub_msg=values.sub_msg.trim();if(!body.sub_msg){error.textContent='拒绝补贴时必须填写原因';return;}}
 if(!Object.keys(body).length){closeSubsidyForm();return;}
 session.busy=true;error.textContent='';form.setAttribute('aria-busy','true');const controls=[...form.querySelectorAll('input,select,textarea,button')];controls.forEach(control=>control.disabled=true);
 try{await api('/'+form.dataset.edit,{method:'PATCH',body:JSON.stringify(body)});if(current()){closeSubsidyForm();await renderReviewPage('subsidies');}}
 catch(errorValue){if(current()){error.textContent=errorValue.message;controls.forEach(control=>control.disabled=false);}}finally{session.busy=false;if(current())form.removeAttribute('aria-busy');}
},true);
