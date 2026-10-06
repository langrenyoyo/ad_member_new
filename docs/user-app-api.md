# 用户 APP API 接口文档

更新日期：2026-10-07。新增完整设备风控调用契约见第 12 节。

APP 请求日志：服务端新增脱敏 JSON 请求日志，响应头 `X-App-Audit-Id` 可用于排障关联，不影响现有响应 JSON。详见 [请求日志说明](app-request-logging.md)。

本文档面向用户 APP，范围是用户注册、登录、会话恢复、APP 初始化和广告拉取/奖励回调。接口命名空间与管理端隔离，建议统一使用 `/api/app/v1`。

> **当前实现状态**：`/api/app/v1` 已在后端实现。接口包含用户注册、登录、刷新、退出、当前用户、游戏配置、广告会话与奖励幂等结算、广告历史、钱包、金币流水，以及补贴申请、凭证上传和审核结果查询。在线 OpenAPI 可在 `/docs` 的 `User APP` 标签查看。

## 1. 基本信息

| 项目 | 约定 |
|---|---|
| API 前缀 | `/api/app/v1` |
| 登录方式 | 用户 JWT Access Token + Refresh Token |
| 请求格式 | JSON；图片和设备证明按接口要求发送二进制或字符串 |
| 时间格式 | ISO 8601，服务端统一保存 UTC |
| 金币单位 | 非负整数或定点数，具体精度由游戏配置决定 |
| APP 标识 | `app_id`、`app_version`、`platform`、`device_id` |
| 幂等字段 | 写入和广告事件使用 `idempotency_key` 或 `event_id` |

生产环境必须使用 HTTPS。APP 不得保存管理员 token，也不能调用管理端 `/api/v1` 接口代替用户接口。

## 2. 通用请求与响应

### 2.1 请求头

未登录接口：

```http
Content-Type: application/json
X-App-Id: ad-member
X-App-Version: 1.0.0
X-Platform: android
X-Device-Id: <device_id>
```

已登录接口增加：

```http
Authorization: Bearer <user_access_token>
```

`X-Device-Id` 是设备安装实例标识，不使用 IMEI、Android ID 等不可逆性不足或受平台限制的硬件标识。设备变更时必须重新风控校验。

### 2.2 成功响应

单对象：

```json
{
  "data": {},
  "request_id": "req_01J..."
}
```

列表：

```json
{
  "data": {
    "items": [],
    "total": 0,
    "limit": 20,
    "offset": 0
  },
  "request_id": "req_01J..."
}
```

广告完成接口即使重复提交，也应返回第一次结算结果，不能重复增加金币。

### 2.3 错误响应

```json
{
  "detail": "Ad session expired"
}
```

当前业务错误使用 `detail` 字符串；参数校验错误 `422` 的 `detail` 是包含 `loc`、`msg`、`type` 等字段的数组。下面的错误码仅是客户端分类建议，服务端没有统一返回这些字符串，也不保证错误响应带 `request_id` 或 `Retry-After`。

| HTTP | 客户端分类建议 | APP 处理 |
|---:|---|---|
| 400 | `INVALID_ARGUMENT` | 提示字段错误 |
| 401 | `TOKEN_INVALID`、`TOKEN_EXPIRED` | 尝试 refresh；失败后回到登录页 |
| 403 | `ACCOUNT_DISABLED`、`DEVICE_BLOCKED` | 停止业务操作并展示账号/设备状态 |
| 404 | `USER_NOT_FOUND`、`GAME_NOT_FOUND` | 清理本地对象并刷新配置 |
| 409 | `USERNAME_EXISTS`、`IDEMPOTENCY_CONFLICT` | 使用服务端提示，不重复提交 |
| 422 | `PASSWORD_WEAK`、`AD_EVENT_INVALID` | 展示可读校验提示 |
| 429 | `TOO_MANY_REQUESTS`、`AD_RATE_LIMITED` | 按 `Retry-After` 等待后重试 |
| 503 | `AD_PROVIDER_UNAVAILABLE` | 显示暂无广告，不能伪造奖励 |

