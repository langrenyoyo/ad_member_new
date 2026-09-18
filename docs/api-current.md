# 当前 API 参考

本文档以运行时应用 `backend/app/main_from_txt.py` 的 FastAPI OpenAPI 为准。启动后可通过 `/docs` 查看交互式 Swagger，通过 `/openapi.json` 获取机器可读契约。

## 基本约定

- 管理接口前缀：`/api/v1`
- 认证接口前缀：`/api/auth`
- 请求认证：`Authorization: Bearer <access_token>`
- 未认证：`401`；无角色权限：`403`；参数校验：`422`；资源不存在：`404`；状态冲突：`409`。
- 普通列表通常返回 `{total, items, limit, offset}`，部分页面额外返回 `summary`、`permissions` 或图表数据。
- 时间参数使用 ISO 8601。带时区的输入会转换为 UTC；无时区输入按 UTC 解释，页面日期筛选会先按 Asia/Shanghai 转换。

## 认证与资料

| 方法 | 路径 | 请求/响应 | 前端状态 |
|---|---|---|---|
| POST | `/api/auth/login` | JSON `{username,password}`；返回 `access_token, token_type, expires_in, user` | 已闭环 |
| GET | `/api/auth/me` | 返回管理员公开资料 | 已闭环 |
| PATCH | `/api/auth/me` | JSON `{display_name,password?,avatar?}`；空密码不修改 | 已闭环 |
| POST | `/api/auth/avatar` | 原始图片二进制；返回 `{url}`；最大 2 MB | 已闭环 |
| GET | `/api/auth/operations` | `q,limit,offset,sort=id\|created_at,order` | 已闭环 |
| POST | `/api/auth/change-password` | JSON `{current_password,new_password}`；成功 `204` | 后端接口，当前前端未调用 |
| GET | `/api/health` | 返回 `{status:"ok"}` | 运行检查接口 |
| GET | `/api/member-images/{filename}` | 读取规范化 PNG | 前端图片资源 |

头像上传支持 PNG、JPEG、WebP、GIF，服务端保存为 48 位十六进制文件名的 PNG。成员头像上传另有同一处理器的 `/api/v1/member-images`。

## 仪表盘、主体与游戏

| 方法 | 路径 | 关键参数/请求体 | 前端状态 |
|---|---|---|---|
| GET | `/api/v1/dashboard/summary` | 无 | 已闭环 |
| GET | `/api/v1/dashboard/registrations` | `days` | 已闭环 |
| GET | `/api/v1/dashboard/activity` | 无 | 后端接口，当前首页未调用 |
| GET | `/api/v1/member-filter-options/{kind}` | `kind=games\|agents`；`q,agent_id,id,limit,offset` | 已闭环 |
| GET/POST | `/api/v1/agents` | 列表筛选；创建使用 `AgentCreate` | 已闭环 |
| GET/PATCH/DELETE | `/api/v1/agents/{agent_id}` | 详情、局部更新、删除 | 已闭环 |
| POST | `/api/v1/agents/batch-status` | `{ids:[int],status:0\|1}` | 已闭环 |
| GET/PATCH | `/api/v1/agents/{agent_id}/oss` | `{ossKey,ossKeySecret,endPoint,bucket}` | 已闭环 |
| GET/PATCH | `/api/v1/agents/{agent_id}/analysis-settings` | `coin/success/apps` 区间数组 | 已闭环 |
| GET | `/api/v1/agents/{agent_id}/analysis` | 收益、成功率、APP 数量、时间范围、分页、排序 | 已闭环 |
| GET | `/api/v1/agents/{agent_id}/dashboard` | 无 | 已闭环 |
| GET/POST | `/api/v1/games` | 列表筛选；创建使用 `GameCreate` | 已闭环 |
| GET/PATCH/DELETE | `/api/v1/games/{game_id}` | 详情、局部更新、删除 | 已闭环 |
| POST | `/api/v1/games/{game_id}/members/batch-status` | `{ids:[int],status:0\|1}` | 已闭环 |

主体列表会额外返回 `permissions` 和 `summary`。主体、游戏删除会检查关联数据并可能返回 `409`。

## 会员与游戏数据

