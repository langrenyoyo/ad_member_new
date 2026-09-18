"""Apply scoped ASCII replacements without re-encoding legacy app.js bytes."""
from pathlib import Path
p = Path('public/app.js')
data = p.read_bytes()
def replace(old, new):
    global data
    old = old.encode('ascii')
    assert data.count(old) == 1, old[:80]
    data = data.replace(old, new.encode('ascii'), 1)
replace("state.q=state.memberFilters.username||state.memberFilters.name||'';", "state.q='';state.status='';")
replace("state.q='';state.memberFilters={};", "state.q='';state.status='';state.memberFilters={};")
start = data.index(b"'<div class=\"member-filters\">")
end = data.index(b"</div>':''}", start) + len(b"</div>'")
data = data[:start] + b'memberFilterMarkup()' + data[end:]
replace("'game_name','agent_id'].includes(k)", "'game_name','agent_id','agent_name'].includes(k)")
data=data.replace(b'const labels={username:', b"const labels={real_name:'\\u771f\\u5b9e\\u59d3\\u540d',username:")
replace('${esc(val(x,k))}', '${memberCell(x,k,val(x,k))}')
helpers = r'''
function memberFilterMarkup(){
 const fields=[['id','Id'],['username','\u8d26\u53f7'],['parent_id','\u4e0a\u7ea7Id'],['game_name','\u6e38\u620f\u540d\u79f0'],['vip','VIP'],['agent_name','\u4ee3\u7406\u5546\u540d\u79f0'],['name','\u6635\u79f0'],['status','\u72b6\u6001']];
 return '<div class="member-filters">'+fields.map(([key,label])=>{
  const value=state.memberFilters[key]||'';
  const options=key==='vip'?Array.from({length:11},(_,i)=>[String(i),'V'+i]):key==='status'?[['1','\u542f\u7528'],['0','\u7981\u7528']]:null;
  const control=options?`<select data-mf="${key}"><option value="">\u5168\u90e8</option>${options.map(([v,l])=>`<option value="${v}" ${value===v?'selected':''}>${l}</option>`).join('')}</select>`:`<input data-mf="${key}" value="${esc(value)}">`;
  return `<label><span>${label}</span>${control}</label>`;
 }).join('')+'<span class="filter-actions"><button type="button" class="button primary" id="memberFilterSubmit">\u63d0\u4ea4</button><button type="button" class="button ghost" id="memberFilterReset">\u91cd\u7f6e</button></span></div>';
}
function memberCell(row,key,value){
 if(state.view!=='members')return esc(value);
 if(key==='vip')return `<span class="vip-badge">V${esc(row[key])}</span>`;
 if(key==='status'||key==='is_white'){
  const on=String(row[key])==='1', white=key==='is_white';
  return `<button type="button" role="switch" aria-checked="${on}" aria-label="${white?'\u767d\u540d\u5355':'\u72b6\u6001'}" class="member-switch ${on?'on':''}" ${white?'data-white':'data-toggle'}="${esc(row.id)}" ${white?'data-next-white':'data-next-status'}="${on?0:1}">${on?'\u5f00':'\u5173'}</button>`;
 }
 return esc(value);
}
'''
p.write_bytes(data + helpers.encode('ascii'))
