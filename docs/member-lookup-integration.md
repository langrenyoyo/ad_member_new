# 会员关联筛选器接入记录

本轮把对标的 SelectPage 2.20 控件加载到会员筛选区。`member-lookups.js` 为每个控件建立独立的存活标记和 XMLHttpRequest 集合，筛选区重新渲染、切换路由或旧输入节点脱离 DOM 时终止请求并移除结果弹层。供应商控件仍负责键盘导航、分页、单选、清空和显示文本。

供应商请求使用 POST 和 `q_word[]`、`pageNumber`、`keyValue`；适配层将其转换成 `/api/v1/member-filter-options/games|agents` 的 GET，附加当前认证头和主体范围。返回 `{items,total}` 被转换为供应商要求的 `{list,totalRow}`。选中项的隐藏值始终为 ID，显示框使用名称；刷新时通过 ID 回填名称。提交筛选只写入 `game_id`、`agent_id`，表格内名称按钮仍走名称快捷搜索。

验证命令：

- `python verify_member_lookups.py`：认证头、首屏十项、选中 ID、提交参数、ID 回填、重置、名称输入搜索、网络失败时保留选中值和导航清理。
- `python verify_member_toolbar.py`：选择、编辑、筛选折叠和路由回归。
- `python -m unittest backend.tests.test_core_crud.CoreCrudTestCase.test_member_filter_options_paging_scope_and_literal_search`：后端排序、分页、范围、特殊字符和认证。
- `python compare_members_fixture.py`：同数据列表几何；当前差异像素占比 2.9428%。

仍未覆盖对标下拉面板的逐像素状态、真实账号的主体可见范围和乱序响应的双端截图，也没有向对标提交筛选业务请求。整体一比一仍未完成。

后续修复：选中游戏或代理商 ID 后点击表格名称快捷搜索，会清除同类旧 ID，避免名称条件和过期 ID 同时提交。其他筛选条件保留。浏览器回归新增从 ID 选择切换到名称搜索的请求断言，确认游戏 ID 被移除、代理商 ID 保留。网络失败用例也改为等待实际 `requestfailed` 事件；此前仅填值后等待不足以证明查询已发出，本次通过真实拦截失败验证已选 ID 保持。

## 异步 ID 回填竞态修复

`verify_member_lookup_races.py` 复现：ID 7200 的名称回填请求尚未完成时，用户打开选项并选择 ID 7201；随后旧请求返回，会把显示名称和隐藏 ID 都覆盖回 7200。修复前测试明确失败，显示 `Old game`。

适配层现给每个控件的请求分配递增版本，并在输入、选择和清空时使旧版本失效。只有仍连接页面且版本匹配的成功或失败回调才能更新控件；未修改供应商源码。新增延迟成功、延迟失败、选择后清空三种浏览器场景，均通过；原选择器主流程回归通过。这证明本地不再被上述旧回填覆盖，不等同于对标服务器语义或全部网络竞态已验收。
