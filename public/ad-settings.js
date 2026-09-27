const adSettingsState={generation:0};

const adSettingLabels={
  title:'\u5e7f\u544a\u8054\u76df\u8bbe\u7f6e',
  provider:'\u5e7f\u544a\u8054\u76df',
  appId:'\u8054\u76df App ID',
  rewarded:'\u6fc0\u52b1\u5e7f\u544a\u4f4d ID',
  interstitial:'\u63d2\u5c4f\u5e7f\u544a\u4f4d ID',
  banner:'Banner \u5e7f\u544a\u4f4d ID',
  rewardCoin:'\u6fc0\u52b1\u5956\u52b1\u91d1\u5e01',
  cooldown:'\u5e7f\u544a\u51b7\u5374\u79d2\u6570',
  enabled:'\u914d\u7f6e\u72b6\u6001',
  on:'\u542f\u7528',
  off:'\u505c\u7528',
  save:'\u4fdd\u5b58\u914d\u7f6e',
  refresh:'\u5237\u65b0',
  saving:'\u4fdd\u5b58\u4e2d...',
  saved:'\u4fdd\u5b58\u6210\u529f',
  failed:'\u4fdd\u5b58\u5931\u8d25',
};

function adSettingsField(label,name,value,type='text',extra=''){
  return `<label class="ad-settings-field"><span>${esc(label)}</span><input name="${esc(name)}" type="${type}" value="${esc(value??'')}" ${extra}></label>`;
}

function adSettingsCard(game,config){
  const placements=config?.placements||{};
  const rewarded=placements.rewarded||{},interstitial=placements.interstitial||{},banner=placements.banner||{};
  const enabled=Boolean(config?.enabled);
  return `<form class="panel ad-settings-card" data-ad-game="${esc(game.id)}">
    <div class="panel-head"><div><h2>${esc(game.name||'-')}</h2><p class="muted">\u6e38\u620f ID: ${esc(game.id)} &middot; \u4e3b\u4f53 ID: ${esc(game.agent_id??'-')}</p></div><span class="ad-settings-status ${enabled?'enabled':'disabled'}">${enabled?adSettingLabels.on:adSettingLabels.off}</span></div>
    <div class="ad-settings-grid">
      <label class="ad-settings-field"><span>${adSettingLabels.enabled}</span><select name="enabled"><option value="1" ${enabled?'selected':''}>${adSettingLabels.on}</option><option value="0" ${enabled?'':'selected'}>${adSettingLabels.off}</option></select></label>
      ${adSettingsField(adSettingLabels.provider,'provider',config?.provider||'internal')}
      ${adSettingsField(adSettingLabels.appId,'app_id',config?.app_id)}
      ${adSettingsField(adSettingLabels.rewarded,'rewarded_unit_id',rewarded.unit_id)}
      ${adSettingsField(adSettingLabels.interstitial,'interstitial_unit_id',interstitial.unit_id)}
      ${adSettingsField(adSettingLabels.banner,'banner_unit_id',banner.unit_id)}
      ${adSettingsField(adSettingLabels.rewardCoin,'reward_coin',rewarded.reward_coin,'number','min="0" step="0.0001"')}
      ${adSettingsField(adSettingLabels.cooldown,'cooldown_seconds',rewarded.cooldown_seconds,'number','min="0" step="1"')}
    </div>
    <div class="ad-settings-actions"><span class="ad-settings-message" role="status"></span><button class="button primary" type="submit">${adSettingLabels.save}</button></div>
  </form>`;
}

async function renderAdSettings(){
  if(state.view!=='ad-settings')return;
  const generation=++adSettingsState.generation;
  $('#content').innerHTML=`<section class="panel"><div class="panel-head"><h2>${adSettingLabels.title}</h2></div><p class="muted">\u4e3a\u6bcf\u4e2a\u6e38\u620f\u914d\u7f6e\u5e7f\u544a\u8054\u76df App ID\u3001\u5e7f\u544a\u4f4d ID\u3001\u5956\u52b1\u91d1\u5e01\u548c\u51b7\u5374\u65f6\u95f4\u3002APP \u4f1a\u8bfb\u53d6\u8fd9\u91cc\u7684\u914d\u7f6e\u3002</p><div class="ad-settings-loading">\u6b63\u5728\u52a0\u8f7d\u6e38\u620f\u914d\u7f6e...</div></section>`;
  try{
    const games=await api('/games?limit=200&offset=0');
    if(generation!==adSettingsState.generation||state.view!=='ad-settings')return;
    const rows=await Promise.all((games.items||[]).map(async game=>[game,await api(`/games/${game.id}/ad-config`)]));
    if(generation!==adSettingsState.generation||state.view!=='ad-settings')return;
    $('#content').innerHTML=`<div class="ad-settings-page"><section class="panel ad-settings-intro"><div class="panel-head"><div><h2>${adSettingLabels.title}</h2><p class="muted">\u914d\u7f6e\u5b8c\u6210\u540e\uff0c\u7528\u6237 APP \u7684 bootstrap \u548c\u5e7f\u544a\u8bf7\u6c42\u4f1a\u4f7f\u7528\u5bf9\u5e94\u5e7f\u544a\u4f4d\u3002</p></div><button class="button ghost" id="adSettingsRefresh" type="button">${adSettingLabels.refresh}</button></div><div class="ad-settings-notice">\u8bf7\u586b\u5199\u771f\u5b9e\u8054\u76df\u5e7f\u544a\u4f4d ID\u3002\u672a\u914d\u7f6e\u771f\u5b9e\u6e20\u9053\u65f6\uff0c\u4e0d\u8981\u628a\u5185\u90e8\u6d4b\u8bd5\u503c\u7528\u4e8e\u751f\u4ea7\u6295\u653e\u3002</div></section>${rows.length?rows.map(([game,config])=>adSettingsCard(game,config)).join(''):'<section class="panel"><div class="empty">\u6682\u65e0\u6e38\u620f</div></section>'}</div>`;
    $('#adSettingsRefresh').onclick=()=>renderAdSettings();
    document.querySelectorAll('[data-ad-game]').forEach(form=>form.addEventListener('submit',async event=>{
      event.preventDefault();
      const button=form.querySelector('button[type="submit"]');
      const message=form.querySelector('.ad-settings-message');
      button.disabled=true; message.textContent=adSettingLabels.saving;
      const body=Object.fromEntries(new FormData(form));
      body.enabled=Number(body.enabled); body.reward_coin=Number(body.reward_coin||0); body.cooldown_seconds=Number(body.cooldown_seconds||0);
      try{
        const result=await api(`/games/${form.dataset.adGame}/ad-config`,{method:'PATCH',body:JSON.stringify(body)});
        message.textContent=adSettingLabels.saved;
        const status=form.querySelector('.ad-settings-status');
        status.className=`ad-settings-status ${result.enabled?'enabled':'disabled'}`;
        status.textContent=result.enabled?adSettingLabels.on:adSettingLabels.off;
      }catch(error){message.textContent=error.message||adSettingLabels.failed;}
      finally{button.disabled=false;}
    }));
  }catch(error){
    if(generation!==adSettingsState.generation||state.view!=='ad-settings')return;
    $('#content').innerHTML=`<section class="panel"><div class="panel-head"><h2>${adSettingLabels.title}</h2></div><div class="empty">${esc(error.message||'\u52a0\u8f7d\u5931\u8d25')}</div></section>`;
  }
}
