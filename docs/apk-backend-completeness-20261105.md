# 邀请码版 APK 与后台功能对应核查（2026-11-05）

核查对象：`鸭只易记-v1.0-release-邀请码版-20261104-222625.apk`。

结论：主要会员业务具备对应后台接口；补贴活动的配置、说明展示、资格校验、申请、审核和结果查询已实现。但独立的“补贴公告中心”未发现实现，补贴审核通过也不会自动打款或增加金币。因此不能据此认定补贴业务已经形成完整的资金闭环，或生产环境已经全部可用。

**核查范围与证据**

- APK 包名 `com.heshangzhilian.yazhiyiji`，版本 `1.0`，versionCode `1`。
- SHA256：`890CDD495807A51BC8439916D77165919113A0E875B24EAF14780AFC6748A40D`。
- 包内构建元数据记录源码提交 `458b991f371eb23082de4e8bc29b47f1f1e6c98f`。
- 本地 Android 仓库同在该提交，另有三个未提交文件：`UserAppApi.kt`、`IdiomQuizApp.kt`、`MemberCenterViewModel.kt`。差异涉及分页和邀请码输入提示；没有将这些工作区差异直接当作 APK 行为。
- 对 APK 的首页公告渲染、补贴详情渲染和公告刷新协程进行了反汇编核对。APK 确实读取 `announcement`、`instructions`，并存在每 60 秒调用 `refreshOnboarding()` 的代码。
- 本次没有安装 APK、登录线上账号或检查服务器数据库，结论基于发布包静态分析、本地源码和隔离环境测试。接口存在与线上已部署、已配置、已通过真机验收分别判断。

**主要功能对应情况**

| APP 功能 | 对应后台 | 当前判断与边界 |
| --- | --- | --- |
| 密码注册、登录、刷新及退出 | `auth/register`、`auth/login`、`auth/refresh`、`auth/logout` | 有实现 |
| 短信和微信登录 | `auth/sms/*`、`auth/wechat` | 有实现；真实平台凭据、短信送达和 APK 签名匹配未在本次验证 |
| 资料、头像与修改密码 | `me`、`auth/change-password`、`subsidies/images` | 有实现；头像复用图片上传接口 |
| 邀请码、上级绑定、团队与分佣 | `invite-code`、`onboarding`、`commission-team`、`commissions` | 有实现；当前后端为六位英文或数字邀请码，普通会员也可获得；强制注册仅接受本应用有效团长或代理的邀请码 |
| APP 首页公告 | 会员策略 `announcement` → `onboarding.policy.announcement` | 基础配置、下发、展示链路已实现 |
| 补贴活动与规则说明 | `subsidy-campaigns`、`subsidy-campaigns/{id}` | 有管理端编辑和 APP 详情展示 |
| 补贴申请、凭证、审核与结果 | 活动申请接口、`subsidies`、`subsidies/images`、管理端审核接口 | 申请与审核链路已实现；不包含补贴自动付款 |
| 钱包、金币与广告记录 | `wallet`、`wallet/coin-logs`、`ads/*` | 有实现；真实广告回调与实际奖励仍须线上验收 |
| 支付宝绑定与提现 | `me/alipay`、`withdrawal-options`、`withdrawals` | 有实现及支付宝适配代码；本次未验证生产打款配置与真实到账，提现付款不能视作补贴付款 |
| 设备风控与应用使用情况 | `device-risk/*`、`usage` | 有服务端实现；真实 SDK、授权与风控平台联调不在本次验证范围 |
| 成语题库、答题、收藏、错题和学习进度 | `QuizRepository`、Room 数据库及本地设置 | 主要为本地功能；未发现这些学习数据的云端同步链路 |

上述接口均以 `/api/app/v1/` 为用户端前缀，管理端以 `/api/v1/` 为前缀。

**“补贴公告”需要区分的两条现有链路**

