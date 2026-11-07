# app-release20261107.apk 与后台一致性分析（2026-11-07）

## 结论

主要用户接口兼容，但当前不能判定 APP 与线上后台完全一致，补贴“审核通过即增加金币”的需求在线上尚未生效。

- 新 APK 已修复补贴活动重复请求第一页：实际带上 `limit=20&offset=...`。
- 线上后台仍运行旧版审核实现，只更新状态和审核信息，不增加金币；本地的金币到账修复尚未部署。
- APK 的补贴界面仍显示人民币金额和“已通过”，未直接展示补贴到账金币或兑换比例。钱包和金币流水接口可以承载到账结果，但申请详情缺少结构化的到账金币字段。
- 活动分页的结束判断还有一个小问题：总数恰好为 20、40 等整页时，多显示一次“加载更多”，再请求一个空页后才停止。

本次仅分析与只读核验，没有修改业务代码、部署服务、审核真实申请或执行真实资金操作。

## 核查对象

| 项目 | 实际值 |
| --- | --- |
| APK 文件 | `app-release20261107.apk` |
| SHA256 | `78fd7c1345772034106dcd64766e2a604a27bcc523a1f6a046fb28e61eff0d62` |
| 包名 | `com.heshangzhilian.yazhiyiji` |
| versionName / versionCode | `1.0 / 1` |
| APK 构建提交 | `91e9f000bcfd1bbe90cf6eb1c9c8508fd6e78800` |
| APK API 根地址 | `https://admember.yunjizhilian.asia/api/app/v1/` |
| 注册游戏 ID | `238` |
| 本地 Android 仓库 HEAD | `458b991f371eb23082de4e8bc29b47f1f1e6c98f`，另有工作区修改 |
| 线上后台仓库 HEAD | `77b343210ae8f6642db9defb3ced833ed4e5e3e3` |

APK 构建提交与本地 Android HEAD 不同，以下客户端判断来自 APK 实际反汇编，未用本地工作区代替发布包。

## 功能与接口对照

用户端路径以下均省略 `/api/app/v1/` 前缀。

| 功能 | APK 调用及解析 | 当前后台对应情况 |
| --- | --- | --- |
| 密码注册、登录、刷新、退出 | `auth/register`、`auth/login`、`auth/refresh`、`auth/logout` | 路径、请求模型和认证方式有对应；本次未登录生产账号 |
| 短信、微信与设置密码 | `auth/sms/*`、`auth/wechat`、`auth/wechat-password` | 有对应接口；真实短信送达、微信签名/授权未在本次真机验证 |
| 注册邀请码开关 | 登录前请求 `policy?game_id=238`，解析注册策略 | 支持 `require_registration_invite`；线上本次读取为 `true`，不再仅依赖旧 APK 固定提示 |
| 我的邀请码、上级绑定 | 读取 `onboarding.invite_code`；`POST onboarding` | 所有会员生成六位英文/数字邀请码；注册及绑定的有效邀请人仍限制为同游戏团长/代理 |
| 资料、头像、密码 | `me`、`auth/change-password`、`subsidies/images` | 有对应；上传使用原始图片二进制 |
| 首页公告 | 读取 `onboarding.policy.announcement` | 有后台配置和下发；游戏 238 的公开策略本次返回空公告 |
| 补贴活动列表 | `subsidy-campaigns?game_id=...&limit=20&offset=...` | 旧参数兼容；分页重复第一页已修复，整页结束判断仍有小问题 |
| 活动详情、规则、资格 | `subsidy-campaigns/{id}`，读取 `instructions/eligible/reasons` 等 | 字段与当前实现对应 |
| 上传和活动申请 | `subsidies/images`；`subsidy-campaigns/{id}/applications` | `request_key`、三种图片字段、联系信息对应；金额由服务端活动快照设置 |
| 普通申请、申请记录 | `subsidies`、`subsidies/{id}` | 路径和字段对应；配置过活动的游戏不能绕过活动入口提交普通申请 |
| 补贴审核到账 | 申请页展示 `status/price/sub_msg`；钱包及流水可查询金币 | 本地已实现金币发放；线上仍为旧逻辑，不发金币 |
| 钱包、金币流水 | `wallet`、`wallet/coin-logs?limit=20&offset=...` | 路径及字段对应，数字字符串可由客户端 Decimal 解析 |
| 团队、分佣 | `commission-team`、`commissions`，读取 `summary` | 有对应，旧分页参数仍兼容 |
| 支付宝及提现 | `me/alipay`、`withdrawal-options`、`withdrawals` | 有对应接口；现金提现与补贴金币到账是不同链路，本次未验证真实出款 |
| 广告与设备风控 | `bootstrap`、`ads/*`、`device-risk/*`、`usage`、`device-observations` | 有对应接口；平台回调、设备 SDK 和真实奖励需真机联调 |
| 成语答题、收藏、错题、学习统计 | APK Room 数据库和 `QuizRepository` | 主要为本机数据，未发现对应的云端学习数据同步链路 |

线上与本地 OpenAPI 的 **48 项用户端操作**一致：没有缺失路径、方法、参数或所引用请求模型的差异。这证明接口定义一致，不代表处理函数内部逻辑和生产结算结果一致。

## 具体问题及证据

### 1. 优先处理：线上没有部署补贴金币到账修复

只读检查确认：