## 3. 用户注册与登录

### 3.1 注册

```http
POST /api/app/v1/auth/register
```

请求：

```json
{
  "username": "user001",
  "password": "A_strong_password_123",
  "invite_code": "ABC123",
  "agent_id": 133,
  "game_id": 237,
  "device_id": "install-uuid",
  "app_id": "ad-member",
  "app_version": "1.0.0",
  "platform": "android"
}
```

字段：

| 字段 | 必填 | 规则 |
|---|---:|---|
| `username` | 是 | 4-64 个字符；同一注册范围内唯一 |
| `password` | 是 | 至少 8 位，必须包含字母和数字；服务端只保存哈希 |
| `invite_code` | 否 | 用于绑定主体/渠道；无效时返回 `422` |
| `agent_id` | 否 | 已知主体 ID；与 `game_id` 不匹配时拒绝 |
| `game_id` | 否 | 注册来源游戏；必须属于主体 |
| `device_id` | 是 | APP 安装实例 ID |
| `app_id/app_version/platform` | 是 | 客户端版本和平台信息 |

成功 `201`：

```json
{
  "data": {
    "user": {
      "id": 695016,
      "username": "user001",
      "name": "",
      "game_id": 237,
      "agent_id": 133,
      "status": 1,
      "coin": 0,
      "freeze_coin": 0
    },
    "access_token": "<user_access_token>",
    "refresh_token": "<refresh_token>",
    "expires_in": 7200,
    "token_type": "bearer"
  }
}
```

注册必须原子完成：用户名、会员记录、主体/游戏绑定和设备记录任一项失败时全部回滚。

### 3.2 登录

```http
POST /api/app/v1/auth/login
```

请求：

```json
{
  "username": "user001",
  "password": "A_strong_password_123",
  "device_id": "install-uuid",
  "app_id": "ad-member",
  "app_version": "1.0.0",
  "platform": "android"
}
```

成功 `200` 返回与注册相同的 token 结构。账号不存在、密码错误、账号停用统一返回 `401`，不要返回“用户名存在/不存在”的差异化提示。

### 3.3 刷新 token

```http
POST /api/app/v1/auth/refresh
```

请求：

```json
{"refresh_token":"<refresh_token>","device_id":"install-uuid"}
```

服务端轮换 refresh token，旧 refresh token 立即失效。返回新的 `access_token`、`refresh_token` 和 `expires_in`。

### 3.4 退出登录

```http
POST /api/app/v1/auth/logout
Authorization: Bearer <user_access_token>
```

请求可带 `{ "refresh_token": "<refresh_token>" }`。服务端撤销当前 refresh token 和设备会话，成功返回 `204`。

### 3.5 当前用户

```http
GET /api/app/v1/me
Authorization: Bearer <user_access_token>
```

返回用户公开资料、主体/游戏归属、金币余额和当前设备状态。不得返回 `password_hash`、支付密码哈希、内部风控字段或管理员字段。

### 3.6 修改资料和密码

```http
PATCH /api/app/v1/me
Authorization: Bearer <user_access_token>
```

允许字段：`name`、`image_url`、`sex`、`real_name`、`receive_name`、`address`。密码修改单独使用：

```http
POST /api/app/v1/auth/change-password
Authorization: Bearer <user_access_token>
```

```json
{
  "current_password": "old_password",
  "new_password": "new_password_123"
}
```

### 3.7 ????

```http
POST /api/app/v1/auth/wechat-login
```

????? `POST /api/app/v1/auth/wechat`?APP ????? SDK ????? `code`?????????????? `wx_appid` ? `wx_secert` ????? openid???????????? JWT????????? access token ??????? token?

?????

