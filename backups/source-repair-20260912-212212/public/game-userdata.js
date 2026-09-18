const gameUserTabs = [
 {id:'first',label:'鎶藉鍒楄〃',endpoint:'lottery-records',columns:[
  ['id','Id'],['user_id','浼氬憳ID','search'],['username','鐢ㄦ埛璐﹀彿','search'],['game_name','娓告垙鍚嶇О'],
  ['lottery_price','閲戝竵','sort'],['ecpm','ECPM'],['adn_name','绫诲瀷','search'],['ip','鍏綉IP','search'],
  ['network_status','鍐呯綉',{0:'鏄',1:'鍚'}],['tag','鏄惁椋庢帶'],['is_white','鐧藉悕鍗',{0:'鍚',1:'鏄'}],
  ['status','鐘舵€',{0:'澶辫触',1:'鎴愬姛'}],['created_at','鎶藉鏃堕棿','date'],
  ['ad_network_rit_id','骞垮憡浠ｇ爜浣'],['request_id','骞垮憡request_id'],['trans_id','浜ゆ槗trans_id']
 ]},
 {id:'second',label:'椋庢帶鍘嗗彶',endpoint:'/risk/history',absolute:true,columns:[
  ['id','Id'],['user_id','浼氬憳ID','search'],['username','鐢ㄦ埛璐﹀彿','search'],['game_name','娓告垙鍚嶇О'],
  ['ip','IP','search'],['network_status','鍐呯綉',{0:'鏄',1:'鍚'}],['tags','鏍囩','search'],['created_at','鍒涘缓鏃堕棿','date']
 ]},
 {id:'four',label:'鐢ㄦ埛鍒楄〃',endpoint:'/members',absolute:true,columns:[
  ['id','Id'],['username','璐﹀彿','search'],['name','鏄电О','search'],['game_name','娓告垙鍚嶇О'],
  ['coin_user','绱閲戝竵鏀剁泭','sort'],['coin_user_month','鏈湀閲戝竵鏀剁泭'],['coin_user_day','浠婃棩閲戝竵鏀剁泭'],
  ['coin','鍙敤閲戝竵','sort'],['freeze_coin','鍐荤粨閲戝竵','sort'],['is_true','鍐呴儴鍙',{0:'鍚',1:'鏄'}],
  ['game_addiction_enable','杈炬爣',{0:'鍚',1:'鏄'}],['is_white','鐧藉悕鍗',{0:'鍚',1:'鏄'}],['status','鐘舵€',{0:'绂佺敤',1:'鍚敤'}],['created_at','鍒涘缓鏃堕棿','date']
 ]},
 {id:'third',label:'鎻愮幇璁板綍',endpoint:'/withdrawals',absolute:true,columns:[
  ['id','Id'],['user_id','浼氬憳ID','search'],['username','璐﹀彿','search'],['game_name','娓告垙鍚嶇О'],
  ['receive_name','鏀朵欢浜','search'],['receive_tel','鑱旂郴鏂瑰紡','search'],['exchange_value','閲戦','sort'],
  ['status','鐘舵€',{0:'鐢宠涓',1:'瀹℃牳閫氳繃',2:'瀹℃牳澶辫触',4:'瀹℃牳澶辫触'}],['reason','鎷掔粷鍘熷洜'],['created_at','鐢宠鏃堕棿','date'],['updated_at','鏇存柊鏃堕棿','date']
 ]},
 {id:'five',label:'鐧婚檰鍘嗗彶',endpoint:'login-logs',columns:[
  ['id','Id'],['user_id','浼氬憳ID','search'],['username','鐢ㄦ埛璐﹀彿','search'],['game_name','娓告垙鍚嶇О'],
  ['device_id','璁惧鍙'],['ip','IP','search'],['created_at','鐧婚檰鏃堕棿','date']
 ]},
 {id:'six',label:'姣忔棩娲昏穬',endpoint:'daily-activity',columns:[['id','Id'],['game_name','娓告垙鍚嶇О'],['num','鏃ユ椿','sort'],['date','鏃堕棿','date']]},
 {id:'seven',label:'鏁版嵁缁熻',endpoint:'statistics',stats:true,columns:[]}
];

