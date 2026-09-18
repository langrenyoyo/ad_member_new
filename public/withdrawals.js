const reviewStates={withdrawals:{status:'',page:1},subsidies:{status:'',page:1}};
async function renderWithdrawals(){await renderReviewPage('withdrawals');}

function withdrawalRowActions(row,permissions={}){
 const editable=permissions.edit!==false&&Number(row.status)===0;
 const review=permissions.row_review===true&&Number(row.status)===0;
 const blacklist=permissions.blacklist!==false;
 return `${blacklist?`<button class="withdraw-blacklist" data-withdrawal-blacklist="${esc(row.id)}" aria-label="拉黑">拉黑</button>`:''}${editable?`<button class="review-edit" data-withdrawal-edit="${esc(row.id)}" aria-label="编辑" title="编辑"><i class="shell-icon" aria-hidden="true">&#xf040;</i></button>`:''}${review?`<button class="withdraw-approve" data-review-action="approve" data-review-id="${esc(row.id)}">同意</button><button class="withdraw-reject" data-review-action="refuse" data-review-id="${esc(row.id)}">拒绝</button><button class="withdraw-reject" data-review-action="reject" data-review-id="${esc(row.id)}">有理由拒绝</button>`:''}`;
}

document.addEventListener('click',event=>{
 if(event.target.closest('[data-withdrawal-form-cancel],#closeModal,#cancelModal'))closeWithdrawalForm();
},true);
window.addEventListener('hashchange',closeWithdrawalForm);
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&withdrawalEditorSession){event.preventDefault();closeWithdrawalForm();}});

document.addEventListener('submit',async event=>{
 const form=event.target;if(form.id!=='editorForm'||form.dataset.withdrawalForm!=='1')return;
 event.preventDefault();event.stopImmediatePropagation();const session=withdrawalEditorSession;
 const current=()=>withdrawalEditorSession===session&&session?.fields?.isConnected&&!$('#modal').hidden&&location.hash===session.route;
 if(!current()||session.busy)return;
 const error=form.querySelector('.subsidy-form-error'),values=Object.fromEntries(new FormData(form));
 if(values.exchange_value.trim()===''||!Number.isFinite(Number(values.exchange_value))||Number(values.exchange_value)<0){error.textContent='金额必须是有效的非负数字';return;}
 const body=Object.fromEntries(Object.entries(values).filter(([key,value])=>value!==session.initial[key]));
 if('exchange_value' in body)body.exchange_value=Number(body.exchange_value);
 if('exchange_type' in body)body.exchange_type=Number(body.exchange_type);
 if(!Object.keys(body).length){closeWithdrawalForm();return;}
 session.busy=true;error.textContent='';form.setAttribute('aria-busy','true');const controls=[...form.querySelectorAll('input,select,textarea,button')];controls.forEach(control=>control.disabled=true);
 try{await api('/'+form.dataset.edit,{method:'PATCH',body:JSON.stringify(body)});if(current()){closeWithdrawalForm();await renderReviewPage('withdrawals');}}
 catch(errorValue){if(current()){error.textContent=errorValue.message;controls.forEach(control=>control.disabled=false);}}
 finally{session.busy=false;if(current())form.removeAttribute('aria-busy');}
},true);