```json
{
  "code": "?? SDK ?????? code",
  "provider": "mini_program",
  "game_id": 237,
  "device_id": "install-uuid",
  "nickname": "????",
  "avatar_url": "https://thirdwx.qlogo.cn/...",
  "app_id": "ad-member",
  "app_version": "1.0.0",
  "platform": "android"
}
```

`provider` ?? `mini_program` ?????? `jscode2session`??? `app` ????????? `sns/oauth2/access_token`?`game_id` ?????????? AppID ? Secret???????????????????????????????? openid???????????????????????????? `user`?`access_token`?`refresh_token` ? `expires_in`?

???????? `503`??? code ???? `401`?????????? `502`????????????? AppID ? Secret???? HTTPS?

## 4. APP 初始化和游戏配置

### 4.1 初始化

```http
GET /api/app/v1/bootstrap?game_id=237
Authorization: Bearer <user_access_token>
```

返回一次 APP 启动所需的最小数据：

```json
{
  "data": {
    "user": {"id": 695016, "username": "user001", "coin": 120, "freeze_coin": 0},
    "game": {"id": 237, "name": "示例游戏", "status": 1, "ad_status": 1},
    "ad_config": {
      "enabled": true,
      "provider": "internal",
      "app_id": "?? App ID",
      "app_key": "?? App Key",
      "placements": [
        {"placement": "splash", "ad_unit_id": "splash-placement-id"},
        {"placement": "native", "ad_unit_id": "native-placement-id"},
        {"placement": "rewarded", "ad_type": "rewarded", "ad_unit_id": "unit-rewarded", "cooldown_seconds": 30, "reward_coin": 10},
        {"placement": "interstitial", "ad_type": "interstitial", "ad_unit_id": "unit-interstitial", "cooldown_seconds": 10, "reward_coin": 0}
      ]
    },
    "server_time": "2026-09-21T12:00:00Z"
  }
}
```

当用户、游戏或广告开关不可用时，返回明确错误；不能通过返回空配置掩盖账号停用或主体/游戏不匹配。

### 4.2 游戏列表

如果一个用户可关联多个游戏：

```http
GET /api/app/v1/games
Authorization: Bearer <user_access_token>
```

只返回当前用户有权限进入、`status=1` 且允许 APP 使用的游戏。游戏列表不是管理端 `/api/v1/games` 的直出结果，服务端必须过滤内部配置字段。

## 5. 广告拉取和奖励

广告接口处理的是一次广告会话。`AdRecord` 是后台历史记录，不能直接作为 APP 广告库存返回。

### 5.1 创建广告会话

```http
POST /api/app/v1/ads/request
Authorization: Bearer <user_access_token>
```

请求：

```json
{
  "game_id": 237,
  "placement": "rewarded",
  "ad_type": "rewarded",
  "device_id": "install-uuid",
  "client_request_id": "client-20260921-0001",
  "risk_check_id": "<device-risk-check-id>"
}
```

成功 `201`：

```json
{
  "data": {
    "ad_session_id": "ads_01J...",
    "request_id": "req_ad_01J...",
    "placement": "rewarded",
    "provider": "ad-network",
    "ad_unit_id": "unit-rewarded",
    "ad_type": "rewarded",
    "reward": {"enabled": true, "coin": 10, "currency": "coin"},
    "session_token": "<short_lived_session_token>",
    "expires_at": "2026-09-21T12:05:00Z"
  }
}
```

服务端必须校验：用户状态、游戏归属、广告开关、设备状态、冷却时间、频控和渠道配置。开启指定游戏的设备风控后，`risk_check_id` 必填且只能使用一次；同一 `client_request_id` 重试时必须原样携带同一个 `risk_check_id`。`coin`、`ecpm`、`reward` 等结算值由服务端决定，APP 不得自行修改。

### 5.2 广告展示/曝光事件

```http
POST /api/app/v1/ads/{ad_session_id}/impression
Authorization: Bearer <user_access_token>
```

请求：