| 方法 | 路径 | 关键参数/请求体 | 前端状态 |
|---|---|---|---|
| POST | `/api/v1/member-images` | 原始图片二进制；返回 `{url}` | 已闭环 |
| GET | `/api/v1/members` | `id,username,name,parent_id,game_name,agent_id,game_id,status,is_white,vip` 等筛选；分页排序 | 已闭环 |
| POST | `/api/v1/members` | `MemberCreate` | 受权限控制；列表按权限隐藏入口 |
| GET/PATCH/DELETE | `/api/v1/members/{member_id}` | 详情、局部更新、删除；密码只接收明文输入并持久化哈希 | 已闭环 |
| POST | `/api/v1/members/batch-status` | `{ids:[int],status:0\|1}`，可带 `agent_id` | 已闭环 |
| POST | `/api/v1/members/{member_id}/clear-coins` | `{reason?}` | 后端接口，当前前端未调用 |
| PATCH | `/api/v1/members/{member_id}/device-ban` | `{target:"device"\|"imei",banned,expected_identifier}` | 已闭环于会员行为弹窗 |
| GET | `/api/v1/members/{member_id}/app-usage` | `game_id?,limit,offset` | 已闭环 |
| GET | `/api/v1/member-addresses` | 必填 `user_id`；可按游戏、收款资料、时间筛选 | 已闭环读取 |
| PATCH | `/api/v1/member-addresses/{user_id}` | `{receive_address,receive_name?,receive_tel?}` | 后端接口，当前前端无保存入口 |
| GET | `/api/v1/lottery-records` | 会员、游戏、网络、白名单、状态、时间等筛选 | 已闭环 |
| GET | `/api/v1/games/{game_id}/lottery-records` | 同上，强制游戏范围 | 已闭环 |
| GET | `/api/v1/member-daily-income` | 会员/游戏、日期、排序、分页 | 已闭环 |
| GET | `/api/v1/games/{game_id}/daily-activity` | 日期、排序、分页 | 已闭环 |
| GET | `/api/v1/games/{game_id}/statistics` | 无；返回统计卡片、图表序列和地区数据 | 已闭环 |
| GET | `/api/v1/login-logs` | 会员、游戏、IP、时间、分页排序 | 已闭环 |
| GET | `/api/v1/games/{game_id}/login-logs` | 同上，强制游戏范围 | 已闭环 |

`MemberUpdate` 为 PATCH 语义，只提交实际变更字段；空字符串用于清空允许清空的文本字段，`null` 会被拒绝。删除会员存在关联流水、设备、登录或抽奖记录时返回 `409`。

## 广告

| 方法 | 路径 | 关键参数/请求体 | 前端状态 |
|---|---|---|---|
| GET | `/api/v1/ads` | 搜索、主体/游戏/会员、金币、广告类型、状态、观看时间、分页排序 | 已闭环 |
| GET | `/api/v1/ads/statistics` | 同广告筛选；`group_by=day\|ad_group\|game\|agent` | 后端接口，当前广告页未调用 |
| GET | `/api/v1/ads/export` | 同广告筛选；返回 CSV 文件 | 已闭环下载 |
| POST | `/api/v1/ads/import` | 原始 CSV body，`X-File-Name` 文件名 | 后端接口，当前前端未提供导入入口 |
| GET | `/api/v1/ads/imports` | `q,limit,offset` | 后端接口，当前前端未调用 |
| GET | `/api/v1/ads/imports/{batch_id}/errors` | `q,limit,offset` | 后端接口，当前前端未调用 |
| GET | `/api/v1/ads/alerts` | 告警类型、级别、来源、广告组、时间、分页 | 后端接口，当前前端未调用 |

广告导入支持 UTF-8、UTF-8 BOM 和 GBK。导入、批次和告警虽然服务端已注册，但没有前端工作流，因此目前不算端到端闭环。

## 提现、补贴与黑名单