1. 首页通用公告：后台“设备风控 → APP 业务规则”选择游戏 ID，填写公告内容并保存。写入接口为 `PUT /api/v1/games/{game_id}/member-policy`，要求超级管理员权限；内容保存在游戏 `settings_json.member_policy` 中。APP 登录后从 `GET /api/app/v1/onboarding` 读取，在首页展示非空公告。APP 处于前台 RESUMED 状态时每 60 秒发起规则刷新；网络成功、认证有效的情况下更新内容，不是服务端主动推送。
2. 补贴活动说明：后台“补贴申请 → 补贴活动与每日名额”创建或编辑活动，可配置名称、启停、每日名额、提现门槛、充值条件、补贴金额、审核时限和领取说明 `instructions`。超级管理员或运营可保存。APP 在“我的 → 会员中心 → 补贴活动 → 查看详情”读取说明和规则；可点击“刷新资格”重新获取详情。活动列表不会作为独立补贴公告中心显示。

首页公告可以写补贴通知，活动说明可以写领取规则，两者均已有后台支持；但它们是两份独立数据，修改其中一份不会自动更新另一份。公告文本中的金额也不会自动修改活动规则，最终申请条件和金额以服务端活动配置为准。

未发现独立补贴公告的数据模型、分类接口、公告列表/历史、定时发布、失效时间、已读记录、强制确认或补贴公告专属展示页。后台虽提供 `announcement_version`，当前 Android 代码未使用该字段做版本识别或已读控制。如果需求只是“后台修改一段文字并在首页显示”，现有基础功能满足；如果要求独立“补贴公告”模块，则尚未补齐。

关键实现位置：

- `public/member-policy.js:19`、`:24`：公告版本和内容编辑。
- `backend/app/member_policy.py:258`：策略保存与权限；`:317`：onboarding 下发。
- `apk/test_android/app/src/main/java/com/example/idiomquiz/ui/IdiomQuizApp.kt:165`：前台周期刷新；`:412`：首页公告展示。
- `public/subsidies.js:20`：活动编辑表单与领取说明。
- `backend/app/subsidy_campaigns.py:17`、`:45`：活动字段和输入约束；`:144`、`:161`、`:168`：列表、详情与申请。
- `apk/test_android/app/src/main/java/com/example/idiomquiz/ui/MemberCenterScreen.kt:203`：补贴详情说明与规则展示。

**补贴业务仍需关注的缺口**

- 审核通过只更新补贴审核状态、审核时间等字段，没有调用支付渠道，也没有增加金币。若用户应在审核通过后自动收到补贴，需要补贴付款订单、幂等付款、结果查询、失败处理及对账链路。证据：`backend/app/main_from_txt.py:6550` 和 `docs/user-app-api.md:622`。
- 充值金额真实性、安装来源等依赖人工核对截图；服务端资格检查使用当天已确认提现记录。活动规则中的审核小时数用于截止时间和超时提示，不代表到期自动审核、自动付款或发送通知。
- 活动新建默认关闭；APP 列表仅返回符合主体与游戏范围的已开放活动。生产数据库需完成创建 `subsidy_campaigns` 与 `subsidy_reservations` 的迁移，相关版本为 `e926_subsidy_campaigns`。本次未检查服务器迁移和真实活动配置。
- 一个游戏配置过活动后，即使活动关闭，普通补贴申请接口仍返回 409，要求通过活动入口申请；活动关闭期间可能没有可申请入口。这是当前明确实现的规则，需要运营理解。

**本次验证结果**

- `python -m pytest backend/tests/test_app_subsidies.py backend/tests/test_member_policy.py -q`：46 passed，20 subtests passed；2 条 Python 3.12 SQLite datetime 适配器弃用警告。
- 覆盖补贴申请/查询、凭证限制、归属与权限、活动规则快照、幂等重试、最后一个名额并发、北京时间资格，以及公告配置、会员策略、邀请码和分佣等相关逻辑。
- `python scripts/verify_subsidy_campaign_ui.py`：使用临时数据库和隔离 HTTP 服务，管理端真实浏览器创建、编辑、启用活动，刷新后数据保留，无浏览器脚本错误。
- APK 反汇编证据输出到 `artifacts/release-IdiomQuizAppKt.smali`、`artifacts/release-MemberCenterScreenKt.smali`、`artifacts/release-announcement-refresh.smali`。

建议先确认补贴公告的验收口径：现有首页通知和活动领取说明可以配置使用；独立公告模块和补贴自动到账应分别作为尚需补齐的功能，不应按“后台已有补贴接口”直接验收通过。
