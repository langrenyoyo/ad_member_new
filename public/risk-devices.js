const deviceRiskState={tableState:null,controller:null};
async function renderRiskDevices(){
 if(state.view!=='risk-devices')return;deviceRiskState.controller?.destroy();
 $('#content').innerHTML='<div id="deviceRiskHost"></div>';
 const tab={endpoint:'/risk/devices',absolute:true,state:deviceRiskState.tableState,
  columns:whitelistColumns.map(column=>column[0]==='game_name'?[column[0],'',...column.slice(2)]:column),cell:whitelistCell,
  mountActions(panel,s,refresh){
   const actions=mountWhitelistActions(panel,s,refresh,{gameLookup:false,selectionLabel:'全选本页会员'});
   const space=document.createElement('div');space.setAttribute('aria-hidden','true');
   panel.querySelector('form').children[2].before(space);
   return actions;
  },
  filterColumns:[['username','账号','search'],['parent_id','上级Id','search'],['agent_id','代理商名称','search'],['name','昵称','search'],
   ['status','状态',{0:'禁用',1:'启用'}],['created_at','创建时间','date']],
  exportCell:whitelistExportCell,exportXmlCell:cell=>cell.querySelector('a>i,a>.label')||cell.textContent,
  exportFileName:()=>'export_'+new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date())};
 deviceRiskState.controller=mountGameUserTable($('#deviceRiskHost'),null,tab);deviceRiskState.tableState=deviceRiskState.controller.state;
 await deviceRiskState.controller.refresh();
}
window.addEventListener('hashchange',()=>{if(!/^#risk-devices(?:$|[?&])/.test(location.hash)){deviceRiskState.controller?.destroy();deviceRiskState.controller=null;}});
