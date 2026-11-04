# 会员身份管理

会员管理列表新增“会员身份”列及同名筛选项，支持用户、团长、代理。点击列表中的身份可直接筛选；筛选随分页及导出请求保留。

会员管理 → 编辑 → 基础信息 → 会员身份，可由超级管理员修改。资料与身份在同一个事务保存，失败时回滚；操作员可编辑原有资料，但身份只读。身份变更记录操作审计。

身份读取已有 `member_enrollments.level`，未有记录的会员显示为用户，不迁移或重置现有身份。旧版身份修改接口继续使用同一字段。VIP、旧版代理标记与会员身份为独立字段。团长和代理的邀请码资格及分佣继续按已有业务规则执行；各身份分佣比例仍在应用业务规则中统一配置。

接口新增内容：

- GET `/api/v1/members` 支持 `member_level=0|1|3`，返回 `member_level`、`member_level_name` 和身份修改权限。
- GET `/api/v1/members/{id}` 返回身份及 `can_edit_member_level`。
- PATCH `/api/v1/members/{id}` 支持整型 `member_level`，仅超级管理员可提交，拒绝空值及其他等级。

2026-11-02 页面统一：会员管理移除 VIP 列、筛选、列设置及编辑项；用户提现、补贴申请将 VIP 列及筛选替换为会员身份。两页列表接口新增 `member_level=0|1|3`，返回身份值及名称，分页、导出沿用筛选。无身份记录的会员视为用户；会员已不存在的历史申请显示“会员不存在”，不混入用户身份筛选。历史 VIP 数据及接口兼容字段保留，不执行数据清理。

验证：`python -m pytest backend/tests/test_member_levels.py backend/tests/test_member_policy.py backend/tests/test_registration_invite.py -q`；`python scripts/verify_member_levels_ui.py`；`npm run check`。
