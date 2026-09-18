const profileState={tableState:null,session:null};
let profileIdentityGeneration=0;
function profileLogTime(value) {
 if(!value)return '';const raw=String(value),date=new Date(/[zZ]$|[+-]\d\d:\d\d$/.test(raw)?raw:raw+'Z');
 if(Number.isNaN(date.getTime()))return raw;
 return new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(date);
}
function profileAvatar(value){return /^\/api\/member-images\/[0-9a-f]{48}\.png$/.test(value||'')?value:'/assets/img/avatar.png';}
function updateProfileIdentity(user){
 profileIdentityGeneration++;
 const name=user.display_name||user.username||'';
 document.querySelectorAll('#accountName,.target-user-label').forEach(node=>node.textContent=name);
 const avatar=profileAvatar(user.avatar);document.querySelectorAll('.target-avatar').forEach(node=>node.src=avatar);
 document.body.style.setProperty('--profile-avatar',`url("${avatar}")`);
}
function profileLogCell(row,column,interactive){
 const key=column[0],value=row[key]??'';
 if(key==='created_at')return esc(profileLogTime(value));
 if(key==='path'){
  let href='';try{const url=new URL(value,location.origin);if(value&&['http:','https:'].includes(url.protocol))href=url.href;}catch{}
  return `<div class="profile-log-link"><input type="text" aria-label="请求路径" value="${esc(value)}"><a ${href?`href="${esc(href)}" target="_blank" rel="noopener"`:''} class="profile-link-button" title="打开链接" aria-label="打开链接"><i class="shell-icon" aria-hidden="true">&#xf0c1;</i></a></div>`;
 }
 if(key==='ip')return interactive?`<button type="button" class="game-user-cell-search" title="点击搜索 ${esc(value)}">${esc(value)}</button>`:`<a>${esc(value)}</a>`;
 return esc(value);
}
function mountProfileLogActions(panel,s){
 const form=panel.querySelector('form'),tools=panel.querySelector('.game-user-table-tools');let timer;
 panel.querySelector('section').classList.add('profile-log-panel');panel.querySelector('[role=alert]').id='profileLogError';
 panel.querySelector('.game-user-results').id='profileLogTable';panel.querySelector('.game-user-pagination').id='profileLogPagination';
 panel.querySelector('[data-action=refresh]').id='profileLogRefresh';panel.querySelector('[data-action=search]').hidden=true;
 form.insertAdjacentHTML('afterbegin',`<input type="hidden" name="q" value="${esc(s.filters.q||'')}">`);
 const search=document.createElement('input');search.id='profileLogSearch';search.type='search';search.placeholder='搜索';search.setAttribute('aria-label','搜索操作日志');search.value=s.filters.q||'';tools.prepend(search);
 const submit=()=>{clearTimeout(timer);form.elements.q.value=search.value.trim();form.requestSubmit();};
 search.oninput=()=>{clearTimeout(timer);timer=setTimeout(submit,500);};
 search.onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();submit();}};
 for(const [selector,icon] of [['[data-action=cards]','list-alt'],['.game-user-columns summary','th'],['.game-user-export summary','export']]){
  const control=panel.querySelector(selector);control.title=control.getAttribute('aria-label');
  control.innerHTML=`<i class="glyphicon glyphicon-${icon}" aria-hidden="true"></i>${control.tagName==='SUMMARY'?' <span class="caret"></span>':''}`;
 }
 return {paint(){panel.querySelectorAll('.game-user-cards article>div').forEach(row=>{
  const title=row.querySelector('strong');title.textContent=title.textContent.slice(0,-1);row.hidden=!row.querySelector('span').innerHTML;
 });},destroy(){clearTimeout(timer);}};
}
async function renderProfile(){
 profileState.session?.destroy();
 const session={closed:false,request:new AbortController(),upload:null,controller:null},route=location.hash,generation=pageLoadGeneration;
 const current=()=>!session.closed&&profileState.session===session&&location.hash===route&&pageLoadGeneration===generation;
 session.destroy=()=>{session.closed=true;session.request.abort();session.upload?.abort();session.controller?.destroy();};profileState.session=session;
 $('#content').innerHTML='<div class="profile-loading" role="status">加载中</div>';
 let user;
 try{user=await api('/auth/me',{signal:session.request.signal},'/api');}
 catch(error){if(current()&&error.name!=='AbortError'){
  $('#content').innerHTML='<div class="profile-loading"><p role="alert"></p><button type="button">重试</button></div>';
  $('#content [role=alert]').textContent=error.message;$('#content button').onclick=renderProfile;
 }return;}
 if(!current())return;updateProfileIdentity(user);
 $('#content').innerHTML=`<div class="profile-layout"><section class="profile-card"><header>个人资料</header><div class="profile-card-body"><form id="profileForm">
  <div class="profile-avatar-container"><img class="profile-avatar" src="${esc(profileAvatar(user.avatar))}" alt="头像"><button type="button" id="profileAvatarUpload" aria-label="上传头像">点击编辑</button><input type="file" id="profileAvatarFile" accept="image/png,image/jpeg,image/webp,image/gif" hidden></div>
  <h2 id="profileName">${esc(user.display_name)}</h2><input type="hidden" name="avatar" value="${esc(profileAvatar(user.avatar))}">
  <label>用户名:<input value="${esc(user.username)}" disabled></label><label>Mobile:<input value="${esc(user.mobile||'')}" disabled></label>
  <label>昵称:<input name="display_name" value="${esc(user.display_name)}" maxlength="128" required></label>
  <label>密码:<input name="password" type="password" autocomplete="new-password" placeholder="不修改密码请留空"></label>
  <div class="profile-form-actions"><button type="submit" class="profile-primary">提交</button> <button type="reset">重置</button></div><p id="profileMessage" role="status"></p>
 </form></div></section><section class="profile-log-section"><div class="profile-log-tab"><i class="shell-icon" aria-hidden="true">&#xf03a;</i> 操作日志</div><div id="profileLogs"></div></section></div>`;
 const form=$('#profileForm'),message=$('#profileMessage'),file=$('#profileAvatarFile'),avatar=$('.profile-avatar');let busy=false,savedAvatar=profileAvatar(user.avatar);
 const cancelUpload=()=>{session.upload?.abort();session.upload=null;form.querySelector('[type=submit]').disabled=busy;};
 $('#profileAvatarUpload').onclick=()=>file.click();
 file.onchange=async()=>{
  const image=file.files[0];if(!image||busy)return;cancelUpload();message.textContent='';
  if(!['image/png','image/jpeg','image/webp','image/gif'].includes(image.type)){message.textContent='请选择 PNG、JPEG、WebP 或 GIF 图片';file.value='';return;}
  if(image.size>2*1024*1024){message.textContent='图片不能超过 2MB';file.value='';return;}
  const request=new AbortController();session.upload=request;form.querySelector('[type=submit]').disabled=true;
  try{
   const data=await api('/auth/avatar',{method:'POST',headers:{'Content-Type':image.type},body:image,signal:request.signal},'/api');
   if(!current()||session.upload!==request)return;
   form.elements.avatar.value=data.url;avatar.src=profileAvatar(data.url);message.textContent='上传成功';
  }catch(error){if(current()&&session.upload===request&&error.name!=='AbortError')message.textContent=error.message;}
  finally{if(session.upload===request){session.upload=null;if(current())form.querySelector('[type=submit]').disabled=busy;}file.value='';}
 };
 form.onreset=()=>{cancelUpload();message.textContent='';form.elements.avatar.value=savedAvatar;avatar.src=savedAvatar;};
 form.onsubmit=async event=>{
  event.preventDefault();if(busy||session.upload||!current())return;
  const body=Object.fromEntries(new FormData(form));if(!body.password)delete body.password;
  const controls=[...form.querySelectorAll('input,button')].filter(node=>!node.disabled);busy=true;controls.forEach(node=>node.disabled=true);form.setAttribute('aria-busy','true');message.textContent='';
  try{
   const saved=await api('/auth/me',{method:'PATCH',body:JSON.stringify(body)},'/api');if(!current())return;
   updateProfileIdentity(saved);$('#profileName').textContent=saved.display_name;
   form.elements.display_name.value=form.elements.display_name.defaultValue=saved.display_name;
   savedAvatar=profileAvatar(saved.avatar);form.elements.avatar.value=savedAvatar;avatar.src=savedAvatar;
   form.elements.password.value='';message.textContent='保存成功';await session.controller.refresh();
  }catch(error){if(current())message.textContent=error.message;}
  finally{busy=false;if(current()){controls.forEach(node=>node.disabled=false);form.removeAttribute('aria-busy');}}
 };
 const tab={endpoint:'/auth/operations',apiPrefix:'/api',absolute:true,state:profileState.tableState,filterColumns:[],
  columns:[['id','ID'],['title','标题'],['path','链接'],['ip','ip'],['created_at','操作时间','date']],
  cell:profileLogCell,exportCell:(row,column)=>column[0]==='path'?'<div><input></div>':profileLogCell(row,column),exportSkipFirst:true,mountActions:mountProfileLogActions,
  exportFileName:()=>'export_'+new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date())};
 session.controller=mountGameUserTable($('#profileLogs'),null,tab);profileState.tableState=session.controller.state;
 await session.controller.refresh();
}
window.addEventListener('hashchange',()=>{if(!/^#(?:profile|general)(?:$|[?&])/.test(location.hash))profileState.session?.destroy();});
