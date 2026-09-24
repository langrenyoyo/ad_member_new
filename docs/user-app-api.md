# 用户 APP API 接口文档

本文档面向用户 APP，范围是用户注册、登录、会话恢复、APP 初始化和广告拉取/奖励回调。接口命名空间与管理端隔离，建议统一使用 `/api/app/v1`。

> **当前实现状态**：本文档是用户 APP 的目标接口契约，当前后端尚未注册 `/api/app/v1` 路由。现有 `/api/auth/login` 是管理员登录接口，`/api/v1/members` 是管理端会员 CRUD，`/api/v1/ads` 是管理端广告历史明细查询，均不能直接给用户 APP 使用。

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
  "error": {
    "code": "AD_SESSION_EXPIRED",
    "message": "广告会话已过期",
    "details": {}
  },
  "request_id": "req_01J..."
}
```

| HTTP | 错误码示例 | APP 处理 |
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
      "placements": [
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
  "client_request_id": "client-20260921-0001"
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

服务端必须校验：用户状态、游戏归属、广告开关、设备状态、冷却时间、频控和渠道配置。`coin`、`ecpm`、`reward` 等结算值由服务端决定，APP 不得自行修改。

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

## 6. 金币余额和流水

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

## 7. 服务端状态机和幂等要求

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

## 8. 与当前后端的差异

| APP 需求 | 当前代码状态 | 处理结论 |
|---|---|---|
| 用户注册 | 只有管理员可调用的 `POST /api/v1/members` | 需要新增 APP 注册接口和用户鉴权 |
| 用户登录 | `/api/auth/login` 只校验 `AdminUser` | 不能复用，需要用户 JWT |
| 用户 token 刷新/退出 | 没有用户会话接口 | 需要新增 refresh token 撤销机制 |
| APP 拉广告 | `/api/v1/ads` 受管理员鉴权保护，返回历史明细 | 需要新增广告会话和广告 provider 适配层 |
| 广告曝光/完成 | 当前没有 APP 事件接口 | 需要新增幂等事件和奖励结算 |
| 用户金币余额 | 管理端可读会员字段 | 需要增加用户自助只读接口 |
| 用户广告历史 | 管理端可按 `user_id` 筛选 | 需要服务端从 token 固定用户范围 |

## 9. 实施顺序

1. 增加用户认证模型或明确复用 `Member` 的密码字段，并增加用户 JWT 的 `sub/type/aud` 声明。
2. 增加用户注册、登录、refresh、退出和当前用户接口。
3. 增加用户与主体/游戏/设备绑定校验。
4. 建立广告会话、广告事件、provider 回调和金币流水幂等表。
5. 实现广告配置、请求、曝光、完成、失败和历史接口。
6. 增加重复事件、越权用户、停用账号、设备切换、频控和 provider 异常测试。
7. 将 `/api/app/v1/openapi.json` 发布给 APP 开发，不把管理端 OpenAPI 当作用户 APP 契约。

## 10. APP 联调验收清单

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
