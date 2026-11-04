# 注册推荐码开关

后台入口：风控管理 → 设备风控 → APP 业务规则 → 输入游戏 ID 并加载 → 会员准入。

“强制推荐码注册（团长 / 代理）”按游戏独立保存，默认开启，旧配置未包含该字段时也保持开启。

- 开启：密码注册、短信首次注册、微信首次注册必须提供有效推荐码。
- 关闭：推荐码可留空注册，上级 ID 为 0；主动填写时仍须校验，错误推荐码不会被静默忽略。
- 邀请码为 6 位英文字母和数字组合（不区分大小写）。推荐人必须是本应用中启用的团长或代理；普通用户、停用用户、其他应用用户的邀请码均无效。旧邀请码在迁移后失效。
- 注册失败会回滚账号创建及绑定；已有账号登录不要求重复输入推荐码。
- “未绑定账号须补绑上级（限制业务使用）”为独立规则；即使允许无推荐码注册，该规则仍可要求未绑定用户在使用业务功能前补绑。

配置字段：`require_registration_invite`，存储在游戏 `settings_json.member_policy`，无需数据库迁移。

后台 GET/PUT `/api/v1/games/{game_id}/member-policy` 读写该字段；保存仅限超级管理员并记录操作审计。APP 公共接口 GET `/api/app/v1/policy?game_id=...` 返回该字段。

验证：`python -m pytest backend/tests/test_registration_invite.py backend/tests/test_member_policy.py -q`，`python scripts/verify_member_policy_ui.py`，`npm run check`。

Android 注册页文案同步改为“上级推荐码”，说明是否必填由应用规则决定；手机上旧版本的必填文案需更新 APK 后才会改变，注册是否允许由服务端实时校验。