```json
{
  "event_id": "imp-01J...",
  "session_token": "<short_lived_session_token>",
  "occurred_at": "2026-09-21T12:01:10Z"
}
```

成功 `202`。同一 `event_id` 重复提交必须幂等，不能重复生成广告记录。

### 5.3 激励广告完成

```http
POST /api/app/v1/ads/{ad_session_id}/complete
Authorization: Bearer <user_access_token>
```

请求：

```json
{
  "event_id": "complete-01J...",
  "session_token": "<short_lived_session_token>",
  "provider_event_id": "provider-event-id",
  "watched_seconds": 31,
  "occurred_at": "2026-09-21T12:01:41Z"
}
```

成功 `200`：

```json
{
  "data": {
    "ad_session_id": "ads_01J...",
    "status": "rewarded",
    "rewarded": true,
    "coin_added": 10,
    "coin_balance": 130,
    "coin_log_id": 88001
  }
}
```

奖励发放条件：广告会话有效、展示事件存在、观看时长达到配置、provider 回调或签名校验通过、事件未结算。任一条件不满足返回 `422` 或 `409`，不增加金币。

### 5.4 广告失败/关闭

```http
POST /api/app/v1/ads/{ad_session_id}/fail
Authorization: Bearer <user_access_token>
```

请求：`{ "event_id": "fail-01J...", "reason": "NO_FILL" }`。成功 `202`，只结束广告会话，不发放奖励。客户端关闭广告不能调用 `complete`。

### 5.5 广告记录查询

```http
GET /api/app/v1/ads/history?game_id=237&limit=20&offset=0
Authorization: Bearer <user_access_token>
```

只返回当前用户自己的记录：`id、game_id、placement、ad_type、provider、status、coin_added、request_id、watched_at、created_at`。不得接受客户端传入其他 `user_id`。

## 6. 补贴申请

### 6.1 活动、每日名额与资格

后台入口：`http://localhost:3000/#subsidies` → **补贴活动与每日名额**。
运营/超级管理员可新建、编辑、启停活动；审核员可查看活动和审核申请。
新建表单预填每日 50 名、提现门槛 500 分、充值条件 600 分、补贴 1200 分、24 小时审核；这些是截图参考值，活动默认关闭，保存开放后才对 APP 展示。

```http
GET /api/app/v1/subsidy-campaigns?game_id=237
GET /api/app/v1/subsidy-campaigns/{campaign_id}
Authorization: Bearer <user_access_token>
```

列表返回 `data.items/total`，详情返回 `data`。字段包含 `id/title/game_id/enabled`、`daily_quota/used/remaining/quota_date`、
`withdrawal_cents/recharge_cents/reward_cents`（整数分）、`review_hours/instructions`、
`confirmed_withdrawal_cents/eligible/reasons/required_images`。

规则：

- 每日按北京时间 00:00 重置。活动行锁（PostgreSQL）或写事务（SQLite）保护最后一个名额，防止并发超额。
- 同一用户每天每个活动最多申请一次；同一游戏有待审申请时不能再申请。驳回或删除申请不返还当日名额，保留配额记录供追溯。
- 提现门槛只累计该用户、主体、游戏中 `status=1`、`plan_status=1` 且 `transferred_at` 落在当天的金额。创建时间、待审金额、客户端上报金额均不计入。
- 当前提现模型没有广告收益来源标签，因此核验的是同游戏已确认提现总额，不能单独证明这些提现全部来自“当日看广告”；需要严格限定来源时应补充提现来源关联。
- 充值金额、安装来源、应用类型和保留应用要求由审核人员核验凭证，当前没有第三方充值核验或安装存续证明。

提交活动申请：

```http
POST /api/app/v1/subsidy-campaigns/{campaign_id}/applications
Authorization: Bearer <user_access_token>
Content-Type: application/json
```

