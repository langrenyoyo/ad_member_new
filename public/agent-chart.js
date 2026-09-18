let agentChartReady;
const agentCharts=new Map();
function loadStatisticsCharts(){
 if(!agentChartReady)agentChartReady=(async()=>{
  if(!window.echarts)await loadReviewScript('/vendor/echarts.min.js');
  const response=await fetch('/vendor/echarts-walden.json');if(!response.ok)throw Error('图表主题加载失败');
  window.echarts.registerTheme('walden',await response.json());
 })().catch(error=>{agentChartReady=undefined;throw error;});
 return agentChartReady;
}
async function mountAgentChart(rows){
 const element=document.querySelector('#agentChart');
 if(!element)return;
 try{
  await loadStatisticsCharts();if(!element.isConnected)return;
  const chart=window.echarts.init(element,'walden');
  chart.setOption({
   title:{text:'',subtext:''},
   color:['#18d1b1','#3fb1e3','#626c91','#a0a7e6','#c4ebad','#96dee8'],
   tooltip:{trigger:'axis'},legend:{data:['注册用户数']},
   toolbox:{show:false,feature:{magicType:{show:true,type:['stack','tiled']},saveAsImage:{show:true}}},
   xAxis:{type:'category',boundaryGap:false,data:rows.map(row=>row.date)},yAxis:{},
   grid:[{left:'left',top:'top',right:'10',bottom:30}],
   series:[{name:'注册用户数',type:'line',smooth:true,areaStyle:{normal:{}},lineStyle:{normal:{width:1.5}},data:rows.map(row=>row.count)}]
  });
  const observer=new ResizeObserver(()=>chart.resize());
  observer.observe(element);
  agentCharts.set(element,{chart,observer});
 }catch(error){if(element.isConnected){element.textContent=error.message;element.setAttribute('role','alert');}}
}
const agentChartCleanup=new MutationObserver(()=>{
 for(const [element,{chart,observer}] of agentCharts)if(!element.isConnected){observer.disconnect();chart.dispose();agentCharts.delete(element);}
});
agentChartCleanup.observe(document.body,{childList:true,subtree:true});
