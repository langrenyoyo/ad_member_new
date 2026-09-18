let reviewExporterReady;
function attachMemberExport(items,params){
 const panel=document.querySelector('#content .panel'),toolbar=document.querySelector('.topbar .toolbar');if(!panel||!toolbar)return;
 const menu=document.createElement('details');menu.className='member-export';menu.dataset.memberToolbar='';
 menu.innerHTML='<summary aria-label="导出数据" title="导出数据"><span aria-hidden="true"> ▾</span></summary><div>'+[['json','JSON'],['xml','XML'],['csv','CSV'],['txt','TXT'],['doc','MS-Word'],['excel','MS-Excel']].map(([type,label])=>`<button type="button" data-member-export="${type}">${label}</button>`).join('')+'</div>';
 toolbar.insertBefore(menu,toolbar.querySelector('#memberSearchToggle'));
 const errorBox=document.createElement('div');errorBox.className='member-export-error';errorBox.setAttribute('role','alert');panel.append(errorBox);
 let busy=false;
 menu.querySelectorAll('button').forEach(button=>button.onclick=async()=>{
  if(busy)return;
  const selected=new Set([...panel.querySelectorAll('[data-select]:checked')].map(e=>String(e.dataset.select)));
  const fields=memberColumnSchema.filter(([key])=>key!=='operate'&&state.memberVisibleColumns.includes(key));
  const query=new URLSearchParams(params),type=button.dataset.memberExport;
  let rows=selected.size?items.filter(row=>selected.has(String(row.id))):[],table;
  busy=true;menu.open=false;menu.setAttribute('aria-busy','true');menu.querySelectorAll('button').forEach(e=>e.disabled=true);errorBox.textContent='';
  try{
   await loadReviewExporter();if(!panel.isConnected)return;
   if(!fields.length)throw Error('请至少显示一个数据列后导出');
   if(!selected.size){
    query.set('limit','200');query.set('offset','0');
    const first=await api('/members?'+query);rows=first.items;const total=first.total;
    while(rows.length<total){
     if(!panel.isConnected)return;
     query.set('offset',String(rows.length));const next=await api('/members?'+query);
     if(next.total!==total||!next.items.length)throw Error('数据已变化，请刷新后重新导出');rows.push(...next.items);
    }
    if(rows.length!==total||new Set(rows.map(row=>row.id)).size!==rows.length)throw Error('数据已变化，请刷新后重新导出');
   }
   if(!panel.isConnected)return;
   table=document.createElement('table');table.className='review-export-table';
   const head=table.createTHead().insertRow();fields.forEach(([,label])=>{const th=document.createElement('th');th.textContent=label;head.append(th);});
   const body=table.createTBody();
   for(const row of rows){const tr=body.insertRow();for(const [key] of fields){
    const cell=tr.insertCell();
    if(key==='image_url')continue;
    let markup;
    if(key==='vip'&&row[key]!=null)markup=`<span class="label label-${['success','warning','danger'][Number(row[key])]||'primary'}">V${esc(row[key])}</span>`;
    if(['status','is_white','exchange_enable'].includes(key)&&row[key]!=null)markup=`<i class="fa fa-toggle-on text-success text-success ${String(row[key])==='1'?'':'fa-flip-horizontal text-gray'} fa-2x"></i>`;
    if(markup){cell.innerHTML='<a>'+markup+'</a>';cell.dataset.memberExportValue=markup;continue;}
    if(['username','parent_id','game_name','agent_name','name','ip','last_login_ip'].includes(key)&&row[key]!=null&&String(row[key]).trim()!==''&&Number.isFinite(Number(row[key]))){const link=document.createElement('a');link.textContent=String(row[key]);cell.append(link);continue;}
    const formatted=document.createElement('div');formatted.innerHTML=memberCell(row,key,row[key]);cell.textContent=formatted.textContent;
   }}
   document.body.append(table);
   window.jQuery(table).tableExport({type,preventInjection:false,fileName:'export_'+new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date()),mso:{onMsoNumberFormat:cell=>!isNaN(window.jQuery(cell).text())?'\\@':''},onBeforeSaveToFile:(data,name,mime,charset)=>{
    if(!panel.isConnected)return false;
    if(type==='xml')data=serializeExportXml(table,cell=>cell.dataset.memberExportValue?new DOMParser().parseFromString(cell.dataset.memberExportValue,'application/xml').documentElement:cell.textContent);
    const url=URL.createObjectURL(new Blob([(type==='csv'||type==='txt'?'\ufeff':''),data],{type:mime+';charset='+charset}));
    const link=document.createElement('a');link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);return false;
   }});
  }catch(error){if(panel.isConnected)errorBox.textContent=error.message;}
  finally{table?.remove();busy=false;menu.removeAttribute('aria-busy');menu.querySelectorAll('button').forEach(e=>e.disabled=false);}
 });
 menu.addEventListener('keydown',event=>{if(event.key==='Escape'){menu.open=false;menu.querySelector('summary').focus();}});
 menu.addEventListener('focusout',event=>{if(!menu.contains(event.relatedTarget))menu.open=false;});
}
function serializeExportXml(table,cellValue=cell=>cell.textContent){
 const doc=document.implementation.createDocument(null,'tabledata');
 const fields=doc.createElement('fields'),data=doc.createElement('data');
 doc.documentElement.append(fields,data);
 for(const cell of table.tHead.rows[0].cells){const field=doc.createElement('field');field.textContent=cell.textContent;fields.append(field);}
 [...table.tBodies[0].rows].forEach((source,index)=>{const row=doc.createElement('row');row.setAttribute('id',String(index+1));[...source.cells].forEach((cell,i)=>{const column=doc.createElement('column-'+(i+1));const value=cellValue(cell);if(value?.nodeType)column.append(exportXmlNode(doc,value));else column.textContent=value;row.append(column);});data.append(row);});
 return '<?xml version="1.0" encoding="utf-8"?>'+new XMLSerializer().serializeToString(doc);
}
function exportXmlNode(doc,source){
 if(source.nodeType===3)return doc.createTextNode(source.nodeValue);
 if(source.nodeType===11){const fragment=doc.createDocumentFragment();for(const child of source.childNodes)fragment.append(exportXmlNode(doc,child));return fragment;}
 const node=doc.createElement(source.tagName.toLowerCase());
 for(const attribute of source.attributes||[])node.setAttribute(attribute.name,attribute.value);
 for(const child of source.childNodes||[])node.append(child.nodeType===3?doc.createTextNode(child.nodeValue):exportXmlNode(doc,child));
 return node;
}
let reviewJQueryReady;
function loadReviewScript(src){return new Promise((resolve,reject)=>{const node=document.createElement('script');node.src=src;node.onload=resolve;node.onerror=()=>{node.remove();reject(Error('组件加载失败'));};document.head.append(node);});}
function loadReviewJQuery(){
 if(!reviewJQueryReady)reviewJQueryReady=(async()=>{if(!window.jQuery){await loadReviewScript('/vendor/jquery.min.js');window.jQuery.noConflict();}})().catch(error=>{reviewJQueryReady=undefined;throw error;});
 return reviewJQueryReady;
}
function loadReviewExporter(){
 if(!reviewExporterReady){
  reviewExporterReady=(async()=>{
   await loadReviewJQuery();
   if(!window.jQuery.fn.tableExport)await loadReviewScript('/vendor/tableExport.js');
  })().catch(error=>{reviewExporterReady=undefined;throw error;});
 }
 return reviewExporterReady;
}