let withdrawalEditorSession=null;
function closeWithdrawalForm(){
 if(!withdrawalEditorSession)return;
 withdrawalEditorSession.request.abort();withdrawalEditorSession=null;
 const form=$('#editorForm');form.dataset.withdrawalForm='';form.dataset.edit='';form.removeAttribute('aria-busy');$('#modal').hidden=true;
}
function withdrawalFormField(key,label,value,kind='text'){
 const current=esc(value??'');
 if(key==='exchange_type')return `<label class="subsidy-form-field"><span>${label}</span><select name="exchange_type"><option value="0" ${String(value)==='0'?'selected':''}>默认</option><option value="1" ${String(value)==='1'?'selected':''}>支付宝</option><option value="2" ${String(value)==='2'?'selected':''}>微信</option></select></label>`;
 return `<label class="subsidy-form-field"><span>${label}</span><input name="${key}" type="${kind}" value="${current}" ${kind==='number'?'step="any"':''}></label>`;
}
async function openWithdrawalForm(record){
 const modal=$('#modal'),form=$('#editorForm');if(!modal||!form)return;
 closeWithdrawalForm();const session={request:new AbortController(),route:location.hash,busy:false};withdrawalEditorSession=session;
 modal.hidden=false;form.dataset.subsidyForm='';form.dataset.withdrawalForm='1';form.dataset.edit='withdrawals/'+record.id;form.dataset.create='';$('#modalTitle').textContent='编辑提现记录';
 const current=()=>withdrawalEditorSession===session&&!modal.hidden&&location.hash===session.route;
 $('#formFields').innerHTML='<div class="subsidy-form-loading" role="status">正在加载...</div>';
 try{
  const row=await api('/withdrawals/'+record.id,{signal:session.request.signal});if(!current())return;
  const fields=[['good_name','商品名称'],['device_manufacturer','手机型号'],['receive_name','收件人'],['receive_tel','联系方式'],['receive_address','收货地址'],['exchange_value','金额','number'],['exchange_type','提现方式'],['delivery_name','快递名称'],['delivery_no','快递单号']];
  $('#formFields').innerHTML=`<div class="subsidy-form-fields withdrawal-form-fields">${fields.map(([key,label,kind])=>withdrawalFormField(key,label,row[key],kind||'text')).join('')}<label class="subsidy-form-field subsidy-form-full"><span>备注</span><textarea name="remark" rows="4">${esc(row.remark||'')}</textarea></label><label class="subsidy-form-field subsidy-form-full"><span>失败原因</span><textarea name="sub_msg" rows="3">${esc(row.sub_msg||'')}</textarea></label></div><div class="subsidy-form-error" role="alert"></div><div class="modal-actions"><button type="submit" class="button primary">保存</button><button type="button" class="button ghost" data-withdrawal-form-cancel>取消</button></div>`;
  session.initial=Object.fromEntries(new FormData(form));session.fields=form.querySelector('.withdrawal-form-fields');
 }catch(error){if(current()&&error.name!=='AbortError'){$('#formFields').innerHTML=`<div class="subsidy-form-error" role="alert">${esc(error.message)}</div><button type="button" data-withdrawal-retry>重试</button>`;form.querySelector('[data-withdrawal-retry]').onclick=()=>openWithdrawalForm(record);}}
}

