# 用户 APP API 实现说明

用户端接口已独立挂载在 `/api/app/v1`，与后台管理员接口 `/api/v1` 使用不同的 JWT 类型。

## 已实现接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/register` | 用户注册并返回 access/refresh token |
| POST | `/auth/login` | 用户登录 |
| POST | `/auth/refresh` | 轮换 refresh token |
| POST | `/auth/logout` | 撤销 refresh token |
| GET/PATCH | `/me` | 查询或更新当前用户资料 |
| POST | `/auth/change-password` | 修改用户密码 |
| GET | `/games` | 查询当前主体可用游戏 |
| GET | `/bootstrap` | APP 启动配置和用户信息 |
| POST | `/ads/request` | 创建广告会话 |
| POST | `/ads/{id}/impression` | 上报广告曝光 |
| POST | `/ads/{id}/complete` | 上报广告完成并结算金币 |
| POST | `/ads/{id}/fail` | 结束失败的广告会话 |
| GET | `/ads/history` | 查询当前用户广告记录 |
| GET | `/wallet` | 查询金币余额 |
| GET | `/wallet/coin-logs` | 查询金币流水 |

请求前缀为 `https://<域名>/api/app/v1`，登录后使用：

```http
Authorization: Bearer <access_token>
X-Device-Id: <安装实例 ID>
```

注册和登录必须提交 `device_id`。广告完成使用 `event_id` 幂等，重复提交会返回第一次结算结果，不会重复增加金币。管理员 token 不可访问 APP 接口，用户 token 也不可访问后台接口。

## 广告结算边界

当前项目使用内部广告会话适配层，广告奖励由服务端根据游戏配置的 `star_coin` 决定，客户端传入的金币、ECPM 和奖励值不会参与结算。生产接入第三方广告平台时，应在 `ads/request`、provider 回调和 `ads/complete` 之间增加真实 provider 签名校验；未配置 provider 时不应把内部会话当作真实广告填充。

完整请求模型和响应字段见 [user-app-api.md](./user-app-api.md)。在线 OpenAPI 地址为 `/docs`，其中包含 `User APP` 标签下的接口。
