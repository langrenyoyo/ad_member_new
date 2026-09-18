# 接口文档

> 本文件保留为历史接口记录。当前联调请以 [当前 API 参考](./api-current.md) 和 [前后端 API 闭环分析](./api-closure-analysis.md) 为准；运行时完整契约可从 FastAPI `/openapi.json` 获取。

接口设计以 [https://ad.leadink.cn/](https://ad.leadink.cn/) 后台菜单和页面数据口径为整站对标对象，后端采用自研等价实现。

## 1. 统一约定

- 前缀：`/api/v1`
- 登录接口：`/api/auth/*`
- 鉴权方式：`Authorization: Bearer <token>`
- 列表接口统一返回 `total / items / limit / offset`
- 统计接口返回 `summary / items`

## 2. 认证接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | 登录并返回 token |
| GET | `/api/auth/me` | 获取当前登录用户 |
| PATCH | `/api/auth/me` | 保存当前账号昵称、可选密码和头像；空密码不修改 |
| POST | `/api/auth/avatar` | 已登录账号上传头像原始二进制，返回规范化 PNG 地址；不自动修改资料 |
| GET | `/api/auth/operations` | 当前账号日志；`q`、`limit=1..200`、`offset`、`sort=id/created_at`、`order=asc/desc` |
| POST | `/api/auth/change-password` | 修改密码 |

个人资料返回 `avatar`，默认 `/assets/img/avatar.png`。头像上传最大 2MB、4096px，支持 PNG/JPEG/WebP/GIF；保存资料时只接收默认头像或存在的 `/api/member-images/{48位十六进制}.png`。昵称必填 1–128 字，非空密码至少 10 字；这些限制为本地策略，参考后台实际写入规则尚未核实。详见 [个人资料核验](profile-parity-verification.md)。

## 3. 仪表盘

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/dashboard/summary` | 总览指标 |
| GET | `/api/v1/dashboard/activity` | 最近活动 |

## 4. 广告接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/ads` | 广告列表 |
| GET | `/api/v1/ads/{id}` | 广告详情 |
| GET | `/api/v1/ads/statistics` | 广告统计 |
| GET | `/api/v1/ads/export` | 广告导出 |
| POST | `/api/v1/ads/import` | 广告导入 |
| GET | `/api/v1/ads/imports` | 导入批次 |
| GET | `/api/v1/ads/imports/{batch_id}/errors` | 导入失败明细 |
| GET | `/api/v1/ads/alerts` | 广告告警 |

### 4.1 列表筛选参数
- `q`
- `parent_id`
- `user_id`
- `game_id`
- `agent_id`
- `coin_min`
- `coin_max`
- `ad_platform`
- `ad_type`
- `sub_ad_type`
- `is_fu`
- `fu_type`
- `is_look`
- `ad_group`
- `status`
- `watched_from`
- `watched_to`

### 4.2 统计维度
- `day`
- `ad_group`
- `game`
- `agent`

### 4.3 导入要求
- 上传方式：原始 CSV body
- 文件名：通过 `X-File-Name` 传入
- 编码：UTF-8 / UTF-8 BOM / GBK
- 结果：返回批次编号、成功数、失败数和错误行

## 5. 主体 / 游戏 / 会员

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/agents` | 主体列表 |
| POST | `/api/v1/agents` | 新增主体 |
| GET | `/api/v1/agents/{agent_id}` | 主体详情 |
| PATCH | `/api/v1/agents/{agent_id}` | 编辑主体 |
| DELETE | `/api/v1/agents/{agent_id}` | 删除主体 |
| POST | `/api/v1/agents/batch-status` | operator/superadmin 批量启用或禁用；`ids` 为 1 至 10000 项，`status` 为 0/1，去重并全量校验后原子更新，返回 `updated` |
| GET | `/api/v1/agents/{agent_id}/oss` | operator/superadmin 读取独立 OSS 配置 |
| PATCH | `/api/v1/agents/{agent_id}/oss` | operator/superadmin 保存 `ossKey/ossKeySecret/endPoint/bucket` |
| GET | `/api/v1/agents/{agent_id}/analysis` | 主体抽奖聚合、会员明细与六图；数值四区间、日期、排序、分页；图表为完整过滤结果 |
| GET | `/api/v1/agents/{agent_id}/analysis-settings` | 读取 coin/success/apps 区间数组，不创建记录 |
| PATCH | `/api/v1/agents/{agent_id}/analysis-settings` | operator/superadmin 合并所提交分组；每项 name/minimum/maximum，最多各 50 条，拒绝倒序或重叠 |
| GET | `/api/v1/games` | 游戏列表 |
| POST | `/api/v1/games` | 新增游戏 |
| GET | `/api/v1/games/{game_id}` | 游戏详情 |
| PATCH | `/api/v1/games/{game_id}` | 编辑游戏 |
| DELETE | `/api/v1/games/{game_id}` | 删除游戏 |
| GET | `/api/v1/members` | 会员列表 |
| POST | `/api/v1/members` | 新增会员 |
| GET | `/api/v1/members/{member_id}` | 会员详情 |
| PATCH | `/api/v1/members/{member_id}` | 编辑会员 |
| DELETE | `/api/v1/members/{member_id}` | 删除会员 |

主体列表返回额外 `permissions`，包含 `create/edit/delete/oss/batch_status/dashboard` 布尔能力；前五项仅 operator/superadmin 为真，dashboard 对已登录账号为真。客户端据此显示入口，服务端仍独立鉴权。批量状态缺失任何记录返回 404 并不更新其他记录，非法空列表或状态返回 422；鉴权失败返回 401/403。OSS 不并入主体普通列表或详情。

分析筛选为 `coin_user_total_min/max`、`coin_every_min/max`、`success_percent_min/max`、`app_num_min/max`，支持单边；`created_from/to` 为抽奖时间（UTC 或带时区），范围包含两端。排序 `id/coin_user/coin/freeze_coin/created_at`，`limit=1..200`。响应包含 `agent_name/items/total/echart_data/can_configure`；图表键与参考六图对应，业务口径的证据与缺口见 `docs/agent-analysis-parity-verification.md`。

## 6. 审核与风控

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/withdrawals` | 提现列表 |
| GET | `/api/v1/withdrawals/{withdrawal_id}` | 提现详情 |
| PATCH | `/api/v1/withdrawals/{withdrawal_id}` | 更新提现 |
| POST | `/api/v1/withdrawals/{withdrawal_id}/approve` | 通过提现 |
| POST | `/api/v1/withdrawals/{withdrawal_id}/reject` | 驳回提现 |
| POST | `/api/v1/withdrawals/{withdrawal_id}/transfer` | 提现转账 |
| GET | `/api/v1/subsidies` | 补贴列表 |
| PATCH | `/api/v1/subsidies/{subsidy_id}` | 更新补贴 |
| DELETE | `/api/v1/subsidies/{subsidy_id}` | 删除补贴 |
| POST | `/api/v1/subsidies/batch-delete` | 批量删除补贴 |
| POST | `/api/v1/subsidies/batch-approve` | 批量同意补贴；`ids` 原子校验 |
| POST | `/api/v1/subsidies/batch-reject` | 批量驳回补贴；需要非空 `message`，原子校验 |
| POST | `/api/v1/subsidies/batch-refuse` | 批量无理由拒绝补贴 |
| POST | `/api/v1/subsidies/{subsidy_id}/approve` | 通过补贴 |
| POST | `/api/v1/subsidies/{subsidy_id}/reject` | 驳回补贴 |
| GET | `/api/v1/coin-logs` | 金币流水 |
| GET | `/api/v1/risk/history` | 风控历史 |
| GET | `/api/v1/risk/whitelist` | 白名单 |
| GET | `/api/v1/risk/devices` | 设备风控；真实会员入选来源待确认，当前返回 503，不返回风险日志 |

## 7. 教程

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/tutorials` | 认证目录查询，返回 `id/name/created_at/updated_at`，不含正文 |
| GET | `/api/v1/tutorials/{id}` | 认证读取正文，增加 `content`；未知 ID 返回 404 |

目录参数：`limit=1..200`（默认 10）、`offset`、`sort=id/created_at/updated_at`、`order=asc/desc`、`created_from/created_to/updated_from/updated_to`。默认 Id 倒序，先筛选排序再分页；有时区输入归一为 UTC，无时区输入按 UTC。当前读取 `public/target-book.json`，源文件缺失或损坏返回 503，合法空目录返回空列表。未提供教程写入或自动同步接口。详见 [教程核验](book-parity-verification.md)。

## 8. 返回字段建议

- 列表接口：`total`、`items`、`limit`、`offset`
- 统计接口：`summary`、`type_breakdown`、`source_breakdown`
- 广告记录建议兼容返回：`pre_ecpm`、`ad_network_rit_id`、`create_time`