1. `admember.yunjizhilian.asia` 的 Nginx 配置转发到 `127.0.0.1:8001`。
2. 该 Uvicorn 服务使用 `--app-dir /www/wwwroot/ad_member_new/backend`，进程工作目录为 `/www/wwwroot/ad_member_new`。
3. 该目录 Git HEAD 是 `77b3432`，本次核查的三个后台源文件没有服务器工作区修改。
4. 服务器 `approve_subsidy()` 仍执行 `item.status = 1`、`mark_audit()`、`session.commit()`，没有余额更新、金币流水或 `grant_subsidy_coins()` 调用。
5. 服务器没有本地新加的 `SUBSIDY_COIN_LOG_TYPE = 302`、`grant_subsidy_coins()`。本地补贴活动和会员策略模块经统一换行后与服务器一致，差异集中在本地修改过的主模块。

因此，新 APK 配合当前线上后台，补贴审核通过仍不会增加金币。解决这一项需要部署已有后台修复并重启对应服务；仅替换 APK 不会生效。本次没有执行部署。

本地已完成的规则是：申请补贴金额（元）乘以审核时游戏策略的 `coins_per_yuan`，保留六位小数向下截断；状态、余额、累计收入与 `type=302` 流水同一事务提交，并防止重复发放。历史已通过记录不自动补发。

### 2. 补贴列表与详情没有明确展示金币到账

APK 实际文案仍为：

- 活动列表：`奖励 ¥{reward_cents / 100}`。
- 申请列表及详情：`补贴金额 ¥{price}`。
- 状态：`待审核 / 已通过 / 已驳回`。
- 申请表仍使用“收款姓名”“收款账号”。

`price` 和 `reward_cents` 在后台仍以元和分保存，因此这些金额的数值单位没有解析错误；问题是没有明确告诉用户最终以金币发放，也没有在申请详情展示实际到账金币。

APK 有读取 `wallet` 与 `wallet/coin-logs` 的能力，因此后台修复部署后，可在钱包及流水看到到账。申请详情接口目前没有结构化的 `credited_coin`、实际兑换比例或关联流水 ID，不能直接用申请金额推断历史实际到账；兑换比例可能在审核前后变化，历史通过记录也不会自动补发。若要求在每笔申请详情显示到账金币，需要后台补充这类字段并接入 APP。

证据：`MemberCenterScreenKt.smali` 的约 7091、7192、7404 行，以及本地 `_app_subsidy_payload()`。

### 3. 补贴分页已修复，但整页结束判断没有对齐后台

APK 维护 `campaignPage`：首次/刷新设为 1，下一页偏移为 `(campaignPage + 1 - 1) × 20`，请求成功后增加页数。因此正常偏移依次为 `0、20、40`，网络失败不会提前跳页。

但活动分支将 `hasMore` 设置为 `loadedCount >= campaignPage × 20`，没有采用后台 `has_more` 或比较 `loadedCount < total`。

| 活动总数 | APK 行为 |
| --- | --- |
| 45 | 请求 20 / 20 / 5 条，正常停止，无旧版重复第一页问题 |
| 20 | 首次已加载完全部 20 条，仍显示加载更多；再请求 `offset=20` 的空页后停止 |
| 40 | 第二页已加载完全部 40 条，仍显示加载更多；再请求 `offset=40` 的空页后停止 |

这是结束提示和多余请求问题，不会把第一页重复追加，也不阻止读取后续活动。建议使用服务端 `data.has_more` 或 `loadedCount < data.total`。

证据：`MemberCenterViewModel$load$1.smali` 约 631 行的请求构造、819 行之后页数推进，以及约 927 行的总已加载数量判断。

### 4. 补贴公告仍是基础公告与活动说明两条配置

APP 首页通用公告读取 `onboarding.policy.announcement`，活动详情读取 `instructions`。它们都有后台对应配置，但两者独立，不会互相修改活动规则、金额和公告正文。

本次只读请求游戏 238 的公开策略，`announcement` 为空，因此当前没有可由这一配置展示的首页公告正文。这是当前配置状态，不是请求失败。没有发现专属补贴公告列表、公告历史、定时发布或已读回执等独立模块；若验收仅要求首页文字和活动领取说明，已有基本对应。

## 验证范围与结果

- APK 静态核验：manifest、构建元数据、业务 API、认证刷新、会员中心、补贴提交及显示、注册策略解析等实际包内代码。
- 线上只读 HTTP：`GET /api/health` 返回 `200 {"status":"ok"}`；OpenAPI 返回 200；游戏 238 公开策略返回 200。未认证 bootstrap 返回 401，与认证要求一致。
- 线上只读 SSH：确认域名转发、运行服务路径、后台提交与实际审核函数，没有执行部署或审核。
- 本地隔离测试：`test_app_subsidies.py`、`test_app_pagination.py`、`test_member_policy.py`，**58 passed，86 subtests passed**；仅有两条 SQLite datetime 弃用警告。
- 没有安装新 APK 或进行真机点击、生产账号登录、真实提现、真实广告奖励和实际补贴到账操作，因此不将上述静态/隔离验证表述为生产全流程验收通过。
- APK 仍使用 `versionCode=1`；与旧包相同。后续正式分发版本应递增该值，版本号问题与 API 兼容性分别处理。

## 本次证据文件

位于 `artifacts/apk-audit-20261107/`：

- `metadata.json`、`manifest.xml`：包身份和构建来源。
- `*.smali`、`ui-strings.txt`：APK 实际业务逻辑和界面文字。
- `openapi-comparison.json`：本地与线上用户端接口对比结果。
- `online-policy.json`、`online-health.json`：只读公开接口响应。
- `server-source-check.json`、`server-runtime-check.json`：服务器源码、运行路径和域名转发证据。原始字节哈希受换行影响，应以 `server-runtime-check.json` 的统一换行比对为准。

建议交付顺序：先部署本地补贴金币到账修复，再补齐 APP 到账说明/详情展示并修正活动分页结束判断，最后用真机走完申请、审核、钱包及流水核对。