```json
{
  "request_key": "每次新申请生成的UUID，重试时保持不变",
  "download_image": "/api/member-images/<下载截图文件名>.png",
  "install_image": "/api/member-images/<安装来源截图文件名>.png",
  "recharge_image": "/api/member-images/<充值截图文件名>.png",
  "receive_name": "收件人",
  "receive_tel": "联系方式"
}
```

三张图均必填、必须是已上传的不同地址。金额、会员、主体和游戏由服务端设置。成功返回 `201` 和申请记录；相同用户、请求编号和内容重试返回原记录，相同编号更换内容返回 `409`；原记录已被后台删除时重试返回 `410`。
资格不满足、名额用尽、已申请返回 `409`。用户越权活动返回 `404`，主体/游戏停用返回 `403`。

申请与原有补贴列表共用记录，APP 可通过下述 `/subsidies` 列表及详情查询结果。
响应增加 `campaign`：申请时规则快照、三类 `evidence`、`review_due_at`、`overdue`。历史普通申请的该字段为 `null`。
后台修改活动不改变已有申请金额，活动申请的条件金额、补贴金额和三张凭证不允许编辑；可审核通过或驳回。
超时为页面提示，不会自动审核或打款。

管理接口：`GET/POST /api/v1/subsidy-campaigns`，`PUT /api/v1/subsidy-campaigns/{id}`（提交完整配置）。
活动不提供删除入口，关闭后保留历史；每日名额不能调整到小于当天已用数量。

### 6.2 图片上传与兼容申请

APP 用户只能访问自己的补贴记录。提交前可用图片上传接口上传凭证，再把返回的 URL 放到 `pics` 中。支持 PNG/JPEG/WebP/GIF，单张原图不超过 2MB，宽高各不超过 4096 像素；服务端统一转换为 PNG。请求体是图片二进制，不是 multipart 表单。上传成功返回 `201`。

```http
POST /api/app/v1/subsidies/images
Authorization: Bearer <user_access_token>
Content-Type: image/png

<图片二进制>
```

```json
{"data":{"url":"/api/member-images/<随机文件名>.png"},"request_id":"req_01J..."}
```

未配置活动的游戏仍可使用旧版普通申请；一旦该游戏配置过活动，下面的普通申请入口返回 `409`，必须改用活动申请接口，关闭活动也不能绕过规则。

提交普通申请：

```http
POST /api/app/v1/subsidies
Authorization: Bearer <user_access_token>
Content-Type: application/json
```

```json
{
  "game_id": 237,
  "tx_price": 10.25,
  "pics": ["/api/member-images/<随机文件名>.png"],
  "receive_name": "收款人",
  "receive_tel": "收款账号"
}
```

字段约定：

| 字段 | 约束 |
|---|---|
| `game_id` | 可选，默认当前用户绑定的游戏；必须是同主体的启用游戏 |
| `tx_price` | 必填，提现金额条件（元）；大于 0，最多两位小数、十二位有效数字 |
| `pics` | 可选，最多 9 张；仅接受上传接口返回且仍存在的图片地址 |
| `receive_name` | 必填，收件人，去除首尾空格后 1–64 字符 |
| `receive_tel` | 必填，联系方式，去除首尾空格后 1–64 字符 |

成功返回 `201`，结构为 `{"data":{...申请记录...},"request_id":"..."}`。用户、主体和审核状态由服务端设置；`price` 初始为 0，由后台填写到账金额；`sub_msg` 初始为空，由后台填写审核备注。请求中传入 `price`、`status`、`user_id`、`agent_id` 或其他未定义字段返回 `422`。

同一用户和游戏只能同时存在一条待审核申请，重复或并发提交返回 `409`；此规则不是基于请求键的永久幂等，已处理后允许新申请。停用用户返回 `401`；停用主体或跨主体游戏返回 `403`；不存在或停用游戏返回 `404`；字段或图片不合法返回 `422`。广告开关不影响申请，也不影响查询历史记录。

查询自己的申请：