function attachReviewExport(kind,columns,items,params,renderCell){
 const panel=document.querySelector('.withdrawal-panel'),s=reviewStates[kind];
 const menu=document.createElement('details');menu.className='review-export';
 menu.innerHTML='<summary aria-label="导出数据" title="导出数据"><i class="glyphicon glyphicon-export" aria-hidden="true"></i> <span class="caret"></span></summary><div class="review-export-options">'+[['json','JSON'],['xml','XML'],['csv','CSV'],['txt','TXT'],['doc','MS-Word'],['excel','MS-Excel']].map(([type,label])=>`<button type="button" data-review-export="${type}">${label}</button>`).join('')+'</div>';
 panel.querySelector('.withdrawal-toolbar').append(menu);
 let busy=false;
 menu.querySelectorAll('button').forEach(button=>button.onclick=async()=>{
  if(busy)return;
  const selected=new Set([...panel.querySelectorAll('[data-withdrawal-select]:checked,[data-subsidy-select]:checked')].map(box=>Number(box.dataset.withdrawalSelect||box.dataset.subsidySelect)));
  const visible=new Set(s.visibleColumns),fields=columns.filter(([key])=>key!=='review_actions'&&visible.has(key));
  const type=button.dataset.reviewExport,query=new URLSearchParams(params);
  let rows=selected.size?items.filter(row=>selected.has(row.id)):[],table;
  busy=true;menu.open=false;menu.setAttribute('aria-busy','true');menu.querySelectorAll('button').forEach(node=>node.disabled=true);
  const errorBox=panel.querySelector('#reviewError');errorBox.textContent='';
  try{
   await loadReviewExporter();
   if(!panel.isConnected)return;
   if(!selected.size){
    query.set('limit','200');query.set('offset','0');
    const first=await api('/'+kind+'?'+query);rows=first.items;
    const total=first.total;
    while(rows.length<total){
     query.set('offset',String(rows.length));
     const next=await api('/'+kind+'?'+query);
     if(!panel.isConnected)return;
     if(next.total!==total||!next.items.length)throw Error('数据已变化，请刷新后重新导出');
     rows.push(...next.items);
    }
    if(rows.length!==total||new Set(rows.map(row=>row.id)).size!==rows.length)throw Error('数据已变化，请刷新后重新导出');
   }
   if(!panel.isConnected)return;
   table=document.createElement('table');table.className='review-export-table';
   table.innerHTML='<thead><tr>'+fields.map(([,label])=>`<th>${esc(label)}</th>`).join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+fields.map(([key])=>`<td>${key==='pics'?'':renderCell(row,key)}</td>`).join('')+'</tr>').join('')+'</tbody>';
   document.body.append(table);
   window.jQuery(table).tableExport({type,preventInjection:false,fileName:'export_'+new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date()),
    mso:{onMsoNumberFormat:cell=>!isNaN(window.jQuery(cell).text())?'\\@':''},
    onBeforeSaveToFile:(data,name,mime,charset)=>{
     if(type==='xml')data=serializeExportXml(table);
     const blob=new Blob([(type==='csv'||type==='txt'?'\ufeff':''),data],{type:mime+';charset='+charset});
     const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);return false;
    }
   });
  }catch(error){if(panel.isConnected)errorBox.textContent=error.message;}
  finally{table?.remove();busy=false;menu.removeAttribute('aria-busy');menu.querySelectorAll('button').forEach(node=>node.disabled=false);}
 });
 menu.addEventListener('keydown',event=>{if(event.key==='Escape'){menu.open=false;menu.querySelector('summary').focus();}});
 if(!attachReviewExport.listening){document.addEventListener('click',event=>document.querySelectorAll('.review-export[open]').forEach(open=>{if(!open.contains(event.target))open.open=false;}));attachReviewExport.listening=true;}
}
