"""Create a dedicated risk history view using the existing list UI conventions."""
from pathlib import Path
s=Path('public/coin-logs.js').read_text(encoding='utf-8')
s=s[s.index('const coinState='):]
s=s.replace('coinState','riskHistoryState').replace('coinDefaults','riskHistoryDefaults').replace('renderCoinLogs','renderRiskHistory').replace('loadCoinLogs','loadRiskHistory')
s=s.replace("return {game_ad_status:'0',created_range:adsDefaults().watched_range};","return {};")
s=s.replace("['coin-logs','profit'].includes(state.view)","['risk-history'].includes(state.view)")
s=s.replace('coin-panel','risk-history-panel').replace('coinFilters','riskHistoryFilters').replace('coinError','riskHistoryError').replace('coinRefresh','riskHistoryRefresh').replace('coinSummary','riskHistorySummary').replace('coinTable','riskHistoryTable').replace('coinPagination','riskHistoryPagination').replace('coinPrev','riskHistoryPrev').replace('coinNext','riskHistoryNext')
start=s.index(" ${field('会员ID'");end=s.index(' <div class="ads-filter-actions">',start)
s=s[:start]+""" ${field('会员ID',input('user_id','会员ID'))}${field('用户账号',input('username','用户账号'))}${field('上级Id',input('parent_id','上级Id'))}${field('游戏名称',select('game_id',games.map(x=>[x.id,x.name])))}
 ${field('代理商名称',select('agent_id',agents.map(x=>[x.id,x.name])))}${field('标签',input('tagcode','标签'))}${field('硬件主ID',input('hardware_main_id','硬件主ID'))}${field('ip',input('ip','ip'))}${field('创建时间',input('created_range','创建时间'))}
"""+s[end:]
s=s.replace("'/coin-logs?'","'/risk/history?'").replace('刷新金币流水','刷新风控历史')
s=s.replace("$('#riskHistorySummary').textContent='金币变动: '+data.summary.change;",'')
start=s.index('  const columns=');end=s.index('\n',start)
s=s[:start]+"  const columns=[['id','Id'],['user_id','会员ID'],['username','用户账号'],['game_name','游戏名称'],['tagcode','标签'],['tags','标签名'],['hardware_main_id','硬件主ID'],['ip','ip'],['action','行为'],['risk_score','风险分数'],['risk_level','风险等级'],['created_at','创建时间']];"+s[end:]
s=s.replace("key==='type'?coinTypes[row[key]]||row[key]:",'').replace('colspan="11"','colspan="12"')
Path('public/risk-history.js').write_text(s,encoding='utf-8')
p=Path('public/app.js');data=p.read_bytes();old=b"if(state.view==='ads'){await renderAds();return}";assert data.count(old)==1;data=data.replace(old,old+b"if(state.view==='risk-history'){await renderRiskHistory();return}");old=b"document.body.classList.toggle('book-view',state.view==='book');";data=data.replace(old,old+b"document.body.classList.toggle('risk-history-view',state.view==='risk-history');");p.write_bytes(data)
p=Path('public/index.html');data=p.read_bytes().replace(b'</head>',b'<link rel="stylesheet" href="/risk-history.css"></head>').replace(b'<script src="/app.js">',b'<script src="/risk-history.js"></script><script src="/app.js">');p.write_bytes(data)
