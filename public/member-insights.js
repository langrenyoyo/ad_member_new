// Operational panels with audited category review; API content is always escaped.
document.addEventListener('click', event=>{
 const button=event.target.closest('[data-member-insights]');if(!button)return;
 const dialog=document.createElement('dialog');dialog.style.cssText='width:min(1200px,95vw);max-height:90vh;overflow:auto';
 dialog.innerHTML='<button type="button" data-close>关闭档案</button><div data-host></div>';
 dialog.querySelector('[data-close]').onclick=()=>dialog.close();
 dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();
 const host=dialog.querySelector('[data-host]');mountMemberInsights(host);
 host.querySelector('[data-insight] input').value=button.dataset.memberInsights;
 host.querySelector('[data-insight]').requestSubmit();
});
function mountMemberInsights(host) {
 host.insertAdjacentHTML('beforeend', '<section class="panel"><h2>会员档案与设备观测</h2><form data-insight><label>会员 ID <input name="id" type="number" min="1" required></label><button>查看档案</button></form><p data-insight-status role="status"></p><div data-insight-result></div><form data-observations><label>游戏 ID <input name="game" type="number" min="1" required></label><button>查看设备观测</button></form><p>仅观察，不自动封禁。样本由 APP 授权上报；定位稳定不等于设备无人操作。未验证设备不参与设备去重统计。</p><div data-observation-result></div></section>');
 const status=host.querySelector('[data-insight-status]');let memberVersion=0,boardVersion=0;
 const money=cents=>(Number(cents||0)/100).toFixed(2);
 host.querySelector('[data-insight]').onsubmit=async event=>{
  event.preventDefault();const id=Number(new FormData(event.target).get('id')),version=++memberVersion;
  const area=host.querySelector('[data-insight-result]');area.replaceChildren();status.textContent='加载中';
  try{
   const d=await api(`/members/${id}/insights`);if(!host.isConnected||version!==memberVersion)return;
   area.innerHTML=`<h3>会员档案 #${esc(d.id)} · ${esc(d.name||'')} · ${d.status===1?'启用':'停用'}</h3><p>等级：${esc(['用户','V1','V2','代理'][d.level]||'未知')} · 上级：${esc(d.parent_id||'无')} · 邀请码：${esc(d.invite_code||'未生成')} · 直属成员：${esc(d.direct_count)}</p><table><tbody>${[['可用金币',d.coin],['冻结金币',d.frozen_coin],['累计佣金（已计入钱包）',d.commission_total_coin],['今日佣金（北京时间）',d.commission_today_coin],['为各级上级贡献金币',d.contribution_coin],['实际支付提现（元）',money(d.paid_withdrawal_cents)],['广告展示次数（今日）',`${d.ad_views}（${d.ad_views_today}）`]].map(([k,v])=>`<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join('')}</tbody></table><p>广告分类说明：${esc(d.category_reason)}；不据此推断个人兴趣。</p><div data-ad-page></div>`;
   const categories={unknown:'未知',game:'游戏',social:'交友',finance:'金融理财',ecommerce:'电商购物',other:'其他'};
   const summary=document.createElement('p');
   const labels=d.label_summary;
   summary.textContent=labels?`广告标签：${categories[labels.label]||'未知'}；样本 ${labels.total}/${labels.window}；${Object.entries(labels.counts).map(([k,v])=>`${categories[k]||k} ${v}`).join('，')}。${labels.reason}`:'暂无标签统计';
   area.querySelector('[data-ad-page]').before(summary);
   async function ads(offset=0){
    try {const result=await api(`/members/${id}/ad-settlements?limit=20&offset=${offset}`);if(!host.isConnected||version!==memberVersion)return;
     const target=area.querySelector('[data-ad-page]');
     target.innerHTML=`<h4>广告会话 ${esc(result.total)} 条</h4><button data-prev>上一页</button><button data-next>下一页</button><div style="overflow:auto"><table><thead><tr><th>会话</th><th>平台</th><th>结算状态</th><th>用户奖励（金币）</th><th>分配及事件</th></tr></thead><tbody>${result.items.map(a=>`<tr><td>${esc(a.id)}</td><td>${esc(a.provider)}</td><td>${esc(a.status)}</td><td>${esc(a.user_reward_coin)}</td><td><details><summary>查看记录</summary>${(a.client_metadata||[]).map(x=>`<p>${esc(x.event)} / ${esc(x.network)} / ${esc(x.app_name||x.title||"unknown")} (client)</p><details><summary>SDK metadata</summary><pre>${esc(JSON.stringify(x,null,2))}</pre></details>`).join('')}${a.allocations.map(r=>`<p>会员 ${esc(r.member_id)} / ${esc(r.kind)} / ${esc(r.coin)} 金币</p><pre>${esc(JSON.stringify(r.rule,null,2))}</pre>`).join('')}${a.events.map(e=>`<p>${esc(e.time)} ${esc(e.type)}</p>`).join('')}</details></td></tr>`).join('')}</tbody></table></div>`;
     target.querySelector('[data-prev]').disabled=offset===0;target.querySelector('[data-next]').disabled=offset+result.items.length>=result.total;
     target.querySelector('[data-prev]').onclick=()=>ads(Math.max(0,offset-20));target.querySelector('[data-next]').onclick=()=>ads(offset+20);
     target.querySelectorAll('tbody tr').forEach((tr,index)=>{
      const ad=result.items[index],cell=tr.lastElementChild,form=document.createElement('form');
      form.innerHTML=`<p>复核类别：${esc(categories[ad.category]||'未知')} · ${esc(ad.review?.title||'未命名')}</p><select name="category">${Object.entries(categories).map(([k,v])=>`<option value="${k}" ${ad.category===k?'selected':''}>${v}</option>`).join('')}</select><input name="title" placeholder="广告名称" maxlength="255" value="${esc(ad.review?.title||'')}"><input name="reason" placeholder="复核依据（必填）" maxlength="1000" required value="${esc(ad.review?.reason||'')}"><button>保存人工复核（超级管理员）</button><span role="status"></span>`;
      cell.append(form);
      form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('button'),message=form.querySelector('[role=status]');button.disabled=true;
       try{const data=new FormData(form);await api(`/ad-sessions/${encodeURIComponent(ad.id)}/category-review`,{method:'PUT',body:JSON.stringify({category:data.get('category'),title:data.get('title'),reason:data.get('reason'),expected_revision:ad.review?.revision||0})});if(version===memberVersion)host.querySelector('[data-insight]').requestSubmit();}
       catch(error){message.textContent=error.message;}finally{button.disabled=false;}
      };
     });
    }catch(error){if(version===memberVersion)status.textContent=error.message;}
   }
   const more=document.createElement('div');
   more.innerHTML=`<p>收款账号：${esc(d.alipay_masked||'未绑定')}</p><p>近 30 天同设备关联会员（最多 50 人）：${esc((d.related_member_ids_30d||[]).join(', ')||'无')}</p><p>直属会员（最多 50 人）：${esc((d.direct_members||[]).map(x=>'#'+x.id).join(', ')||'无')}</p>`;
   area.append(more);status.textContent='档案已加载';await ads();
  }catch(error){if(version===memberVersion)status.textContent=error.message;}
 };
 host.querySelector('[data-observations]').onsubmit=async event=>{
  event.preventDefault();const game=Number(new FormData(event.target).get('game')),version=++boardVersion;
  const area=host.querySelector('[data-observation-result]');area.replaceChildren();
  async function load(offset=0){try{
   const d=await api(`/games/${game}/observation-board?limit=50&offset=${offset}`);if(!host.isConnected||version!==boardVersion)return;
   const value=v=>v==null?'无法判定':esc(v);
   area.innerHTML=`<p>最近 10 分钟活跃会员 ${esc(d.total)} 人；充电与位置稳定仅统计最近一小时有效采样段。</p><button data-prev>上一页</button><button data-next>下一页</button><div style="overflow:auto"><table><thead><tr>${['会员','可信设备','IP','同 IP 设备','同设备账号','100 米内其他设备','电量','充电','有效观测秒','充电占比','位置稳定秒','样本/更新'].map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${d.items.map(r=>`<tr>${[r.member_id,r.device_id,r.ip,r.same_ip_verified_devices,r.same_device_accounts,r.nearby_verified_devices,r.battery+'%',r.charging?'是':'否',r.observed_seconds,r.charging_ratio==null?null:(r.charging_ratio*100).toFixed(1)+'%',r.location_stable_seconds,`${r.samples} / ${r.updated_at}`].map(v=>`<td>${value(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
   area.querySelector('[data-prev]').disabled=offset===0;area.querySelector('[data-next]').disabled=offset+d.items.length>=d.total;
   area.querySelector('[data-prev]').onclick=()=>load(Math.max(0,offset-50));area.querySelector('[data-next]').onclick=()=>load(offset+50);
  }catch(error){if(version===boardVersion)status.textContent=error.message;}}
  await load();
 };
}