function gameUserCell(row, column) {
 const [key,,kind] = column, value = row[key];
 if(value == null) return '';
 if(kind === 'date') return esc(profileLogTime(value));
 if(typeof kind === 'object') {
  const label = kind[value];
  return label == null ? '' : `<span class="game-user-label value-${Number(value)} ${key==='network_status'&&Number(value)===0?'warning':''}">${esc(label)}</span>`;
 }
 if(kind === 'search' && key !== 'adn_name') return `<button class="game-user-cell-search" data-search-field="${key}" data-search-value="${esc(String(value))}">${esc(value)}</button>`;
 return esc(value);
}

function gameUserQuery(filters, page, size, sort, order) {
 const query = new URLSearchParams({limit:size,offset:(page-1)*size,sort,order});
 for(const [key,value] of Object.entries(filters)) {
  if(value === '') continue;
  if(key !== 'created_range' && key !== 'date_range') {query.set(key,value);continue;}
  const parts = value.split(' - ');
  if(parts.length !== 2 || parts.some(part=>!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(part))) throw Error('鏃堕棿鑼冨洿鏃犳晥');
  const dates = parts.map(part=>new Date(part.replace(' ','T')+'+08:00'));
  if(dates.some(date=>Number.isNaN(date.getTime())) || dates[0]>dates[1]) throw Error('鏃堕棿鑼冨洿鏃犳晥');
  // Date silently rolls invalid days into the next month; reject that normalization.
  if(dates.some((date,index)=>new Date(date.getTime()+8*3600000).toISOString().slice(0,19).replace('T',' ')!==parts[index])) throw Error('鏃堕棿鑼冨洿鏃犳晥');
  if(key==='date_range'){query.set('date_from',parts[0].slice(0,10));query.set('date_to',parts[1].slice(0,10));}else{query.set('created_from',dates[0].toISOString());query.set('created_to',dates[1].toISOString());}
 }
 return query;
}

