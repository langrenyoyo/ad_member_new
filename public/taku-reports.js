function mountTakuReports(host) {
 const panel=document.createElement('section');panel.className='panel';
 panel.innerHTML=`<h2>TAKU 用户收益核对</h2><p>按 TAKU 报表预估收益与设备分摊收益比较，标记疑似核减，不代表最终结算扣减。仅超级管理员可操作。</p>
 <form data-query><label>游戏 ID <input name="game" type="number" min="1" required></label>
 <label>报表日期（UTC+8）<input name="day" type="date" required></label><label>会员 ID（可选）<input name="member" type="number" min="1"></label><button>查询</button></form>
 <form data-sync><button>从 TAKU 同步所选日期</button></form>
 <form data-rule><label>比较基准 <select name="basis"><option value="backend_estimate">后台 SDK 展示预估</option><option value="taku_estimate">TAKU 报表预估</option></select></label><label>超过比例 % <input name="threshold_percent" type="number" min="0" max="100" step="0.01" value="20" required></label>
 <label>最低预估金额（报表币种）<input name="min_estimate" type="number" min="0" step="0.000001" value="0.01" required></label>
 <label>最低展示次数 <input name="min_impressions" type="number" min="1" value="3" required></label><button>保存规则</button></form>
 <form data-import><label>设备明细 CSV <input name="file" type="file" accept=".csv" required></label>
 <label>数据阶段 <select name="stage"><option value="preliminary">次日初步</option><option value="rechecked">D+2 已重新获取</option></select></label><button>导入并核对</button></form>
 <p>导入文件必须属于所选应用、日期和 UTC+8；全文件替换当日最新版本，不能上传分页片段。暂无 OAID 自动关联，未匹配用户需人工核对。</p>
 <p role="status" data-status></p><div data-results style="overflow:auto"></div>`;
 host.append(panel);const status=panel.querySelector('[data-status]'),area=panel.querySelector('[data-results]');
 const selection=()=>{const f=panel.querySelector('[data-query]');if(!f.reportValidity())throw Error('请先选择游戏和日期');const d=new FormData(f);return {game:Number(d.get('game')),day:d.get('day')};};
 const labels={waiting_report:'等待报表（不按零收益计算）',preliminary:'初步报表',rechecked:'补齐后复核',unmatched:'用户未匹配',shared_device_review:'多账号设备待核对',missing_estimate:'缺少预估收益',insufficient_sample:'样本不足',normal:'正常',preliminary_alert:'初步差异预警',suspected_reduction:'疑似核减'};
 async function load(){const {game,day}=selection();const member=panel.querySelector('[name=member]').value;const d=await api(`/games/${game}/taku-reports?day=${encodeURIComponent(day)}${member?'&member_id='+encodeURIComponent(member):''}`);if(!panel.isConnected)return;
 status.textContent=`${labels[d.status]||d.status} · 异常用户 ${(d.flagged_members||[]).length} · ${d.updated_at||''}`;
 if(d.rule)for(const [k,v] of Object.entries(d.rule))panel.querySelector('[data-rule]').elements[k].value=v;
 area.innerHTML='<table><thead><tr>'+['会员','广告位','广告平台 ID','币种','展示数','TAKU 预估','报表收益','差额','差异率 %','标记'].map(x=>`<th>${esc(x)}</th>`).join('')+'</tr></thead><tbody>'+d.items.map(r=>`<tr ${r.flagged?'style="background:#fff0f0"':''}>`+[r.member_id||r.user_id||'未匹配',r.placement_id,r.network_id,r.currency,r.impressions,r.estimate,r.revenue,r.difference,r.reduction_percent===null?'—':Number(r.reduction_percent).toFixed(2),labels[r.status]||r.status].map(v=>`<td>${esc(v)}</td>`).join('')+'</tr>').join('')+'</tbody></table>';}
 for(const form of panel.querySelectorAll('form'))form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('button');button.disabled=true;status.textContent='处理中…';try{
  const {game,day}=selection();
  if(form.hasAttribute('data-sync')){const result=await api(`/games/${game}/taku-reports/sync?day=${encodeURIComponent(day)}`,{method:'POST'});if(result.status!=='imported')throw Error(({waiting_report:'TAKU 暂无报表，保留原有结果',permission_rejected:'TAKU 设备报表权限不足',signature_rejected:'TAKU 签名失败',unsupported_response:'报表返回格式尚未支持，需核对原始协议',rate_limited:'TAKU 限流，请稍后重试'})[result.status]||'同步失败，请稍后重试');}
  if(form.hasAttribute('data-rule')){const body=Object.fromEntries(new FormData(form));body.min_impressions=Number(body.min_impressions);await api(`/games/${game}/taku-reports/rule`,{method:'PUT',body:JSON.stringify(body)});}
  if(form.hasAttribute('data-import')){const data=new FormData(form),file=data.get('file');if(file.size>5_000_000)throw Error('文件不得超过 5 MB');await api(`/games/${game}/taku-reports/import`,{method:'POST',body:JSON.stringify({day,stage:data.get('stage'),csv_text:await file.text()})});}
  await load();
 }catch(error){status.textContent=error.message||'操作失败';}finally{button.disabled=false;}};
}
