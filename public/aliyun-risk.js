async function mountAliyunRisk(host){
 host.innerHTML=`<section class="panel"><h2>清机与双清广告风控</h2><p>同一阿里云设备出现新安装实例时标记为疑似清数据或重装。不能保证识别所有恢复出厂设置。</p><form data-picker><label>游戏 ID <input name="game" type="number" min="1" required list="riskGameOptions"></label><datalist id="riskGameOptions"></datalist><button class="button primary">加载配置</button></form><p data-message role="status"></p><div data-settings></div><div data-devices></div></section>`;
 const message=host.querySelector('[data-message]'),settings=host.querySelector('[data-settings]'),devices=host.querySelector('[data-devices]');
 let gid=0,offset=0,writable=false,generation=0;
 try{const result=await api('/games?limit=200');if(!host.isConnected)return;host.querySelector('datalist').innerHTML=(result.items||[]).map(g=>`<option value="${esc(g.id)}">${esc(g.name)}</option>`).join('');}catch(e){message.textContent=e.message;}
 async function loadDevices(version){
  const result=await api(`/device-risk/devices?game_id=${gid}&limit=20&offset=${offset}`);
  if(!host.isConnected||version!==generation)return;
  devices.innerHTML=`<h3>阿里云已校验设备（${esc(result.total)}）</h3><div style="overflow:auto"><table class="table"><thead><tr><th>设备代码（哈希）</th><th>关联会员</th><th>风险状态 / 原因</th><th>今日批准次数</th><th>风险有效期</th><th>人工处置</th></tr></thead><tbody>${result.items.map(d=>`<tr><td title="${esc(d.device_key)}">#${esc(d.id)}<br>${esc(d.device_key.slice(0,16))}…</td><td>${esc(d.member_ids.join(', '))}</td><td>${d.suspected_reset?'风险设备':'正常'}<br>${esc(d.reason||'—')}<br>${esc(d.tags.join(', '))}</td><td>${esc(d.used_today)}</td><td>${esc(d.risk_until||'—')}</td><td><form data-device="${esc(d.id)}"><select name="mode" ${writable?'':'disabled'}>${[['auto','自动判定'],['allow','人工放行'],['restrict','人工标记风险']].map(([v,l])=>`<option value="${v}" ${v===d.override?'selected':''}>${l}</option>`).join('')}</select><input name="reason" placeholder="填写处置原因" maxlength="200" required ${writable?'':'disabled'}><button ${writable?'':'disabled'}>保存处置</button></form></td></tr>`).join('')||'<tr><td colspan="6">暂无已校验设备</td></tr>'}</tbody></table></div><button data-prev ${offset===0?'disabled':''}>上一页</button> <span>${offset+1} / ${esc(result.total)}</span> <button data-next ${offset+20>=result.total?'disabled':''}>下一页</button>`;
  for(const [selector,delta] of [['[data-prev]',-20],['[data-next]',20]])devices.querySelector(selector).onclick=async()=>{offset+=delta;try{await loadDevices(version);}catch(e){message.textContent=e.message;}};
  devices.querySelectorAll('[data-device]').forEach(form=>form.onsubmit=async event=>{
   event.preventDefault();const button=form.querySelector('button');button.disabled=true;
   try{await api(`/device-risk/devices/${form.dataset.device}`,{method:'PATCH',body:JSON.stringify(Object.fromEntries(new FormData(form)))});message.textContent='设备处置已保存并记录审计';await loadDevices(version);}catch(e){message.textContent=e.message;}finally{button.disabled=!writable;}
  });
 }
 host.querySelector('[data-picker]').onsubmit=async event=>{
  event.preventDefault();gid=Number(new FormData(event.target).get('game'));offset=0;const version=++generation;
  settings.innerHTML='';devices.innerHTML='';message.textContent='加载中…';
  try{
   const rule=await api(`/games/${gid}/device-risk`);if(!host.isConnected||version!==generation)return;
   writable=rule.can_write;message.textContent=rule.aliyun_configured?'服务器已配置阿里云凭据（服务可用性以实际校验为准）':'服务器尚未配置阿里云凭据，无法开启识别';
   settings.innerHTML=`<form data-rule><fieldset ${writable?'':'disabled'}><div class="ad-settings-grid"><label>清机风险识别 <input type="checkbox" name="enabled" ${rule.enabled?'checked':''}></label><label>双清风险用户广告限次 <input type="checkbox" name="limit_enabled" ${rule.limit_enabled?'checked':''}></label><label>每日广告上限（0 表示禁止）<input type="number" name="daily_limit" min="0" max="10000" required value="${esc(rule.daily_limit)}"></label><label>风险持续天数<input type="number" name="risk_days" min="1" max="365" required value="${esc(rule.risk_days)}"></label><label>阿里云清机标签（可选，逗号分隔）<input name="reset_tags" value="${esc(rule.reset_tags.join(','))}" placeholder="仅填写已向阿里云确认的标签代码"></label></div><p>按北京时间每日成功批准的广告申请数限次；同设备共享额度，同时检查账号额度。失败广告不退还次数，重试同一申请不重复计数。人工放行仅豁免本设备限次，仍须校验。</p><button class="button primary">保存风控配置</button></fieldset></form>`;
   settings.querySelector('form').onsubmit=async e=>{
    e.preventDefault();const f=e.target,v=new FormData(f),button=f.querySelector('button');button.disabled=true;
    const body={enabled:v.has('enabled'),limit_enabled:v.has('limit_enabled'),daily_limit:Number(v.get('daily_limit')),risk_days:Number(v.get('risk_days')),reset_tags:String(v.get('reset_tags')).split(/[,，\s]+/).filter(Boolean)};
    try{await api(`/games/${gid}/device-risk`,{method:'PUT',body:JSON.stringify(body)});message.textContent='风控配置已保存';}catch(error){message.textContent=error.message;}finally{button.disabled=false;}
   };
   await loadDevices(version);
  }catch(e){if(version===generation)message.textContent=e.message;}
 };
}
