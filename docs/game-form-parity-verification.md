# 游戏新增/编辑表单验证

## 本轮实现

- 普通游戏管理页支持新建和编辑，主体游戏页支持同一套完整表单。
- 表单覆盖 `GameCreate` / `GameUpdate` 的主体、基础信息、运行参数、分佣提现、微信和 `settings_json` 字段。
- 主体游戏页将当前主体 ID 锁定在请求体中，编辑时拒绝不属于当前主体的游戏。
- 数值字段转换为 Number；整数和空值、游戏名称、JSON 配置均在提交前校验。
- 保存期间锁定控件；请求失败保留输入并显示错误；关闭、切换路由和过期请求不会污染后续表单。
- 弹窗使用与主体编辑一致的深色标题栏、底部操作栏、双列布局和移动端单列滚动布局。

## 验证结果

- `python verify_game_form_browser.py`：通过，普通页新增/编辑、主体 ID 锁定、数值转换、空名称和非法 JSON 阻断通过。
- `python verify_agent_games_fixture.py`：通过，主体游戏分页、排序、筛选、重置和空状态通过。
- `python verify_game_table_markup.py`：通过，通用游戏表分页、列设置、筛选和空状态通过。
- `python verify_agent_form_browser.py`：通过，主体表单回归通过。
- `python verify_agents_parity_browser.py`：通过，主体列表、筛选、分页、导出、批量状态、OSS 和权限回归通过。
- `node scripts/check-js.cjs`：39 个 JavaScript 文件通过语法检查。
- `python -m unittest discover -s backend/tests -p 'test_*.py'`：78 项通过。

## 范围说明

参考站点的主体游戏新增/编辑 URL 对当前账号返回无权限外壳，因此无法取得真实表单的字段级截图和提交协议。本轮以已验证的参考游戏控制器、现有本地游戏模型和 API schema 完成可用的生命周期表单，不能据此宣称隐藏字段和像素细节全部一比一。
