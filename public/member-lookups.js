/* Reference SelectPage controls backed by authenticated, minimal local lookups. */
let memberLookupEntries=[];
let memberLookupSequence=0;
function disposeMemberLookups(){
 for(const entry of memberLookupEntries){
  entry.live=false;
  for(const xhr of entry.requests)xhr.abort();
  const plugin=window.jQuery(entry.input).data('selectPageObject');
  if(plugin){plugin.prop.last_input_time=-1;plugin.elem.result_area.remove();}
 }
 memberLookupEntries=[];
}
window.jQuery.ajaxPrefilter(function(options,original,xhr){
 if(!options.url.startsWith('/__member_lookup/'))return;
 const entry=memberLookupEntries.find(item=>item.url===options.url);
 if(!entry||!entry.live||!entry.input.isConnected){xhr.abort();return;}
 const version=++entry.responseVersion;
 const current=()=>entry.live&&entry.input.isConnected&&entry.responseVersion===version;
 const params=new URLSearchParams(options.data||'');
 const query=new URLSearchParams({limit:'10',offset:String((Math.max(1,Number(params.get('pageNumber'))||1)-1)*10)});
 const id=params.get('keyValue');
 if(id)query.set('id',id);else query.set('q',params.get('q_word[]')||'');
 if(entry.scope)query.set('agent_id',String(entry.scope));
 options.url='/api/v1/member-filter-options/'+entry.kind+'?'+query;
 options.type='GET';options.data=undefined;
 options.headers={...(options.headers||{}),Authorization:'Bearer '+state.token};
 const success=options.success,error=options.error;
 options.success=function(...args){if(current())success?.apply(this,args);};
 options.error=function(...args){if(current()&&args[1]!=='abort')error?.apply(this,args);};
 entry.requests.add(xhr);xhr.always(()=>entry.requests.delete(xhr));
});
function attachMemberLookups(filters){
 disposeMemberLookups();
 for(const [name,key,kind] of [['game_name','game_id','games'],['agent_name','agent_id','agents']]){
  const input=filters.querySelector('[data-mf="'+name+'"]');if(!input)continue;
  const typed=state.memberFilters?.[name]||'',selected=state.memberFilters?.[key]||'';
  const scope=state.agentScope,locked=kind==='agents'&&!!scope;
  input.removeAttribute('data-mf');input.dataset.memberLookup=name;
  input.name='member-lookup-'+key;input.id=input.name;input.classList.add('form-control');
  input.value=String(locked?scope:selected);
  const {plugin}=createFilterLookup(input,kind,scope,plugin=>plugin.elem.hidden.attr('data-mf',key));
  plugin.elem.hidden.attr('data-mf',key);
  if(!selected&&!locked&&typed){input.value=typed;plugin.elem.hidden.attr('data-mf',name).val(typed);}
  if(locked){input.disabled=true;plugin.elem.button.hide();plugin.elem.clear_btn.hide();input.title='当前主体';}
 }
}
function createFilterLookup(input,kind,scope,onChange){
 const entry={input,kind,scope,live:true,responseVersion:0,requests:new Set(),url:'/__member_lookup/'+(++memberLookupSequence)};
 memberLookupEntries.push(entry);
 input.addEventListener('input',()=>{
  entry.responseVersion++;
  const plugin=window.jQuery(input).data('selectPageObject');
  // A new query must not reuse the page selected for the previous keyword.
  if(plugin){plugin.prop.current_page=1;plugin.prop.page_move=false;}
 });
 const sync=plugin=>{entry.responseVersion++;onChange(plugin);};
 window.jQuery(input).selectPage({data:entry.url,lang:'cn',keyField:'id',showField:'name',pageSize:10,
  orderBy:'name ASC',searchField:'name',selectToCloseList:false,
  eAjaxSuccess:data=>({list:data.items,totalRow:data.total}),
  eSelect:(data,plugin)=>sync(plugin),eClear:plugin=>sync(plugin)});
 const plugin=window.jQuery(input).data('selectPageObject');
 plugin.elem.result_area.addClass('member-lookup-results member-lookup-results-'+kind);
 return {entry,plugin};
}
function attachAdsLookups(form){
 disposeMemberLookups();
 for(const [key,field,kind] of [['game_id','game_name','games'],['agent_id','agent_name','agents']]){
  const input=form.querySelector('[data-ads-lookup="'+field+'"]');
  input.value=String(adsState.filters[key]||'');
  const {plugin}=createFilterLookup(input,kind,null,plugin=>plugin.elem.hidden.attr('name',key));
  const position=plugin.calcResultsSize;
  plugin.calcResultsSize=function(self){
   position.call(this,self);
   const box=self.elem.container,menu=self.elem.result_area,left=box.offset().left,width=menu.outerWidth();
   // The reference's jQuery rounds outerWidth when right-aligning the popup.
   if(left+width>window.jQuery(document).width())menu.css('left',left+Math.round(box.outerWidth())-width);
  };
  input.removeAttribute('name');
  if(!adsState.filters[key]&&adsState.filters[field])setAdsLookupName(field,adsState.filters[field]);
 }
}
function attachReviewLookups(form,kind){
 const s=reviewStates[kind],scope=kind==='withdrawals'?s.agentScope:null;
 attachFilterLookups(form,s.filters,scope,'data-review-lookup');
}
function attachFilterLookups(form,filters,scope=null,attribute='data-filter-lookup'){
 disposeMemberLookups();
 for(const [key,source] of [['game_id','games'],['agent_id','agents']]){
  const input=form.elements.namedItem(key),locked=source==='agents'&&!!scope;
  if(!input)continue;
  input.id=form.id+'-'+key;input.setAttribute(attribute,key);input.classList.add('form-control');
  input.value=String(locked?scope:filters[key]||'');
  const {plugin}=createFilterLookup(input,source,scope,plugin=>plugin.elem.hidden.attr('name',key));
  input.removeAttribute('name');
  if(locked){input.disabled=true;input.title='当前主体';plugin.elem.hidden.prop('disabled',true);plugin.elem.button.hide();plugin.elem.clear_btn.hide();}
 }
}
function setAdsLookupName(field,value){
 const input=document.querySelector('[data-ads-lookup="'+field+'"]');if(!input)return;
 const entry=memberLookupEntries.find(item=>item.input===input);if(entry)entry.responseVersion++;
 const plugin=window.jQuery(input).data('selectPageObject');
 plugin.afterInit(plugin,{id:value,name:value});
 plugin.elem.hidden.attr('name',field);
}
document.addEventListener('click',event=>{
 if(event.target.closest('#memberFilterReset')){
  for(const entry of memberLookupEntries)window.jQuery(entry.input).selectPageClear();
 }
},true);
window.addEventListener('hashchange',disposeMemberLookups);
new MutationObserver(()=>{
 if(memberLookupEntries.some(entry=>!entry.input.isConnected))disposeMemberLookups();
}).observe(document.getElementById('content'),{childList:true,subtree:true});