function attachWithdrawalCrud(items,s,permissions={}){
 const toolbar=document.querySelector('.withdrawal-toolbar'),table=document.querySelector('.withdrawal-panel table');if(!toolbar||!table)return;
 const generation=s.generation,active=()=>table.isConnected&&state.view==='withdrawals'&&reviewStates.withdrawals===s&&s.generation===generation;let busy=false;
 const edit=document.createElement('button');edit.id='withdrawalEdit';edit.disabled=true;edit.hidden=permissions.edit===false;edit.innerHTML='<i class="shell-icon" aria-hidden="true">&#xf040;</i> 编辑';
 const anchor=toolbar.querySelector('#withdrawalBatchRefuse');if(anchor)toolbar.insertBefore(edit,anchor);else toolbar.append(edit);
 const selected=()=>[...table.querySelectorAll('[data-withdrawal-select]:checked')].map(box=>items.find(row=>String(row.id)===box.dataset.withdrawalSelect)).filter(Boolean);
 const sync=()=>{const rows=selected();edit.disabled=busy||rows.length!==1||Number(rows[0]?.status)!==0;};
 table.addEventListener('change',event=>{if(event.target.matches('[data-withdrawal-select],#withdrawalSelectAll'))sync();});sync();
 edit.onclick=()=>{const rows=selected();if(rows.length===1)openWithdrawalForm(rows[0]);};
 document.querySelectorAll('[data-withdrawal-edit]').forEach(button=>button.onclick=()=>{const row=items.find(item=>String(item.id)===button.dataset.withdrawalEdit);if(row)openWithdrawalForm(row);});
}
async function renderReviewPage(kind){
 if(!reviewStates[kind].filters)reviewStates[kind].filters=reviewDefaultFilters();
 const generation=reviewStates[kind].generation=(reviewStates[kind].generation||0)+1;
 const s=reviewStates[kind],labels=[['','全部'],['0','申请中'],['1','审核通过'],['4','审核失败']];
 if(!s.pageSize)s.pageSize=reviewPageSize();
 const all=s.pageSize==='All';
 const p=new URLSearchParams({limit:all?200:s.pageSize,offset:all?0:(s.page-1)*s.pageSize});if(s.status!=='')p.set('status',s.status);
 p.set('sort',s.sort||'id');p.set('order',s.order||'desc');
 try{
 reviewFilterParams(kind,p);
 if(kind==='withdrawals'&&s.agentScope)p.set('agent_id',String(s.agentScope));
 const d=await api('/'+kind+'?'+p);if(state.view!==kind||reviewStates[kind]!==s||generation!==s.generation)return;
 if(all){
  while(d.items.length<d.total){
   if(state.view!==kind||reviewStates[kind]!==s||generation!==s.generation)return;
   p.set('offset',String(d.items.length));const next=await api('/'+kind+'?'+p);
   if(next.total!==d.total||!next.items.length)throw Error('数据已变化，请刷新后重试');
   d.items.push(...next.items);
  }
  if(d.items.length!==d.total||new Set(d.items.map(row=>row.id)).size!==d.items.length)throw Error('数据已变化，请刷新后重试');
  p.set('offset','0');
 }
 if(state.view!==kind||reviewStates[kind]!==s||generation!==s.generation)return;
 const lastPage=all?1:Math.max(1,Math.ceil(d.total/s.pageSize));
 if(s.page>lastPage){s.page=lastPage;return renderReviewPage(kind);}
 function cell(row,key){
  if(kind==='subsidies'&&key==='review_actions')return subsidyRowActions(row,d.permissions);
  if(kind==='withdrawals'&&key==='review_actions')return withdrawalRowActions(row,d.permissions);
  if((kind==='withdrawals'||kind==='subsidies')&&key==='behavior')return `<button class="review-behavior" data-member-behavior="single" data-member-id="${esc(row.user_id)}" data-game-id="${esc(row.game_id)}">单APP行为</button>`;
  if((kind==='withdrawals'&&['user_id','username','game_name','receive_name','receive_tel'].includes(key))||(kind==='subsidies'&&['user_id','username','receive_name','receive_tel'].includes(key)))return `<button class="review-search-value" data-review-search="${key==='game_name'?'game_id':key}" data-review-value="${esc(key==='game_name'?row.game_id:row[key])}">${esc(row[key]??'')}</button>`;
  if((kind==='withdrawals'&&['vip','exchange_type','status','plan_status'].includes(key))||(kind==='subsidies'&&['vip','status'].includes(key))){
   const number=Number(row[key]),tone=key==='vip'?({0:'success',1:'warning',2:'danger'})[number]:key==='status'?({0:'info',1:'primary',2:'danger',4:'danger'})[number]:({0:'info',1:'primary',2:'danger'})[number];
   return tone?`<span class="review-badge review-badge-${tone}">${esc(value(row,key)??'')}</span>`:baseCell(row,key);
  }
  return baseCell(row,key);
 }
 const cols=kind==='withdrawals'?[['id','Id'],['user_id','会员ID'],['good_name','商品名称'],['exchange_value','金额'],['device_manufacturer','手机型号'],['receive_name','收件人'],['receive_tel','联系方式'],['exchange_type','提现方式'],['status','状态'],['plan_status','定时'],['sub_msg','失败原因'],['review_actions','操作'],['check_status_txt','作弊审查'],['created_at','申请时间']]:[['id','Id'],['user_id','会员ID'],['tx_price','提现金额条件(元)'],['price','到账金额(元)'],['sub_msg','备注'],['status','状态'],['created_at','申请时间'],['review_actions','操作']];
 cols.splice(2,0,['username','\u8d26\u53f7'],['vip','VIP'],['parent_name','\u4e0a\u7ea7\u6635\u79f0'],['game_name','\u6e38\u620f\u540d\u79f0']);
 if(kind==='withdrawals')cols.splice(cols.findIndex(([key])=>key==='game_name'),0,['behavior','用户行为']);
 if(kind==='subsidies')cols.splice(cols.findIndex(([key])=>key==='price')+1,0,['behavior','用户行为']);
 if(kind==='subsidies')cols.splice(cols.findIndex(([key])=>key==='tx_price')+1,0,['pics','\u7533\u8bf7\u56fe\u7247']);
 if(kind==='subsidies'){
  cols.splice(cols.findIndex(([key])=>key==='price'),0,['receive_name','收件人'],['receive_tel','联系方式']);
  cols.splice(cols.findIndex(([key])=>key==='parent_name'),0,['parent_id','上级Id',false],['parent_username','上级账号',false]);
  cols.splice(cols.findIndex(([key])=>key==='tx_price'),0,['agent_name','代理商名称',false],['name','昵称',false]);
  cols.splice(cols.findIndex(([key])=>key==='sub_msg'),1);
  cols.splice(cols.findIndex(([key])=>key==='status')+1,0,['sub_msg','失败原因']);
  cols.splice(cols.findIndex(([key])=>key==='review_actions'),1);
  cols.splice(cols.findIndex(([key])=>key==='created_at'),0,['review_actions','操作']);
  cols.push(['updated_at','更新时间',false]);
 }
 if(kind==='withdrawals'){
  cols.splice(cols.findIndex(([key])=>key==='parent_name'),0,['parent_id','上级Id',false],['parent_username','上级账号',false]);
  cols.splice(cols.findIndex(([key])=>key==='good_name'),0,['agent_name','代理商名称',false],['name','昵称',false]);
  cols.splice(cols.findIndex(([key])=>key==='exchange_type'),0,['receive_address','收货地址',false],['delivery_name','快递名称',false],['delivery_no','快递单号',false],['remark','备注',false]);
  cols.splice(cols.findIndex(([key])=>key==='status'),0,['is_true','内部号',false]);
  cols.splice(cols.findIndex(([key])=>key==='review_actions'),0,['reason','拒绝原因',false]);
  cols.push(['updated_at','更新时间',false]);
 }
 const value=(r,k)=>['created_at','updated_at'].includes(k)?profileLogTime(r[k]):k==='exchange_value'?Number(r[k]||0)/10+'元':k==='vip'?(r[k]==null?'':'V'+r[k]):k==='exchange_type'?({0:'默认',1:'支付宝',2:'微信'}[r[k]]??r[k]):k==='plan_status'?({0:'默认',1:'转账中',2:'已转账'}[r[k]]??r[k]):k==='status'?({0:'申请中',1:'审核通过',2:'审核失败',4:'审核失败'}[r[k]]):r[k];
 const baseCell=(r,k)=>k==='review_actions'?(kind==='withdrawals'?withdrawalRowActions(r,d.permissions):`<button class="review-edit" data-subsidy-edit="${esc(r.id)}" aria-label="编辑" title="编辑">✎</button><button class="review-delete" data-subsidy-delete="${esc(r.id)}" aria-label="删除" title="删除">▣</button>`):k==='is_true'?esc(({0:'否',1:'是'})[r[k]]??''):k==='pics'?subsidyPictures(r[k]):esc(value(r,k)??'');
 $('#content').innerHTML=`<section class="withdrawal-panel"><div class="withdrawal-tabs">${labels.map(([v,l])=>`<button data-review-status="${v}" class="${s.status===v?'active':''}">${l}</button>`).join('')}</div>${reviewFilterMarkup(kind)}<div class="withdrawal-toolbar"><button id="reviewRefresh" aria-label="刷新">⟳</button></div><p id="reviewError" role="alert"></p><div class="table-wrap"><table class="ads-table"><thead><tr>${cols.map(([k,l,visible])=>`<th data-review-column="${k}" ${visible===false?'hidden':''}>${l}</th>`).join('')}</tr></thead><tbody>${d.items.map(r=>`<tr>${cols.map(([k,,visible])=>`<td data-review-cell="${k}" ${visible===false?'hidden':''}>${cell(r,k)}</td>`).join('')}</tr>`).join('')||`<tr><td colspan="${cols.length}">没有找到匹配的记录</td></tr>`}</tbody></table></div><div class="pagination"></div></section>`;
 attachReviewFilters(kind);
 document.querySelectorAll('[data-review-search]').forEach(button=>button.onclick=()=>{s.filters[button.dataset.reviewSearch]=button.dataset.reviewValue;s.page=1;renderReviewPage(kind);});
 if(kind==='withdrawals'&&s.agentScope)lockAgentScopeFilter(document.querySelector('#reviewFilters'));
 if(kind==='subsidies'){attachSubsidyBatch(d.items,d.summary);attachSubsidyCrud(d.items,s,d.permissions);}
 if(kind==='subsidies')attachSubsidyPictures();
 if(kind==='withdrawals'){attachWithdrawalSelection(d.items,d.summary,d.permissions);attachWithdrawalCrud(d.items,s,d.permissions);}
 attachWithdrawalSorting(kind);
 attachWithdrawalColumns(cols,kind);
 attachReviewCardView(cols,kind);
 attachReviewExport(kind,cols,d.items,p,cell);
 $('#reviewFilters').dataset.reviewKind=kind;
 $('#reviewRefresh').onclick=()=>renderReviewPage(kind);
 attachReviewPagination(kind,d.total,d.items.length);
 document.querySelectorAll('[data-review-status]').forEach(b=>b.onclick=()=>{s.status=b.dataset.reviewStatus;s.filters.status=s.status;s.page=1;renderReviewPage(kind);});
 document.querySelectorAll('[data-review-action]').forEach(b=>b.onclick=async()=>{
 const action=b.dataset.reviewAction,reason=action==='reject'?prompt('请输入驳回原因',''):'';if(reason===null)return;
 if(action==='reject'&&!reason.trim()){$('#reviewError').textContent='驳回原因不能为空';return;}
 if(kind==='withdrawals'&&action!=='reject'&&!await withdrawalConfirm(action==='approve'?'确认同意吗':'确认拒绝吗'))return;
 if(state.view!==kind||reviewStates[kind]!==s||generation!==s.generation)return;
 const buttons=[...b.closest('tr').querySelectorAll('[data-review-action]')];buttons.forEach(button=>button.disabled=true);
 const payload=action==='reject'?(kind==='subsidies'?{message:reason.trim()}:{reason:reason.trim()}):{};
 try{await api('/'+kind+'/'+b.dataset.reviewId+'/'+action,{method:'POST',body:JSON.stringify(payload)});if(state.view===kind&&reviewStates[kind]===s)await renderReviewPage(kind);}catch(e){if(state.view===kind&&reviewStates[kind]===s&&generation===s.generation&&$('#reviewError'))$('#reviewError').textContent=e.message;buttons.forEach(button=>button.disabled=false);}
 });
 }catch(e){if(state.view===kind&&reviewStates[kind]===s&&generation===s.generation){const error=$('#reviewError');if(error)error.innerHTML=`${esc(e.message)} <button id="reviewRetry">重试</button>`;else $('#content').innerHTML=`<div class="error-state" role="alert">${esc(e.message)} <button id="reviewRetry">重试</button></div>`;if($('#reviewRetry'))$('#reviewRetry').onclick=event=>{event.currentTarget.disabled=true;renderReviewPage(kind);};}}
}
