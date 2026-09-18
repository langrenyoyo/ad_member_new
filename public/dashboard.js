async function renderDashboard() {
  const [summary, registrations] = await Promise.all([
    api('/dashboard/summary'), api('/dashboard/registrations?days=31')
  ]);
  if (state.view !== 'dashboard') return;
  const rows = registrations.items || [];
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai' }).format(new Date());
  const added = summary.today_new ?? summary.today_register ?? rows.find(x => x.date === today)?.count ?? 0;
  const logins = summary.today_login ?? summary.today_logins;
  $('#content').innerHTML = `<section class="reference-dashboard">
    <div class="dash-cards">
      <article class="dash-card"><span class="dash-icon dash-green" aria-hidden="true">&#xf234;</span><div><strong>${esc(added)}</strong>今日新增</div></article>
      <article class="dash-card"><span class="dash-icon dash-blue" aria-hidden="true">&#xf0f0;</span><div><strong>${esc(logins ?? '—')}</strong>今日登陆</div></article>
    </div>
    <div class="dash-chart-panel"><div id="echart" role="img" aria-label="每日新增会员趋势"></div></div>
  </section>`;
  const element = document.querySelector('#echart');
  try {
    await loadStatisticsCharts();
    if (!element.isConnected) return;
    const chart = window.echarts.init(element, 'walden');
    chart.setOption({
      color: ['#18d1b1','#3fb1e3','#626c91','#a0a7e6','#c4ebad','#96dee8'],
      tooltip: {trigger:'axis'}, legend: {data:['注册用户数']},
      xAxis: {type:'category',boundaryGap:false,data:rows.map(row=>row.date)},
      yAxis: {}, grid: {left:'left',top:'top',right:10,bottom:30},
      series: [{name:'注册用户数',type:'line',smooth:true,areaStyle:{},lineStyle:{width:1.5},data:rows.map(row=>row.count)}]
    });
    const observer = new ResizeObserver(()=>chart.resize());
    observer.observe(element);
    agentCharts.set(element,{chart,observer});
  } catch (error) {
    if (element.isConnected) {element.textContent=error.message;element.setAttribute('role','alert');}
  }
}
