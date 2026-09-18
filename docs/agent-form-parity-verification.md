# 主体新增/编辑表单验证

## 本轮范围

- 主体新增与编辑使用独立表单，不再受通用弹窗的三个字段限制。
- 表单覆盖上级主体、名称、账号、密码、头像地址、用户 ID、角色 ID、安全密钥和四个状态开关。
- 编辑详情只返回表单需要的非密码字段；密码输入框始终为空，留空更新时保持已有密码哈希和盐值。
- 上级主体选项排除当前主体；后端仍校验不存在的上级和循环层级。
- 页面端校验空名称、请求期间锁定控件、保存失败保留表单并显示错误。

## 验证结果

- `python verify_agent_form_browser.py`：通过，新增/编辑请求体、密码留空和空名称阻断均通过。
- `python verify_agents_parity_browser.py`：通过，主体列表、筛选、分页、导出、批量状态、OSS 和权限回归通过。
- `python -m unittest backend.tests.test_core_crud.CoreCrudTestCase.test_agent_game_member_lifecycle backend.tests.test_core_crud.CoreCrudTestCase.test_agent_editor_fields_parent_cycle_and_password_preservation`：通过。
- `python -m unittest discover -s backend/tests -p 'test_*.py'`：78 项通过。
- `node scripts/check-js.cjs`：38 个 JavaScript 文件通过语法检查。

## 尚未证明

参考账号访问 `/agent/add` 和 `/agent/edit/ids/133` 返回无权限外壳，未能取得参考站点表单的字段级截图或提交协议。因此本轮以已验证的主体模型、列表控制器和本地 API 合同实现生命周期表单，不能据此宣称参考表单的每个隐藏字段和像素已一比一复现。
