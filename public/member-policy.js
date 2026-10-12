async function mountMemberPolicy(host) {
 host.innerHTML='<section class="panel"><h2>APP 业务规则</h2><form data-load><label>游戏 ID <input name="game" type="number" min="1" required></label><button>加载</button></form><p data-status role="status"></p><div data-form></div><button data-ledger type="button">&#26597;&#30475;&#22870;&#21169;&#19982;&#20998;&#20323;&#27969;&#27700;</button><div data-ledgers></div><h3>会员等级与使用情况</h3><form data-member><label>会员 ID <input name="member" type="number" min="1" required></label><select name="level"><option value="0">普通用户</option><option value="1">V1</option><option value="2">V2</option><option value="3">代理</option></select><button>保存等级</button><input name="date" type="date"><button type="button" data-usage>查看使用情况</button></form><div data-report></div></section>';
 if(typeof mountMemberInsights==='function')mountMemberInsights(host);
 const status=host.querySelector('[data-status]'), area=host.querySelector('[data-form]');
 let game=0,generation=0,ledgerOffset=0;
 host.querySelector('[data-ledger]').textContent='查看奖励与分佣流水';
 const labels={require_alipay:'强制绑定支付宝',require_invite:'强制邀请码',require_usage:'要求应用使用情况授权',reset_login_block:'清机额度耗尽后限制登录 24 小时',reward_enabled:'启用自定义奖励策略',commission_enabled:'启用分佣（按最终奖励另计）',whitelist_risk_exempt:'白名单豁免设备风控'};
 host.querySelector('[data-load]').onsubmit=async e=>{
  e.preventDefault();const version=++generation;game=Number(new FormData(e.target).get('game'));area.replaceChildren();ledgerOffset=0;host.querySelector('[data-ledgers]').replaceChildren();
  try {
   const loadedGame=game;
   const p=await api(`/games/${loadedGame}/member-policy`);p.commission_enabled=p.commission_enabled??p.reward_enabled;if(!host.isConnected||version!==generation)return;
   area.innerHTML=`<form data-save>${Object.entries(labels).map(([k,l])=>`<label style="display:block"><input type="checkbox" name="${k}" ${p[k]?'checked':''}>${l}</label>`).join('')}
   <label>邀请最低等级 <select name="invite_min_level">${['用户','V1','V2','代理'].map((l,i)=>`<option value="${i}" ${p.invite_min_level===i?'selected':''}>${l}</option>`).join('')}</select></label>
   <label>奖励基数 <select name="reward_basis"><option value="verified_cny_ecpm">可信人民币 ECPM</option><option value="fixed_ecpm">后台自定义 ECPM</option></select></label>
   ${[['fixed_ecpm','自定义 ECPM'],['coins_per_yuan','每元折算金币'],['whitelist_multiplier','白名单奖励倍率'],['max_reward','单次奖励上限'],['agent_member_id','全应用代理会员 ID（0 不指定）'],['announcement_version','公告版本']].map(([k,l])=>`<label style="display:block">${l}<input type="number" min="0" step="any" name="${k}" value="${esc(p[k])}" required></label>`).join('')}
   <fieldset><legend>各平台释放比例（0–1）</legend>${Object.entries({kuaishou:'快手',gdt:'优量汇',csj:'穿山甲',baidu:'百度',other:'其他'}).map(([k,l])=>`<label>${l}<input name="rate_${k}" type="number" min="0" max="1" step="0.001" value="${esc(p.network_rates[k])}" required></label>`).join('')}</fieldset>
   <fieldset><legend>各级分佣比例（从最终用户奖励另计，合计不超过 1）</legend>${['用户','V1','V2','代理'].map((l,i)=>`<label>${l}<input name="commission_${i}" type="number" min="0" max="1" step="0.001" value="${esc(p.commission_rates[i])}" required></label>`).join('')}</fieldset>
   <fieldset><legend>命中以下设备信号时阻断</legend>${['emulator','root','hook','developer','accessibility','bluetooth'].map(k=>`<label><input name="signal" type="checkbox" value="${k}" ${p.block_signals.includes(k)?'checked':''}>${esc(k)}</label>`).join('')}</fieldset>
   <label style="display:block">广告源对应平台（每行：数字广告源ID=平台代码）<textarea name="sources" rows="5">${esc(Object.entries(p.source_networks).map(([k,v])=>`${k}=${v}`).join('\n'))}</textarea></label>
   <label style="display:block">公告内容<textarea name="announcement" rows="5" maxlength="5000">${esc(p.announcement)}</textarea></label><button>保存规则</button></form>`;
   area.querySelector('[name=reward_basis]').value=p.reward_basis;
   const readiness=document.createElement('p');area.prepend(readiness);
   api(`/games/${loadedGame}/reward-readiness`).then(r=>{if(version===generation)readiness.textContent=r.message||'';}).catch(error=>{if(version===generation)readiness.textContent=error.message;});
   const tierBox=document.createElement('fieldset');
   tierBox.innerHTML=`<legend>ECPM 分段释放</legend><label><input type="checkbox" name="tier_enabled" ${p.tier_enabled?'checked':''}>启用分段释放</label><p>以本次可信人民币 ECPM 为依据，阈值包含上限；超过末档沿用末档比例。替代平台比例，仍受白名单倍率和单次上限约束。</p><label>阈值（元/千次）<input name="tier_upper" placeholder="50,100,200,300,500,1000,2000,3000,4000" value="${esc((p.ecpm_tiers||[]).map(x=>x.upper).join(','))}"></label><label>比例（%，0–1000）<input name="tier_percent" placeholder="200,70,70,70,65,60,50,40,30" value="${esc((p.ecpm_tiers||[]).map(x=>x.percent).join(','))}"></label><pre data-tier-table></pre><label>试算 ECPM<input name="preview_ecpm" type="number" min="0" max="1000000" step="any" value="40"></label><label>广告源 ID<input name="preview_source"></label><label><input name="preview_white" type="checkbox">白名单试算</label><button type="button" data-preview>试算金币（不保存）</button><p data-preview-result></p>`;
   area.querySelector('form').append(tierBox);
   const labelNames={game:'游戏',social:'交友',finance:'金融理财',ecommerce:'电商购物',other:'其他'};
   const labelBox=document.createElement('fieldset');
   labelBox.innerHTML=`<legend>会员广告标签与固定奖励</legend><p>按最近已展示广告统计，人工复核类别；未知计入分母。超过占比且样本充足才生效。固定金币覆盖 ECPM 比例及白名单倍率，仍受单次上限约束；只影响新领取广告。</p><label><input name="label_rewards_enabled" type="checkbox" ${p.label_rewards_enabled?'checked':''}>启用标签固定奖励</label><label>最近广告数<input name="label_window" type="number" min="1" max="1000" value="${esc(p.label_window??100)}" required></label><label>最少样本数<input name="label_min_samples" type="number" min="1" max="1000" value="${esc(p.label_min_samples??10)}" required></label><label>占比阈值（严格超过，0.5–小于 1）<input name="label_threshold" type="number" min="0.5" max="0.999999" step="any" value="${esc(p.label_threshold??'0.5')}" required></label>${Object.entries(labelNames).map(([key,name])=>`<label>${name}固定金币（留空沿用 ECPM）<input name="label_${key}" type="number" min="0" max="1000000" step="0.000001" value="${esc(p.label_rewards?.[key]??'')}"></label>`).join('')}<label>试算标签<select name="preview_label"><option value="unknown">未知</option>${Object.entries(labelNames).map(([key,name])=>`<option value="${key}">${name}</option>`).join('')}</select></label>`;
   area.querySelector('form').append(labelBox);
   function tiers(){
    const left=tierBox.querySelector('[name=tier_upper]').value.trim(),right=tierBox.querySelector('[name=tier_percent]').value.trim();
    if(!left&&!right)return [];
    const parse=s=>s.replaceAll('，',',').split(',').map(v=>{v=v.trim();if(!/^\d+(\.\d+)?$/.test(v))throw Error('阈值和比例必须是非负数，不能有空项');return v;});
    const upper=parse(left),percent=parse(right);if(upper.length!==percent.length||upper.length>100)throw Error('阈值与比例数量必须一致，最多 100 档');
    return upper.map((v,i)=>{if(Number(v)>1000000||Number(percent[i])>1000||(i&&Number(v)<=Number(upper[i-1])))throw Error('阈值须严格递增且不超过 100 万，比例不超过 1000%');return {upper:v,percent:percent[i]};});
   }
   tierBox.oninput=()=>{try{const list=tiers();tierBox.querySelector('[data-tier-table]').textContent=list.map((x,i)=>`${i?list[i-1].upper+' <':'0 ≤'} ECPM ≤ ${x.upper}：${x.percent}%`).concat(list.length?[`ECPM > ${list.at(-1).upper}：${list.at(-1).percent}%`]:[]).join('\n');}catch(error){tierBox.querySelector('[data-tier-table]').textContent=error.message;}};
   tierBox.oninput();
   function buildBody(form){
    const data=new FormData(form),body={...p};Object.keys(labels).forEach(k=>body[k]=data.has(k));
    for(const k of ['invite_min_level','fixed_ecpm','coins_per_yuan','whitelist_multiplier','max_reward','agent_member_id','announcement_version'])body[k]=Number(data.get(k));
    body.reward_basis=data.get('reward_basis');body.announcement=data.get('announcement');body.block_signals=data.getAll('signal');
    body.network_rates=Object.fromEntries(Object.keys(p.network_rates).map(k=>[k,Number(data.get('rate_'+k))]));
    body.commission_rates=[0,1,2,3].map(i=>Number(data.get('commission_'+i)));
    body.source_networks=Object.fromEntries(String(data.get('sources')).split('\n').filter(l=>l.trim()).map(l=>{const parts=l.trim().split('=');if(parts.length!==2)throw Error('广告来源格式应为 ID=平台代码');return parts.map(v=>v.trim());}));
    body.label_rewards_enabled=data.has('label_rewards_enabled');
    body.label_window=Number(data.get('label_window'));body.label_min_samples=Number(data.get('label_min_samples'));body.label_threshold=data.get('label_threshold');
    body.label_rewards=Object.fromEntries(Object.keys(labelNames).filter(k=>data.get('label_'+k)!=='').map(k=>[k,data.get('label_'+k)]));
    body.tier_enabled=data.has('tier_enabled');body.ecpm_tiers=tiers();return body;
   }
   tierBox.querySelector('[data-preview]').onclick=async()=>{const output=tierBox.querySelector('[data-preview-result]');try{const form=area.querySelector('form'),data=new FormData(form);const r=await api('/member-policy/reward-preview',{method:'POST',body:JSON.stringify({policy:buildBody(form),ecpm:data.get('preview_ecpm'),source_id:data.get('preview_source'),is_white:data.has('preview_white'),ad_label:data.get('preview_label')})});output.textContent=`试算奖励 ${r.coin} 金币（不写入余额）`;}catch(error){output.textContent=error.message;}};
   area.querySelector('form').onsubmit=async event=>{
    event.preventDefault();const form=event.target, button=form.querySelector('button');button.disabled=true;
    try {
     const body=buildBody(form);
     await api(`/games/${loadedGame}/member-policy`,{method:'PUT',body:JSON.stringify(body)});if(version===generation)status.textContent='规则已保存';
    }catch(error){if(version===generation)status.textContent=error.message;}finally{button.disabled=false;}
   };
  }catch(error){status.textContent=error.message;}
 };
 async function loadLedger(offset=0) {
  const version=generation, currentGame=game;
  try{if(!currentGame)throw Error('Please load a game first');const r=await api(`/games/${currentGame}/reward-ledgers?limit=50&offset=${offset}`);
   if(version!==generation||!host.isConnected)return;
   ledgerOffset=offset;
   const area=host.querySelector('[data-ledgers]');
   area.innerHTML='<p data-page></p><button data-prev type="button">上一页</button><button data-next type="button">下一页</button><table><thead><tr><th>ID</th><th>广告</th><th>来源会员</th><th>受益会员</th><th>类型</th><th>金币</th></tr></thead><tbody>'+r.items.map(i=>`<tr><td>${esc(i.id)}</td><td>${esc(i.ad_session_id)}</td><td>${esc(i.member_id)}</td><td>${esc(i.beneficiary_id)}</td><td>${esc(i.kind)}</td><td>${esc(i.amount)}</td></tr>`).join('')+'</tbody></table>';
   area.querySelector('[data-page]').textContent=`${r.items.length?offset+1:0} - ${offset+r.items.length} / ${r.total??r.items.length}`;
   area.querySelector('[data-prev]').disabled=offset===0;
   area.querySelector('[data-next]').disabled=offset+r.items.length>=(r.total??r.items.length);
   area.querySelector('[data-prev]').onclick=()=>loadLedger(Math.max(0,ledgerOffset-50));
   area.querySelector('[data-next]').onclick=()=>loadLedger(ledgerOffset+50);
  }catch(error){status.textContent=error.message;}
 }
 host.querySelector('[data-ledger]').onclick=()=>loadLedger();
 const member=host.querySelector('[data-member]');
 member.onsubmit=async e=>{e.preventDefault();try{const d=new FormData(member);const r=await api(`/members/${Number(d.get('member'))}/level`,{method:'PUT',body:JSON.stringify({level:Number(d.get('level'))})});status.textContent='等级已保存，邀请码：'+r.invite_code;}catch(error){status.textContent=error.message;}};
 member.querySelector('[data-usage]').onclick=async()=>{try{const d=new FormData(member);const r=await api(`/members/${Number(d.get('member'))}/usage?report_date=${encodeURIComponent(d.get('date'))}`);host.querySelector('[data-report]').innerHTML='<table><thead><tr><th>应用包名</th><th>使用分钟</th><th>估算打开次数</th></tr></thead><tbody>'+r.items.map(i=>`<tr><td>${esc(i.package_name)}</td><td>${esc((i.duration_ms/60000).toFixed(1))}</td><td>${esc(i.opens)}</td></tr>`).join('')+'</tbody></table>';}catch(error){status.textContent=error.message;}};
}