```http
GET /api/app/v1/subsidies?status=0&limit=20&offset=0
GET /api/app/v1/subsidies/{subsidy_id}
Authorization: Bearer <user_access_token>
```

列表可按 `game_id`、`status` 筛选，`limit` 为 1–100（默认 20），`offset` 默认 0。按申请 ID 倒序，返回 `data.items/total/limit/offset`。详情返回 `data` 单对象；其他用户的记录与不存在的记录均返回 `404`。管理员 token 不能访问 APP 接口，用户 token 不能调用后台审核接口。

状态 `0` 为待审核、`1` 为通过、`2` 为驳回；筛选使用 `status`，兼容字段 `target_status=4` 也表示驳回。`sub_msg` 为后台审核备注，`audited_at` 为审核时间。响应 `pics` 沿用后台的逗号分隔字符串格式（无图为空字符串）。后台列表可直接看到 APP 提交的记录和凭证，修改到账金额、通过或驳回后，APP 查询立即读取同一条记录的最新结果。

审核通过仅代表审核完成；当前补贴模块不调用打款渠道，也不自动增加金币。APP 不应把状态 `1` 展示为支付渠道已确认到账。

## 7. 金币余额和流水

支付宝收款绑定、提现档位、申请、查询及资金冻结规则见 [支付宝提现接口与配置](./alipay-withdrawals.md)。客户端应以 `payout.state=succeeded` 判断到账。

广告奖励需要可核对的余额接口：

```http
GET /api/app/v1/wallet
Authorization: Bearer <user_access_token>
```

```json
{
  "data": {
    "coin": 130,
    "freeze_coin": 0,
    "coin_user": 140,
    "updated_at": "2026-09-21T12:01:41Z"
  }
}
```

流水查询：

```http
GET /api/app/v1/wallet/coin-logs?limit=20&offset=0
Authorization: Bearer <user_access_token>
```

每条流水必须返回 `id、type、coin_before、coin、coin_after、remark、source_id、created_at`。APP 端只读，不能直接修改余额或流水。

## 8. 服务端状态机和幂等要求

广告会话状态建议为：

```text
issued -> impressed -> completed -> rewarded
issued -> failed
issued/impressed -> expired
```

- `request_id`、`ad_session_id`、`event_id`、`provider_event_id` 必须建立唯一约束或等价幂等记录。
- 完成事件和金币流水必须在同一数据库事务中提交。
- 重复完成事件返回首次结算结果，不能二次加金币。
- APP 传入的金额、ECPM、广告类型、奖励金币只能作为上下文，不能作为结算依据。
- 广告 provider 的服务端回调应单独校验签名；不能只信任 APP 上报的 `watched_seconds`。

## 9. 当前后端接口状态

| APP 需求 | 当前代码状态 | 处理结论 |
|---|---|---|
| 用户注册、登录 | 已实现 `/api/app/v1/auth/register`、`/auth/login` | 使用用户 JWT |
| 用户 token 刷新/退出 | 已实现 `/api/app/v1/auth/refresh`、`/auth/logout` | 按用户会话调用 |
| APP 拉广告 | 已实现 `/api/app/v1/ads/request` | 开启风控时提交 `risk_check_id` |
| 广告曝光/完成 | 已实现广告会话事件接口 | TAKU 奖励以服务端验签回调为准 |
| 用户金币余额、流水 | 已实现 `/api/app/v1/wallet`、`/wallet/coin-logs` | 从用户 token 确定范围 |
| 用户广告历史 | 已实现 `/api/app/v1/ads/history` | 仅查询本人记录 |
| 补贴、支付宝提现 | 已实现 APP 申请、账号绑定和状态查询接口 | 真实支付宝支付仍需生产联调 |
| 设备风控 | 已实现 config、challenge、verify 和广告准入校验 | 尚需部署及阿里云真机联调 |

## 10. 对接与发布顺序

