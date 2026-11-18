async function renderDeviceBlocks(){
 const host=document.querySelector('#content');
 host.innerHTML=`<section class="panel"><h2>设备拦截记录</h2><p>记录实际被拒绝的请求。设备校验服务异常不代表设备作弊。历史记录仅展示当时已保存的拦截事件。</p>
 <form data-block-filter class="ad-settings-grid">
 <label>游戏 ID<input name="game_id" type="number" min="1" value="1"></label>
 <label>会员 ID<input name="member_id" type="number" min="1"></label>
 <label>拦截类型<select name="code"><option value="">全部</option>${Object.entries({daily_limit:'每日广告限次',legacy_daily_limit:'历史每日限次',rolling_limit:'24小时额度耗尽',cooldown:'24小时限制期',device_signals:'设备风险信号',check_required:'缺少有效校验',check_missing:'校验不存在',check_expired:'校验过期或已使用',check_rate_limit:'校验请求过频',verification_failed:'设备校验失败或服务异常',retry_mismatch:'重试凭证不匹配',device_banned:'设备已禁用'}).map(([v,l])=>`<option value="${v}">${l}</option>`).join('')}</select></label>
 <label>开始时间（本地）<input name="start" type="datetime-local"></label><label>结束时间（本地）<input name="end" type="datetime-local"></label>
 <button class="button primary">查询 / 刷新</button></form><p data-error role="alert"></p><div data-block-table></div>
 <button data-prev>上一页</button> <span data-page></span> <button data-next>下一页</button></section>`;
 const form=host.querySelector('form'), table=host.querySelector('[data-block-table]'), error=host.querySelector('[data-error]');
 let offset=0, version=0, filters=new URLSearchParams({game_id:'1'});
 const signals={emulator:'模拟器',root:'Root权限',hook:'Hook注入',developer:'开发者模式',accessibility:'无障碍服务',bluetooth:'蓝牙'};
 async function refresh(){
  const current=++version;error.textContent='';table.setAttribute('aria-busy','true');
  host.querySelector('[data-prev]').disabled=true;host.querySelector('[data-next]').disabled=true;
  try{
   const q=new URLSearchParams(filters);q.set('limit','20');q.set('offset',offset);
   const result=await api('/device-risk/blocks?'+q);
   if(current!==version||!table.isConnected||state.view!=='device-blocks')return;
   table.innerHTML=`<div style="overflow:auto"><table class="table"><thead><tr>${['时间（北京时间）','游戏','会员 / 昵称','设备编号','拦截原因','补充说明','请求页面'].map(s=>`<th>${s}</th>`).join('')}</tr></thead><tbody>${result.items.map(row=>{
    const c=row.context||{}, details=[];
    if(c.risk_reason)details.push(c.risk_reason);
    if(c.signals?.length)details.push('命中：'+c.signals.map(x=>signals[x]||x).join('、')+'（客户端上报）');
    if(c.limit!=null||c.daily_limit!=null)details.push('上限：'+(c.limit??c.daily_limit)+(c.used!=null?'，已用：'+c.used:''));
    if(c.blocked_until)details.push('限制截止：'+new Date(/Z$|[+]\d\d:\d\d$/.test(c.blocked_until)?c.blocked_until:c.blocked_until+'Z').toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}));
    return '<tr>'+[new Date(row.created_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}),row.game_name+' #'+row.game_id,'#'+row.member_id+' '+(row.nickname||''),row.device_id?'#'+row.device_id:'未完成设备识别',row.reason,details.join('；')||'—',row.path||'历史记录未保存'].map(x=>`<td>${esc(x)}</td>`).join('')+'</tr>';
   }).join('')||'<tr><td colspan="7">暂无符合条件的拦截记录</td></tr>'}</tbody></table></div>`;
   host.querySelector('[data-page]').textContent=`第 ${Math.floor(offset/20)+1} 页，共 ${result.total} 条`;
   host.querySelector('[data-prev]').disabled=offset===0;host.querySelector('[data-next]').disabled=offset+20>=result.total;
  }catch(e){if(current===version&&table.isConnected){error.textContent=e.message;table.replaceChildren();}}
  finally{if(current===version)table.removeAttribute('aria-busy');}
 }
 form.onsubmit=e=>{e.preventDefault();filters=new URLSearchParams();for(const [k,v] of new FormData(form)){if(v)filters.set(k,['start','end'].includes(k)?new Date(v).toISOString():v);}offset=0;refresh();};
 host.querySelector('[data-prev]').onclick=()=>{offset=Math.max(0,offset-20);refresh();};
 host.querySelector('[data-next]').onclick=()=>{offset+=20;refresh();};
 await refresh();
}