function mountGameUserTable(panel, gameId, tab) {
 if(tab.stats){let stopped=false;panel.innerHTML='<section class="game-user-stats">鍔犺浇涓€</section>';api(`/games/${gameId}/statistics`).then(data=>{if(stopped)return;const chart=(rows,key,label)=>{if(!rows.length)return '<p class="game-stat-empty">鏆傛棤鍘嗗彶璁板綍</p>';const max=Math.max(...rows.map(item=>Number(item[key])),1),points=rows.map((row,i)=>`${(i/(rows.length-1||1)*100).toFixed(2)},${(100-Number(row[key])/max*86-7).toFixed(2)}`).join(' ');return `<div class="game-stat-chart"><h3>${label}</h3><svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="${label}"><polyline points="${points}" vector-effect="non-scaling-stroke"></polyline></svg><div class="game-stat-axis"><span>${esc(rows[0].date)}</span><span>${esc(rows[rows.length-1].date)}</span><b>鏈€澶'${max.toFixed(2)}</b></div></div>`};panel.querySelector('.game-user-stats').innerHTML=`<div class="game-stat-cards"><article><strong>楼${Number(data.total_income).toFixed(2)}</strong><span>鎬婚噾棰</span></article><article><strong>?${Number(data.year_income).toFixed(2)}</strong><span>\u672c\u5e74\u91d1\u989d</span></article><article><strong>?${Number(data.month_income).toFixed(2)}</strong><span>\u672c\u5e74\u91d1\u989d</span></article><article><strong>?${Number(data.yesterday_income).toFixed(2)}</strong><span>\u672c\u5e74\u91d1\u989d</span></article><article><strong>${data.total_members}</strong><span>鎬讳細鍛樻暟</span></article><article><strong>${data.today_new}</strong><span>浠婃棩鏂板</span></article><article><strong>${data.today_login}</strong><span>浠婃棩鐧婚檰</span></article></div>${chart(data.income,'amount','閲戦缁熻')}${chart(data.activity,'num','鏃ユ椿缁熻')}`;}).catch(error=>{if(!stopped)panel.querySelector('.game-user-stats').textContent=error.message;});return {refresh:()=>{},destroy:()=>{stopped=true;}};}
 if(tab.unavailable){panel.innerHTML='<section class="game-user-unavailable"><p>鏆傛棤鍙獙璇佺殑鐙珛鍘嗗彶鏁版嵁婧</p><small>涓洪伩鍏嶄粠蹇収鏁版嵁鎺ㄥ閿欒缁撴灉锛屾椤电鏆傛湭鐢熸垚缁熻鏁版嵁銆</small></section>';return {refresh:()=>{},destroy:()=>{}};}
 const allowedSizes=[10,15,20,25,50],savedSize=Number(localStorage.getItem('pagesize'));
 const s={page:1,size:allowedSizes.includes(savedSize)?savedSize:10,sort:'id',order:'desc',filters:{},visible:new Set(tab.columns.map(c=>c[0])),cards:false,total:0,items:[],generation:0};
 let request,exportRequest,closed=false,exportBusy=false;
 const path=tab.absolute?tab.endpoint:`/games/${gameId}/${tab.endpoint}`;
 panel.innerHTML=`<section class="ads-panel game-user-panel">
  <form class="ads-filters" hidden>${tab.columns.filter(([, ,kind])=>kind==='search'||kind==='date'||typeof kind==='object').map(([key,label,kind])=>`<label><span>${label}</span>${typeof kind==='object'?`<select name="${key}"><option value="">閫夋嫨</option>${Object.entries(kind).map(([value,text])=>`<option value="${value}">${text}</option>`).join('')}</select>`:`<input name="${kind==='date'?(tab.endpoint==='daily-activity'?'date_range':'created_range'):key}" ${key==='user_id'?'inputmode="numeric"':''} placeholder="${label}">`}</label>`).join('')}<div class="ads-filter-actions"><button class="ads-submit" type="submit">鎻愪氦</button><button type="reset">閲嶇疆</button></div></form>
  <div class="ads-toolbar"><button class="ads-refresh" data-action="refresh" aria-label="鍒锋柊"><i class="shell-icon" aria-hidden="true">&#xf021;</i></button><div class="game-user-table-tools">
   <button data-action="search" aria-label="鏅€氭悳绱? aria-expanded="false"><i class="shell-icon" aria-hidden="true">&#xf002;</i></button>
   <button data-action="cards" aria-label="鍒囨崲瑙嗗浘" aria-pressed="false"><i class="shell-icon" aria-hidden="true">&#xf022;</i></button>
   <details class="game-user-columns"><summary aria-label="鏄剧ず鍒?><i class="shell-icon" aria-hidden="true">&#xf0db;</i> 鈻?/summary><div>${tab.columns.map(([key,label])=>`<label><input type="checkbox" data-column="${key}" checked>${label}</label>`).join('')}</div></details>
   <details class="game-user-export"><summary aria-label="瀵煎嚭鏁版嵁"><i class="shell-icon" aria-hidden="true">&#xf019;</i> 鈻?/summary><div>${[['json','JSON'],['xml','XML'],['csv','CSV'],['txt','TXT'],['doc','MS-Word'],['excel','MS-Excel']].map(([key,label])=>`<button data-export="${key}">${label}</button>`).join('')}</div></details>
  </div></div><p role="alert"></p><div class="game-user-results" aria-live="polite"></div><div class="game-user-pagination"></div></section>`;
 const form=panel.querySelector('form'),errorBox=panel.querySelector('[role=alert]'),results=panel.querySelector('.game-user-results'),pagination=panel.querySelector('.game-user-pagination');
 attachReviewDates(form);
 const setExpanded=value=>{form.hidden=!value;panel.querySelector('[data-action=search]').setAttribute('aria-expanded',String(value));};
 const paint=()=>{
  const columns=tab.columns.filter(([key])=>s.visible.has(key));
  results.innerHTML=s.cards?`<div class="game-user-cards">${s.items.map(row=>`<article>${columns.map(column=>`<div><strong>${column[1]}:</strong><span>${gameUserCell(row,column)}</span></div>`).join('')}</article>`).join('')||'<p>娌℃湁鎵惧埌鍖归厤鐨勮褰</p>'}</div>`:
   `<div class="table-wrap"><table class="ads-table"><thead><tr>${columns.map(([key,label,kind])=>`<th ${kind==='sort'||kind==='date'?`aria-sort="${s.sort===key?(s.order==='asc'?'ascending':'descending'):'none'}"`:''}>${kind==='sort'||kind==='date'?`<button data-sort="${key}">${label} ${s.sort===key?(s.order==='asc'?'鈻':'鈻'):'鈫'}</button>`:label}</th>`).join('')}</tr></thead><tbody>${s.items.map(row=>`<tr>${columns.map(column=>`<td>${gameUserCell(row,column)}</td>`).join('')}</tr>`).join('')||`<tr><td colspan="${columns.length}">娌℃湁鎵惧埌鍖归厤鐨勮褰'/td></tr>`}</tbody></table></div>`;
  const last=Math.max(1,Math.ceil(s.total/s.size));
  const pages=[...new Set([1,...Array.from({length:5},(_,i)=>s.page+i-2).filter(n=>n>=1&&n<=last),last])].sort((a,b)=>a-b);
  pagination.hidden=s.total===0;
  pagination.innerHTML=`<span>鏄剧ず绗?${s.total?(s.page-1)*s.size+1:0} 鍒扮 ${(s.page-1)*s.size+s.items.length} 鏉¤褰曪紝鎬诲叡 ${s.total} 鏉¤褰?/span><label>姣忛〉鏄剧ず <select aria-label="姣忛〉璁板綍鏁?>${allowedSizes.map(n=>`<option value="${n}" ${s.size===n?'selected':''}>${n}</option>`).join('')}</select> 鏉¤褰</label><nav aria-label="鍒嗛〉"><button data-page="${s.page-1}" ${s.page===1?'disabled':''}>鈥</button>${pages.map((n,i)=>`${i&&n>pages[i-1]+1?'<span>鈥</span>':''}<button data-page="${n}" ${n===s.page?'aria-current="page"':''}>${n}</button>`).join('')}<button data-page="${s.page+1}" ${s.page===last?'disabled':''}>鈥</button></nav>`;
  results.querySelectorAll('[data-sort]').forEach(button=>button.onclick=()=>{s.order=s.sort===button.dataset.sort&&s.order==='desc'?'asc':'desc';s.sort=button.dataset.sort;s.page=1;refresh();});
  results.querySelectorAll('[data-search-field]').forEach(button=>button.onclick=()=>{const input=form.elements.namedItem(button.dataset.searchField);input.value=button.dataset.searchValue;setExpanded(true);form.requestSubmit();});
  pagination.querySelectorAll('[data-page]').forEach(button=>button.onclick=()=>{s.page=Number(button.dataset.page);refresh();});
  pagination.querySelector('select').onchange=event=>{s.size=Number(event.target.value);localStorage.setItem('pagesize',String(s.size));s.page=1;refresh();};
 };
 async function refresh() {
  const generation=++s.generation;
  request?.abort();request=new AbortController();errorBox.textContent='';
  try {
   const query=gameUserQuery(s.filters,s.page,s.size,s.sort,s.order);
   if(tab.absolute){query.set('game_id',String(gameId));}
   results.setAttribute('aria-busy','true');
   const data=await api(path+'?'+query,{signal:request.signal});
   if(closed||generation!==s.generation)return;
   const last=Math.max(1,Math.ceil(data.total/s.size));
   if(s.page>last){s.page=last;return refresh();}
   s.items=data.items;s.total=data.total;paint();
  }catch(error){if(!closed&&generation===s.generation&&error.name!=='AbortError')errorBox.textContent=error.message;}
  finally{if(generation===s.generation)results.removeAttribute('aria-busy');}
 }
 form.onsubmit=event=>{event.preventDefault();s.filters=Object.fromEntries(new FormData(form));s.page=1;refresh();};
 form.onreset=event=>{event.preventDefault();for(const field of form.querySelectorAll('input,select'))field.value='';s.filters={};s.page=1;refresh();};
 panel.querySelector('[data-action=refresh]').onclick=refresh;
 panel.querySelector('[data-action=search]').onclick=()=>setExpanded(form.hidden);
 panel.querySelector('[data-action=cards]').onclick=event=>{s.cards=!s.cards;event.currentTarget.setAttribute('aria-pressed',String(s.cards));paint();};
 const checkboxes=[...panel.querySelectorAll('[data-column]')];
 checkboxes.forEach(box=>box.onchange=()=>{if(box.checked)s.visible.add(box.dataset.column);else s.visible.delete(box.dataset.column);checkboxes.forEach(item=>item.disabled=s.visible.size===1&&item.checked);paint();});
 panel.querySelectorAll('[data-export]').forEach(button=>button.onclick=async()=>{
  if(exportBusy)return;
  exportBusy=true;exportRequest=new AbortController();const menu=button.closest('details');menu.open=false;
  menu.querySelectorAll('button').forEach(node=>node.disabled=true);errorBox.textContent='';let table;
  try{
   const query=gameUserQuery(s.filters,1,200,s.sort,s.order),columns=tab.columns.filter(([key])=>s.visible.has(key));
   if(tab.absolute)query.set('game_id',String(gameId));
   await loadReviewExporter();if(closed)return;
   const first=await api(path+'?'+query,{signal:exportRequest.signal}),rows=[...first.items];
   while(rows.length<first.total){query.set('offset',String(rows.length));const next=await api(path+'?'+query,{signal:exportRequest.signal});if(next.total!==first.total||!next.items.length)throw Error('鏁版嵁宸插彉鍖栵紝璇峰埛鏂板悗閲嶆柊瀵煎嚭');rows.push(...next.items);}
   if(rows.length!==first.total||new Set(rows.map(row=>row.id)).size!==rows.length)throw Error('鏁版嵁宸插彉鍖栵紝璇峰埛鏂板悗閲嶆柊瀵煎嚭');
   if(closed)return;
   table=document.createElement('table');table.className='review-export-table';
   table.innerHTML='<thead><tr>'+columns.map(([,label])=>`<th>${label}</th>`).join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+columns.map(column=>`<td>${gameUserCell(row,column)}</td>`).join('')+'</tr>').join('')+'</tbody>';
   panel.append(table);const type=button.dataset.export;
   window.jQuery(table).tableExport({type,preventInjection:false,fileName:'export_'+tab.endpoint,
    mso:{onMsoNumberFormat:cell=>!isNaN(window.jQuery(cell).text())?'\\@':''},
    onBeforeSaveToFile:(data,name,mime,charset)=>{if(closed)return false;const url=URL.createObjectURL(new Blob([(type==='csv'||type==='txt'?'\ufeff':''),data],{type:mime+';charset='+charset})),link=document.createElement('a');link.href=url;link.download=name;panel.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);return false;}
   });
  }catch(error){if(!closed&&error.name!=='AbortError')errorBox.textContent=error.message;}
  finally{table?.remove();exportBusy=false;menu.querySelectorAll('button').forEach(node=>node.disabled=false);}
 });
 return {refresh,destroy:()=>{closed=true;s.generation++;request?.abort();exportRequest?.abort();}};
}

