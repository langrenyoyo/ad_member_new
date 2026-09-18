from pathlib import Path

p = Path('public/app.js')
data = p.read_bytes()
def replace(old, new):
    global data
    old, new = old.encode('ascii'), new.encode('ascii')
    assert data.count(old) == 1, old[:60]
    data = data.replace(old, new)

replace("'agent_id','agent_name'].includes(k)", "'agent_id','agent_name','ip','create_time'].includes(k)")
replace("['status','\\u72b6\\u6001']];", "['status','\\u72b6\\u6001'],['ip','\\u6ce8\\u518cIP'],['create_time','\\u521b\\u5efa\\u65f6\\u95f4']];")
replace('<input data-mf="${key}" value="${esc(value)}">', '<input data-mf="${key}" placeholder="${key===\'create_time\'?\'YYYY-MM-DD - YYYY-MM-DD\':label}" value="${esc(value)}">')
replace("'is_white','status','last_login_ip','created_at']", "'is_white','status','ip','created_at']")
data=data.replace(b"const labels={real_name:",b"const labels={ip:'\\u6ce8\\u518cIP',real_name:")
p.write_bytes(data)
