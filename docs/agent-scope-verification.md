# 主体页面数据范围复验

原实现有两个相反的问题：会员列表从 sessionStorage 读取主体 ID，导致全局列表残留主体范围；主体提现入口使用普通全局地址，实际提现渲染器没有主体约束。

主体入口现使用 `#members?agent_id=…` 和 `#withdrawals?agent_id=…`。地址确定页面范围，顶部标签保留各自地址；全局侧栏入口不带主体参数。筛选、重置、分页和刷新后的请求均保留地址指定的主体，筛选不能覆盖主体条件。切换主体时重置旧筛选和分页，过期响应不覆盖当前页面。

验证证据：

- `verify_agent_navigation_scope.py`：浏览器模拟数据覆盖主体入口、会员翻页、重置、提现状态、刷新、重载、顶部标签恢复、退出到全局、切换主体及筛选不能覆盖页面范围。
- `test_agent_member_and_withdrawal_list_scope`：临时数据库生成两个主体的三名会员和三笔提现，核对会员分页、提现列表/状态筛选，以及待处理和已提现金额汇总。
- `verify_shell_browser.py` 在 3000 端口通过导航、标签、侧栏收缩和刷新后账号恢复。

以上证明本地范围传递与后端筛选行为，不证明角色权限模型或主体用户/提现页面视觉已和对标一致。对标主体入口按 `agents/user/index/agent_id/{id}`、`agents/exchange/index/agent_id/{id}` 限定主体的只读证据见 `visual-baseline/reference-verified/agent-dashboard.json`。