| 方法 | 路径 | 关键参数/请求体 | 前端状态 |
|---|---|---|---|
| GET | `/api/v1/withdrawals` | 收款资料、会员/主体/游戏、状态、时间、分页排序 | 已闭环 |
| GET/PATCH | `/api/v1/withdrawals/{withdrawal_id}` | 详情；局部编辑使用 `WithdrawalUpdate` | 已闭环 |
| POST | `/api/v1/withdrawals/{withdrawal_id}/approve` | `{}` | 已闭环 |
| POST | `/api/v1/withdrawals/{withdrawal_id}/reject` | `{reason}` | 已闭环 |
| POST | `/api/v1/withdrawals/{withdrawal_id}/refuse` | `{}` | 已闭环 |
| POST | `/api/v1/withdrawals/{withdrawal_id}/transfer` | `{}` | 后端接口，当前前端使用批量转账 |
| POST | `/api/v1/withdrawals/batch-approve` | `{ids,reason?}` | 后端接口，当前页面未调用 |
| POST | `/api/v1/withdrawals/batch-reject` | `{ids,reason?}` | 后端接口，当前页面未调用 |
| POST | `/api/v1/withdrawals/batch-refuse` | `{ids,reason?}` | 已闭环 |
| POST | `/api/v1/withdrawals/batch-transfer` | `{ids,reason?}` | 已闭环；支付未配置时返回 `503` |
| POST | `/api/v1/withdrawals/batch-transfer-scheduled` | `{ids,reason?}` | 后端接口，当前前端未调用 |
| GET | `/api/v1/withdrawal-blacklist` | 收款人、电话、状态、时间、分页排序 | 已闭环 |
| PATCH | `/api/v1/withdrawal-blacklist/{entry_id}` | `{status:0\|1}` | 已闭环 |
| POST | `/api/v1/withdrawals/{withdrawal_id}/blacklist` | `{receive_name,receive_tel}` | 已闭环 |
| GET | `/api/v1/subsidies` | 会员、收款资料、状态、时间、分页排序 | 已闭环 |
| GET | `/api/v1/subsidies/{subsidy_id}` | 通用资源详情 | 已闭环 |
| PATCH/DELETE | `/api/v1/subsidies/{subsidy_id}` | `SubsidyUpdate`；删除无 body | 已闭环 |
| POST | `/api/v1/subsidies/{subsidy_id}/approve` | `{}` | 已闭环 |
| POST | `/api/v1/subsidies/{subsidy_id}/reject` | `{message}` | 已闭环 |
| POST | `/api/v1/subsidies/batch-delete` | `{ids}` | 已闭环 |
| POST | `/api/v1/subsidies/batch-approve` | `{ids,message?}` | 已闭环 |
| POST | `/api/v1/subsidies/batch-reject` | `{ids,message}` | 后端接口，当前前端使用无理由 `batch-refuse` |
| POST | `/api/v1/subsidies/batch-refuse` | `{ids,message?}` | 已闭环 |
| GET | `/api/v1/coin-logs` | 会员、主体、游戏、类型、备注、时间、分页排序 | 已闭环 |

提现转账调用支付 provider。当前未配置真实 provider 时服务端必须返回 `503`，不应向前端报告支付成功；这是业务未闭环的明确状态。

## 风控与教程

| 方法 | 路径 | 关键参数/响应 | 前端状态 |
|---|---|---|---|
| GET | `/api/v1/risk/history` | 标签、会员、IP、时间、分页排序 | 已闭环 |
| GET | `/api/v1/risk/whitelist` | 会员、主体、游戏、状态、时间、分页排序 | 已闭环 |
| GET | `/api/v1/risk/devices` | 设备风控列表 | 前端已调用，但当前数据源缺失并返回 `503` |
| GET | `/api/v1/tutorials` | 目录分页、排序、创建/更新时间范围；不含正文 | 已闭环 |
| GET | `/api/v1/tutorials/{tutorial_id}` | 返回目录字段加 `content` | 已闭环，原始图片资源仍需补齐 |

## 通用详情路由

`GET /api/v1/{resource}/{item_id}` 是兼容详情入口，支持 `agents`、`games`、`members`、`ads`、`withdrawals`、`subsidies`、`coin-logs`、`risk-history`。其中成员、主体、游戏、提现有更具体的详情路由；联调时优先使用具体路由。

## 关键模型

完整字段约束、枚举和响应 schema 以运行时 `/openapi.json` 为准。代码中的主要请求模型为：`LoginRequest`、`ProfileUpdate`、`AgentCreate/Update`、`GameCreate/Update`、`MemberCreate/Update`、`WithdrawalUpdate/Action/Batch`、`SubsidyUpdate/Action/Batch`、`AgentOssConfig`、`AnalysisBuckets`、`MemberDeviceBan`、`MemberAddressUpdate`。
