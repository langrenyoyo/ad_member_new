# APP 安全防护接口扩展建议

本文档补充 `user-app-api.md` 中尚未定义的设备安全、应用完整性和广告风控接口。当前文档已经定义 `X-Device-Id`、设备状态校验和 `DEVICE_BLOCKED`，但没有定义设备风险上报或 Play Integrity 校验接口。

## 1. 原则

- 客户端检测结果只能作为风控信号，不能单独作为可信证明。
- 广告奖励必须由服务端根据广告会话、广告渠道回调和设备风险决定。
- 客户端不得提交或决定奖励金币、ECPM 或结算状态。
- 所有写入接口使用 `event_id` 或 `idempotency_key` 幂等。
- 设备安装实例使用随机 `device_id`，不使用 IMEI、Android ID 等硬件标识。

## 2. 现有请求头扩展

客户端可以发送：

```http
X-App-Id: ad-member
X-App-Version: 1.0.0
X-Platform: android
X-Device-Id: <install-uuid>
X-Device-Risk: clean
X-Device-Blocked: false
```

`X-Device-Risk` 只表示客户端检测到的信号，例如 `clean`、`emulator,root` 或 `hook`。服务端必须把这些字段当作不可信输入，仅用于记录和风险计算。

## 3. 新增设备证明接口

### 3.1 创建完整性挑战

```http
POST /api/app/v1/security/integrity-challenge
Authorization: Bearer <user_access_token>
```

返回：

```json
{
  "data": {
    "challenge_id": "chal_01J...",
    "nonce": "<base64url-random-nonce>",
    "expires_at": "2026-10-01T03:05:00Z"
  },
  "request_id": "req_01J..."
}
```

`nonce` 必须一次性、短期有效，并绑定用户、设备、包名和版本。服务端必须拒绝过期或重复使用的 challenge。

### 3.2 提交设备证明

```http
POST /api/app/v1/security/device-attestation
Authorization: Bearer <user_access_token>
```

请求：

```json
{
  "challenge_id": "chal_01J...",
  "device_id": "install-uuid",
  "app_id": "ad-member",
  "app_version": "1.0.0",
  "platform": "android",
  "client_risk_flags": ["root", "hook"],
  "integrity_token": "<optional-play-integrity-token>",
  "event_id": "attest-01J..."
}
```

服务端应校验用户和设备绑定，并在服务端调用 Google Play Integrity 校验 `integrity_token`。不得由客户端解析 token 后直接上报“通过”。

返回：

```json
{
  "data": {
    "device_id": "install-uuid",
    "status": "allowed",
    "risk_level": "low",
    "ad_reward_allowed": true,
    "checked_at": "2026-10-01T03:00:00Z",
    "expires_at": "2026-10-01T04:00:00Z"
  },
  "request_id": "req_01J..."
}
```

`status` 建议支持：

- `allowed`：允许业务和广告奖励。
- `review`：允许展示广告，奖励进入审核或异步风控。
- `blocked`：禁止广告奖励。

## 4. 广告接口的服务端风控

现有接口保持不变：

```text
POST /api/app/v1/ads/request
POST /api/app/v1/ads/{ad_session_id}/impression
POST /api/app/v1/ads/{ad_session_id}/complete
POST /api/app/v1/ads/{ad_session_id}/fail
```

`ads/request` 返回会话前必须校验：用户状态、游戏归属、设备绑定、设备状态、广告冷却、频控、客户端风险信号和 Play Integrity 结果（如有）。

风险设备拒绝时：

```http
403 Forbidden
```

```json
{
  "error": {
    "code": "DEVICE_BLOCKED",
    "message": "当前设备暂不支持广告奖励",
    "details": {"ad_reward_allowed": false}
  },
  "request_id": "req_01J..."
}
```

如果允许展示但不奖励，建议正常创建会话并返回：

```json
"reward": {"enabled": false, "coin": 0, "currency": "coin"}
```

## 5. Play Integrity 流程

1. 客户端请求服务端 challenge。
2. 客户端使用 Google Play Integrity SDK 获取 token。
3. 客户端提交 token 和 challenge_id 给 `device-attestation`。
4. 服务端向 Google 解密和校验 token。
5. 服务端检查 package name、nonce、时间、账号和设备完整性结果。
6. 服务端将结果映射为 `allowed`、`review` 或 `blocked`。

客户端不能直接调用 Google 校验接口，也不能仅凭本地模拟器检测给用户发奖励。

## 6. 建议错误码

| HTTP | 错误码 | 含义 |
|---:|---|---|
| 403 | `DEVICE_BLOCKED` | 设备禁止广告奖励 |
| 403 | `APP_INTEGRITY_FAILED` | 包名、签名或完整性校验失败 |
| 422 | `ATTESTATION_INVALID` | 设备证明或 challenge 无效 |
| 409 | `ATTESTATION_REPLAYED` | 证明或事件重复使用 |
| 429 | `DEVICE_RATE_LIMITED` | 设备请求频率过高 |
| 503 | `INTEGRITY_PROVIDER_UNAVAILABLE` | 完整性服务暂不可用 |

## 7. 服务端数据建议

建议新增 `device_security_events`：

```text
id, user_id, device_id, game_id, client_risk_flags,
integrity_result, risk_level, status, created_at, expires_at
```

`integrity_challenges` 至少保存：

```text
id, user_id, device_id, nonce_hash, used_at, expires_at, created_at
```

广告会话建议增加：

```text
risk_level, ad_reward_allowed, integrity_event_id
```

## 8. 实施顺序

1. 先实现 `integrity-challenge` 和 `device-attestation`，只记录风险，不立即拦截正常设备。
2. 在 `ads/request` 接入设备状态、风险等级和频控判断。
3. 接入广告渠道服务端回调，完成服务端奖励校验。
4. 客户端接入 Play Integrity token 流程。
5. 观察误判率后，再对 `blocked` 设备禁止广告奖励。

## 9. 当前项目状态

当前 Android 客户端已经检测模拟器、Root 和常见 Hook 环境，并通过 `X-Device-Risk`、`X-Device-Blocked` 发送检测结果。广告会话、曝光、完成和失败接口也已接入。

桌面的现有 API 文档尚未定义设备证明、Play Integrity challenge 或完整性校验路由。后端新增接口并确认字段后，再按正式协议接入客户端；在此之前，服务端不能仅凭客户端请求头发放奖励。