function openGameUserData(gameId) {
 const existing=document.querySelector('.game-user-dialog');if(existing)existing.close();
 const dialog=document.createElement('dialog');dialog.className='game-user-dialog';dialog.setAttribute('aria-label','鐢ㄦ埛鏁版嵁');
 dialog.innerHTML=`<header><span>鐢ㄦ埛鏁版嵁</span><div><button data-dialog-maximize aria-label="鏈€澶у寲">鈻?/button><button data-dialog-close aria-label="鍏抽棴">脳</button></div></header><div class="game-user-body"><nav role="tablist" aria-label="鐢ㄦ埛鏁版嵁">${gameUserTabs.map((tab,index)=>`<button role="tab" id="game-user-tab-${tab.id}" aria-controls="game-user-pane-${tab.id}" aria-selected="${index===0}" tabindex="${index===0?0:-1}" data-tab="${tab.id}">${tab.label}</button>`).join('')}</nav>${gameUserTabs.map((tab,index)=>`<div role="tabpanel" id="game-user-pane-${tab.id}" aria-labelledby="game-user-tab-${tab.id}" ${index===0?'':'hidden'}></div>`).join('')}</div>`;
 const controllers=new Map(),tabs=[...dialog.querySelectorAll('[role=tab]')];
 const activate=key=>{
  for(const [input,picker] of reviewDateBindings)if(dialog.contains(input))picker.hide();
  dialog.querySelectorAll('details[open]').forEach(menu=>menu.open=false);
  tabs.forEach(button=>{const active=button.dataset.tab===key;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;dialog.querySelector('#'+button.getAttribute('aria-controls')).hidden=!active;});
  if(!controllers.has(key)){const tab=gameUserTabs.find(item=>item.id===key);controllers.set(key,mountGameUserTable(dialog.querySelector('#game-user-pane-'+key),gameId,tab));}
  controllers.get(key).refresh();
 };
 tabs.forEach(button=>button.onclick=()=>activate(button.dataset.tab));
 dialog.querySelector('[role=tablist]').onkeydown=event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();let index=tabs.indexOf(document.activeElement);index=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;tabs[index].focus();activate(tabs[index].dataset.tab);};
 const close=()=>dialog.close();
 dialog.addEventListener('click',event=>dialog.querySelectorAll('details[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;}));
 dialog.addEventListener('keydown',event=>{
  if(event.key!=='Escape')return;
  const menus=[...dialog.querySelectorAll('details[open]')];
  const pickers=[...reviewDateBindings].filter(([input,picker])=>dialog.contains(input)&&picker.isShowing);
  if(menus.length||pickers.length){event.preventDefault();menus.forEach(menu=>menu.open=false);pickers.forEach(([,picker])=>picker.hide());}
 });
 dialog.querySelector('[data-dialog-close]').onclick=close;
 dialog.querySelector('[data-dialog-maximize]').onclick=event=>{const maximized=dialog.classList.toggle('maximized');event.currentTarget.setAttribute('aria-label',maximized?'杩樺師':'鏈€澶у寲');};
 window.addEventListener('hashchange',close);
 dialog.addEventListener('close',()=>{controllers.forEach(controller=>controller.destroy());window.removeEventListener('hashchange',close);dialog.remove();},{once:true});
 document.body.append(dialog);dialog.showModal();activate(gameUserTabs[0].id);
}

function openGameProfitData(gameId){
 openGameUserData(gameId);
 const tab=document.querySelector('.game-user-dialog [data-tab="seven"]');
 if(tab)tab.click();
}

function attachGameUserData(items) {
 const table=document.querySelector('.agent-dashboard .ads-table');if(!table)return;
 table.tHead.rows[0].insertAdjacentHTML('beforeend','<th>鏁版嵁鏌ョ湅</th>');
 [...table.tBodies[0].rows].forEach((row,index)=>{
  if(!items.length){row.cells[0].colSpan++;return;}
  const cell=row.insertCell(),button=document.createElement('button');button.className='game-user-open';button.dataset.gameUser=items[index].id;button.textContent='鐢ㄦ埛鏁版嵁';button.onclick=()=>openGameUserData(items[index].id);cell.append(button);
  const profit=document.createElement('button');profit.className='game-profit-open';profit.textContent='鏀剁泭鏁版嵁';profit.onclick=()=>openGameProfitData(items[index].id);cell.append(profit);
 });
}