1. 对接用户登录、刷新 token、初始化和原有业务接口。
2. 按第 12 节接入设备校验及广告请求参数，识别关闭时兼容原流程。
3. 部署数据库迁移、后端及静态资源，配置阿里云增强版设备风控凭据。
4. 真机验证 token 与 biz_id、设备关联、重装信号、限次及 TAKU 发奖回调。
5. 完成验证后按游戏开启风控。代码实现和模拟测试通过不等于线上已启用。
6. 在线文档为 `/docs`，完整 OpenAPI 为 `/openapi.json`；只对接其中 `/api/app/v1` 路径。当前没有独立 `/api/app/v1/openapi.json` 路由。

## 11. APP 联调验收清单

- 注册成功后能直接获得用户 token，用户名重复返回 `409`。
- 管理员 token 不能访问用户 APP 接口，用户 token 不能访问管理端接口。
- 停用用户、错误密码、过期 token 和 refresh token 撤销均有明确处理。
- 用户只能读取自己的资料、金币、广告会话和广告历史。
- 广告请求受到游戏开关、设备状态、冷却时间和频控约束。
- 同一曝光/完成事件重复提交不会重复写入或重复发放金币。
- provider 无广告或不可用时返回 `503`，APP 不显示成功奖励。
- 完成事件未经服务端验证时不增加金币。
- 金币余额和流水在奖励事务提交后保持一致。

文档生成依据：当前 `Member`、`AdRecord`、`CoinLog` 数据模型、管理端路由鉴权逻辑和广告字段定义。新增 APP 路由后，应重新导出 OpenAPI 并同步本文件。


## 12. 清机 / 双清设备风控接口

本节是 Android APP 必须使用的完整调用契约。阿里云 SDK 集成本身不会自动完成服务端校验，调用顺序必须是：

`config → challenge → Aliyun getDeviceToken(biz_id) → verify → ads/request(risk_check_id)`。

### 12.1 查询风控配置

```http
GET /api/app/v1/device-risk/config?game_id=238
Authorization: Bearer <user_access_token>
```

响应 `200`：

```json
{
  "data": {"enabled": true, "limit_enabled": true, "daily_limit": 10},
  "request_id": "req_01J..."
}
```

`enabled=false` 时无需调用 challenge/verify，按普通广告流程请求。`limit_enabled=true` 一定要求 `enabled=true`。

### 12.2 获取一次性校验挑战

```http
POST /api/app/v1/device-risk/challenge
Authorization: Bearer <user_access_token>
Content-Type: application/json

{"game_id":238,"install_id":"install-uuid-created-on-first-launch"}
```

`install_id` 为 APP 本地持久化的随机 UUID，长度 16–128；正常启动和升级不能重新生成。接口返回 `201`：

```json
{
  "data": {
    "challenge_id": "<challenge-id>",
    "biz_id": "<challenge-id>",
    "expires_at": "2026-10-07T08:05:00Z"
  },
  "request_id": "<challenge-id>"
}
```

`biz_id` 必须原样传给 Android SDK 的 `getDeviceToken(biz_id)`。SDK 调用应在工作线程，并遵守阿里云 SDK 初始化后的等待要求。挑战有效期 5 分钟，每个会员每分钟最多创建 10 次。

### 12.3 提交阿里云设备 token

```http
POST /api/app/v1/device-risk/verify
Authorization: Bearer <user_access_token>
Content-Type: application/json

{"challenge_id":"<challenge-id>","aliyun_device_token":"<SDK-device-token>"}
```

响应 `200`：

```json
{
  "data": {
    "risk_check_id": "<challenge-id>",
    "device_id": 12,
    "suspected_reset": false,
    "limited": false,
    "daily_limit": 10,
    "used": 0,
    "remaining": null
  },
  "request_id": "<aliyun-request-id>"
}
```

`remaining=null` 表示当前设备不受限次规则限制；风险设备限次时返回剩余批准次数。服务端只保存设备标识和 token 的哈希，不把原始 token 返回或写入日志。

| 字段 | 类型 / 约束 | 说明 |
|---|---|---|
| 请求 challenge_id | 字符串，20–64 字符 | 必须属于当前登录用户 |
| 请求 aliyun_device_token | 字符串，10–16384 字符 | SDK 原样返回，不能使用客户端设备 ID 代替 |
| 返回 risk_check_id | 字符串 | 服务端广告准入凭证，与 challenge_id 相同 |
| 返回 device_id | 整数 | 后台内部设备记录 ID，不能替代广告请求中的客户端 device_id |
| 返回 suspected_reset | 布尔 | 当前有效风险状态，包含人工处置结果，不是物理双清证明 |
| 返回 limited | 布尔 | 当前风险状态和限次开关共同决定 |
| 返回 used | 整数 | 当前游戏当天设备次数与当前账号次数的较大值 |
| 返回 remaining | 整数或 null | 校验时快照，最终准入以广告申请结果为准 |

有效期从 challenge 创建起算 5 分钟，verify 成功不会延长有效期，也不会消费广告次数。一次 challenge 只能尝试一次云端验证；失败后或验证响应丢失时重新申请 challenge，不要反复提交同一个 verify。

### 12.4 携带校验凭证申请广告

在原 `POST /api/app/v1/ads/request` 请求中增加：

```json
{"risk_check_id":"<risk_check_id>"}
```

完整示例：

```json
{
  "game_id": 238,
  "placement": "rewarded",
  "ad_type": "rewarded",
  "device_id": "install-uuid",
  "client_request_id": "client-20261007-0001",
  "risk_check_id": "<risk_check_id>"
}
```

校验凭证只能批准一个新的广告会话。客户端超时重试必须使用原 `client_request_id` 和 `risk_check_id`，服务端不会重复扣除广告次数。挑战过期、校验失败或限次用尽时，不得继续展示新广告。

### 12.5 风控错误处理

当前后端错误响应使用 FastAPI 标准格式 `{"detail":"..."}`：

| HTTP | 典型原因 | APP 处理 |
|---:|---|---|
| 401 | 用户 token 无效或过期 | refresh，失败后重新登录 |
| 403 | 广告校验凭证缺失、过期、已消费、归属错误或重试凭证不匹配 | 新申请重新校验；原会话重试须保留原凭证 |
| 404 | challenge 不存在或不属于当前用户 | 丢弃本地凭证，重新申请 |
| 409 | challenge 已使用、已过期或游戏未开启识别 | 刷新配置后重新申请 |
| 422 | 请求字段不符合长度/格式要求 | 修正参数，不要重试原请求 |
| 429 | challenge 频率超限 | 等待一分钟后再尝试，不要循环请求 |
| 429 | 风险设备达到每日上限 | 当天停止新广告申请；北京时间零点刷新额度，配置为 0 时仍禁止 |
| 503 | 阿里云凭据未配置、调用失败或未返回设备标识 | 暂停新广告申请，稍后重试；不能伪造设备码 |

服务端限次按北京时间自然日统计“已批准广告会话”，同一游戏同一设备跨账号共享额度；失败广告不退还次数，已批准广告的 TAKU 回调发奖不受影响。

### 12.6 APP 联调检查

- 确认请求头携带用户 `Authorization`，不能使用管理端 token。
- 确认每次 token 都使用本次 challenge 返回的 `biz_id`，不能用固定 bizId 或复用其他游戏的 token。
- 确认 APP 清数据/重装时按产品策略生成新的 `install_id`，并接受服务端只返回“疑似清数据或重装”的风险信号。
- 确认广告申请、曝光、完成仍按第 5 节接口执行；设备风控只负责新广告会话准入，不替代 TAKU 服务端回调签名验证。

完整部署、阿里云权限和限制说明见 [设备风控部署说明](device-risk.md)。
