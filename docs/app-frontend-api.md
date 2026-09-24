# APP 前端 API 接口文档

本文档面向管理端 APP/前端开发和联调。接口契约以运行时 FastAPI 应用和 `/openapi.json` 为准，代码入口为 `backend/app/main.py`，实际实现位于 `backend/app/main_from_txt.py`。

当前运行时规模：**76 条路径、90 个 HTTP 操作**。本文档覆盖登录、首页、主体、游戏、会员、游戏用户数据、广告、提现、补贴、风控和教程接口。

## 1. 环境与地址

推荐使用仓库内的 Node 同源代理：

```text
前端：http://localhost:3000
API：由 Node 代理到 http://127.0.0.1:8000
Swagger：http://127.0.0.1:8000/docs
OpenAPI：http://127.0.0.1:8000/openapi.json
```

启动命令：

```powershell
python backend/run.py
npm run dev
```

直接部署 FastAPI 时：

- 认证接口前缀：`/api/auth`；
- 业务接口前缀：`/api/v1`；
- 静态资源和健康检查不需要登录；
- 其他认证和业务接口都需要 Bearer token；
- 后端没有配置 CORS，独立 Vite/React 开发服务器必须使用反向代理。

## 2. 统一调用约定

### 2.1 请求头

JSON 请求：

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

原始图片上传：

```http
Authorization: Bearer <access_token>
Content-Type: image/png
```

广告 CSV 导入：

```http
Authorization: Bearer <access_token>
Content-Type: text/csv
X-File-Name: ads.csv
```

图片和 CSV 都发送原始二进制 body，不使用 JSON 或 `multipart/form-data`。

### 2.2 前端请求封装

```js
async function api(path, options = {}, prefix = '/api/v1') {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof Blob)) headers['Content-Type'] = 'application/json';
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(prefix + path, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}
```

登录接口使用 `prefix='/api/auth'`；业务接口使用默认的 `prefix='/api/v1'`。

### 2.3 分页、排序与时间

普通列表响应统一为：

```json
{
  "total": 1,
  "items": [],
  "limit": 20,
  "offset": 0
}
```

- `limit` 通常为 `1..200`，默认 `20`；教程默认 `10`；广告导出默认 `5000`。
- `offset` 从 `0` 开始。
- `sort` 和 `order` 只能使用对应接口声明的枚举值；非法值返回 `422`。
- 相同排序值会使用 `id` 作为稳定次序。
- ISO 8601 时间带时区时转换为 UTC；无时区时间按 UTC 解释。
- 会员页面的 `create_time` 使用北京时间格式：`YYYY-MM-DD` 或 `YYYY-MM-DD HH:mm:ss - YYYY-MM-DD HH:mm:ss`。
- 时间范围开始值大于结束值时返回 `422`。

### 2.4 状态和空数据

- 通用启用状态：`0=禁用`，`1=启用`。
- 审核状态：`0=待审核`，`1=通过`，`2=内部驳回`。
- 提现和补贴响应中的 `target_status` 会把内部 `2` 映射为对外状态 `4`。
- 没有数据时使用 `items: []` 和 `total: 0`，不能当成请求失败。
- 部分汇总字段可能为 `null`，表示数据源不可用，前端不要自动转成 `0`。

## 3. 认证、个人资料与资源

| 方法 | 路径 | 请求/响应 | 前端用途 |
|---|---|---|---|
| POST | `/api/auth/login` | `{username,password}`；返回 `access_token, token_type, expires_in, user` | 登录 |
| GET | `/api/auth/me` | 返回管理员公开资料 | 启动时恢复会话、资料页 |
| PATCH | `/api/auth/me` | `{display_name,password?,avatar?}`；空密码表示不修改 | 保存个人资料 |
| POST | `/api/auth/avatar` | 原始图片 body；成功 `201`，返回 `{url}` | 上传管理员头像 |
| GET | `/api/auth/operations` | `q,limit,offset,sort=id\|created_at,order` | 操作日志 |
| POST | `/api/auth/change-password` | `{current_password,new_password}`；成功 `204` | 修改密码 |
| GET | `/api/health` | `{status:"ok"}` | 健康检查 |
| GET | `/api/member-images/{filename}` | 读取规范化 PNG | 图片展示 |

头像要求：最大 2 MB，支持 PNG/JPEG/WebP/GIF，服务端统一保存为 PNG。头像 URL 必须来自上传接口或默认 `/assets/img/avatar.png`。

登录成功示例：

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 28800,
  "user": {
    "id": 1,
    "username": "admin",
    "display_name": "管理员",
    "role": "superadmin",
    "status": 1
  }
}
```

## 4. 首页、筛选项与主体分析

| 方法 | 路径 | 主要参数/响应 |
|---|---|---|
| GET | `/api/v1/dashboard/summary` | 返回今日新增、登录、主体、游戏、会员、待审核提现/补贴等指标 |
| GET | `/api/v1/dashboard/registrations` | `days=1..31`；返回 `{days,items:[{date,count}]}` |
| GET | `/api/v1/dashboard/activity` | 返回首页活动摘要 |
| GET | `/api/v1/member-filter-options/{kind}` | `kind=games\|agents`；支持 `q,agent_id,id,limit,offset` |
| GET | `/api/v1/agents/{agent_id}/dashboard` | 返回主体仪表盘数据 |
| GET | `/api/v1/agents/{agent_id}/analysis` | 支持金币、成功率、APP 数量、时间、分页和排序筛选；返回 `items,total,echart_data,can_configure` |
| GET | `/api/v1/agents/{agent_id}/analysis-settings` | 返回 `coin/success/apps` 区间配置 |
| PATCH | `/api/v1/agents/{agent_id}/analysis-settings` | `{coin:[],success:[],apps:[]}`；每组最多 50 条，不允许倒序或重叠 |

## 5. 主体、游戏和会员管理

### 5.1 主体

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/agents` | 支持 `q,name,parent_id,status,game_ad_status,ht_status,is_gx,created_from/to,updated_from/to,sort,order,limit,offset`；额外返回 `permissions` 和 `summary` |
| POST | `/api/v1/agents` | 请求模型 `AgentCreate`；成功 `201` |
| GET | `/api/v1/agents/{agent_id}` | 主体详情 |
| PATCH | `/api/v1/agents/{agent_id}` | 请求模型 `AgentUpdate`；只提交需要修改的字段 |
| DELETE | `/api/v1/agents/{agent_id}` | 删除主体；存在关联数据时可能返回 `409` |
| POST | `/api/v1/agents/batch-status` | `{ids:[int],status:0\|1}`；批量请求原子校验 |
| GET | `/api/v1/agents/{agent_id}/oss` | 读取 OSS 配置 |
| PATCH | `/api/v1/agents/{agent_id}/oss` | `{ossKey,ossKeySecret,endPoint,bucket}` |

### 5.2 游戏

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/games` | 支持 `q,game_key,name,agent_id,status,ad_status,lucky_enable,is_mobile,is_landscape,game_type,game_ad_status,created_from/to,sort,order,limit,offset`；额外返回 `summary` |
| POST | `/api/v1/games` | 请求模型 `GameCreate`；成功 `201` |
| GET | `/api/v1/games/{game_id}` | 游戏详情 |
| PATCH | `/api/v1/games/{game_id}` | 请求模型 `GameUpdate` |
| DELETE | `/api/v1/games/{game_id}` | 删除游戏；存在关联数据时可能返回 `409` |
| POST | `/api/v1/games/{game_id}/members/batch-status` | `{ids:[int],status:0\|1}`；限制在指定游戏内 |

### 5.3 会员

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/members` | 支持 `id,username,name,parent_id,agent_id,agent_name,game_id,game_name,status,is_white,exchange_enable,vip,ip,create_time,created_from/to,sort,order,limit,offset` |
| POST | `/api/v1/members` | 请求模型 `MemberCreate`；成功 `201` |
| GET | `/api/v1/members/{member_id}` | 会员详情 |
| PATCH | `/api/v1/members/{member_id}` | 请求模型 `MemberUpdate`；只提交实际变化字段；风险角色只能修改 `is_white` |
| DELETE | `/api/v1/members/{member_id}` | 存在流水、设备、登录或抽奖记录时返回 `409` |
| POST | `/api/v1/members/batch-status` | `{ids:[int],status:0\|1}`，可选 `agent_id` 查询参数 |
| GET | `/api/v1/members/{member_id}/app-usage` | `game_id?,limit,offset`；返回会员 APP 使用统计 |
| POST | `/api/v1/members/{member_id}/clear-coins` | `{reason?}`；清空金币 |
| PATCH | `/api/v1/members/{member_id}/device-ban` | `{target:"device"\|"imei",banned,expected_identifier}` |
| POST | `/api/v1/member-images` | 原始图片 body；成功 `201`，返回 `{url}` |
| GET | `/api/v1/member-addresses` | 必填 `user_id`；支持游戏、收款资料、时间筛选 |
| PATCH | `/api/v1/member-addresses/{user_id}` | `{receive_address,receive_name?,receive_tel?}` |

会员 PATCH 约定：未提交字段保持原值；允许清空的文本字段使用空字符串；模型拒绝 `null` 的字段不要发送 `null`；密码只发送明文输入，服务端持久化哈希。

## 6. 游戏用户数据

| 方法 | 路径 | 主要筛选 |
|---|---|---|
| GET | `/api/v1/lottery-records` | `user_id,game_id,ip,adn_name,network_status,is_white,status,created_from,to,sort,order,limit,offset` |
| GET | `/api/v1/games/{game_id}/lottery-records` | 同上，强制指定游戏范围 |
| GET | `/api/v1/member-daily-income` | `user_id,game_id,date_from,date_to,sort,order,limit,offset` |
| GET | `/api/v1/games/{game_id}/daily-activity` | `date_from,date_to,sort,order,limit,offset` |
| GET | `/api/v1/games/{game_id}/statistics` | 返回 `metrics,income,activity,registrations,regions,mapdata,metric_series,registration_series` |
| GET | `/api/v1/login-logs` | `user_id,filter_user_id,game_id,game_name,username,ip,created_from,to,sort,order,limit,offset` |
| GET | `/api/v1/games/{game_id}/login-logs` | 同上，强制指定游戏范围 |
| GET | `/api/v1/coin-logs` | `user_id,game_id,agent_id,type,remark,created_from,to,sort,order,limit,offset` |
| GET | `/api/v1/risk/history` | `user_id,member_id,username,game_id,agent_id,tagcode,tags,ip,risk_level,action,created_from,to,sort,order,limit,offset` |
| GET | `/api/v1/risk/whitelist` | `username,name,parent_id,game_id,agent_id,game_name,agent_name,status,created_from,to,sort,order,limit,offset` |
| GET | `/api/v1/risk/devices` | `q,limit,offset`；当前数据源不可用时返回 `503` |

## 7. 广告

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/ads` | 支持主体、游戏、会员、金币、广告类型、状态、观看时间、分页和排序筛选 |
| GET | `/api/v1/ads/statistics` | 同广告筛选；`group_by=day\|ad_group\|game\|agent`；返回 `summary/items` |
| GET | `/api/v1/ads/export` | 同广告筛选；返回 CSV 文件流，不调用 `response.json()` |
| POST | `/api/v1/ads/import` | 原始 CSV body，必须带 `X-File-Name`；支持 UTF-8、UTF-8 BOM、GBK/GB18030 |
| GET | `/api/v1/ads/imports` | `q,limit,offset`；导入批次列表 |
| GET | `/api/v1/ads/imports/{batch_id}/errors` | `q,limit,offset`；指定批次错误行 |
| GET | `/api/v1/ads/alerts` | `q,alert_type,severity,source_type,ad_group,watched_from,to,limit,offset` |

导入响应示例：

```json
{
  "batch_id": 1,
  "total": 2,
  "accepted": 1,
  "rejected": 1,
  "errors": [{"row": 3, "errors": ["request_id 已存在"]}]
}
```

## 8. 提现、补贴与黑名单

### 8.1 提现

| 方法 | 路径 | 请求体/说明 |
|---|---|---|
| GET | `/api/v1/withdrawals` | 收款资料、会员、主体、游戏、状态、计划状态、时间、分页排序筛选；返回 `permissions` 和 `summary` |
| GET | `/api/v1/withdrawals/{withdrawal_id}` | 提现详情 |
| PATCH | `/api/v1/withdrawals/{withdrawal_id}` | 请求模型 `WithdrawalUpdate` |
| POST | `/api/v1/withdrawals/{withdrawal_id}/approve` | `{}`；通过审核 |
| POST | `/api/v1/withdrawals/{withdrawal_id}/reject` | `{reason}`；有理由驳回 |
| POST | `/api/v1/withdrawals/{withdrawal_id}/refuse` | `{}`；无理由拒绝 |
| POST | `/api/v1/withdrawals/{withdrawal_id}/transfer` | `{}`；单条转账 |
| POST | `/api/v1/withdrawals/{withdrawal_id}/blacklist` | `{receive_name,receive_tel}`；加入黑名单 |
| POST | `/api/v1/withdrawals/batch-approve` | `{ids,reason?}` |
| POST | `/api/v1/withdrawals/batch-reject` | `{ids,reason?}`；有理由拒绝时 `reason` 必填 |
| POST | `/api/v1/withdrawals/batch-refuse` | `{ids,reason?}`；无理由拒绝 |
| POST | `/api/v1/withdrawals/batch-transfer` | `{ids,reason?}`；未配置支付 provider 时返回 `503` |
| POST | `/api/v1/withdrawals/batch-transfer-scheduled` | `{ids,reason?}`；未配置支付 provider 时返回 `503` |

### 8.2 补贴

| 方法 | 路径 | 请求体/说明 |
|---|---|---|
| GET | `/api/v1/subsidies` | 会员、收款资料、状态、时间、分页排序筛选 |
| PATCH | `/api/v1/subsidies/{subsidy_id}` | 请求模型 `SubsidyUpdate` |
| DELETE | `/api/v1/subsidies/{subsidy_id}` | 删除单条补贴 |
| POST | `/api/v1/subsidies/{subsidy_id}/approve` | `{message?}`；通过 |
| POST | `/api/v1/subsidies/{subsidy_id}/reject` | `{message}`；`message` 不能为空 |
| POST | `/api/v1/subsidies/batch-delete` | `{ids}`；批量删除，原子校验 |
| POST | `/api/v1/subsidies/batch-approve` | `{ids,message?}` |
| POST | `/api/v1/subsidies/batch-reject` | `{ids,message}`；有理由驳回 |
| POST | `/api/v1/subsidies/batch-refuse` | `{ids,message?}`；前端无理由拒绝使用此接口 |

### 8.3 提现黑名单

| 方法 | 路径 | 请求体/说明 |
|---|---|---|
| GET | `/api/v1/withdrawal-blacklist` | 收款人、电话、状态、时间、分页排序筛选 |
| PATCH | `/api/v1/withdrawal-blacklist/{entry_id}` | `{status:0\|1}` |

## 9. 教程

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/tutorials` | 目录分页；`limit,offset,sort=id\|created_at\|updated_at,order,created_from/to,updated_from/to`；不含正文 |
| GET | `/api/v1/tutorials/{tutorial_id}` | 返回目录字段加 `content`；未知 ID 返回 `404` |

教程读取 `public/target-book.json`。源文件缺失或损坏返回 `503`，合法空目录返回空列表。当前没有教程写入或自动同步接口。

## 10. 通用详情接口

```http
GET /api/v1/{resource}/{item_id}
```

`resource` 支持：`agents`、`games`、`members`、`ads`、`withdrawals`、`subsidies`、`coin-logs`、`risk-history`。主体、游戏、会员、提现、补贴有更具体的详情路由，联调时优先使用具体路由。

## 11. 权限矩阵

`superadmin` 跳过角色限制。列表响应中的 `permissions` 仅用于前端显示按钮，服务端权限判断仍然有效。

| 能力 | superadmin | operator | reviewer | risk |
|---|---:|---:|---:|---:|
| 主体/游戏/会员 CRUD | 是 | 是 | 否 | 否 |
| 主体批量状态、OSS、分析配置 | 是 | 是 | 否 | 否 |
| 会员白名单 PATCH | 是 | 是 | 否 | 仅 `is_white` |
| 会员设备封禁 | 是 | 是 | 否 | 是 |
| 清空会员金币 | 是 | 是 | 否 | 否 |
| 提现审核、拒绝、转账 | 是 | 否 | 是 | 否 |
| 提现黑名单 | 是 | 否 | 是 | 是 |
| 补贴审核和批量操作 | 是 | 否 | 是 | 否 |
| 广告 CSV 导入 | 是 | 是 | 否 | 否 |
| 会员图片上传 | 是 | 是 | 否 | 否 |

## 12. 请求模型字段速查

字段类型、默认值和枚举以 `/openapi.json` 为最终准；下表列出前端最常用的请求字段。带 `*` 的字段为必填。

| 模型 | 字段 |
|---|---|
| `LoginRequest` | `username*`, `password*` |
| `PasswordChangeRequest` | `current_password*`, `new_password*` |
| `ProfileUpdate` | `display_name*`, `password?`, `avatar?` |
| `AgentCreate` | `name*`, `parent_id?`, `user_name?`, `avatar?`, `password?`, `user_id?`, `role_id?`, `security_key?`, `status?`, `game_ad_status?`, `ht_status?`, `is_gx?` |
| `AgentUpdate` | `parent_id?`, `name?`, `user_name?`, `avatar?`, `password?`, `user_id?`, `role_id?`, `security_key?`, `status?`, `game_ad_status?`, `ht_status?`, `is_gx?` |
| `GameCreate` | `name*`, `agent_id?`, `game_icon?`, `game_key?`, `game_url?`, `game_type?`, `status?`, `ad_status?`, `lucky_enable?`, `is_landscape?`, `is_game?`, `is_mobile?`, `is_imei?`, `raffle_num?`, `star_countdown?`, `over_countdown?`, `star_coin?`, `over_coin?`, `coin_get?`, `exchange_num?`, `commission_status?`, `commission_source?`, `commission_rate?`, `tixian_price?`, `tixian_coin?`, `tixian_wx?`, `wx_appid?`, `wx_secert?`, `other_url?`, `settings_json?` |
| `GameUpdate` | `GameCreate` 中除 `name` 外的字段均可选，`name` 也可选 |
| `MemberCreate` | `username*`，以及密码、主体/游戏/上级、收款资料、设备、金币、状态、白名单、抽奖和比例字段 |
| `MemberUpdate` | `MemberCreate` 字段均可选；只提交实际变化字段 |
| `WithdrawalUpdate` | `status?`, `plan_status?`, `sub_msg?`, `reason?`, `good_name?`, `device_manufacturer?`, `delivery_name?`, `delivery_no?`, `remark?`, `receive_name?`, `receive_tel?`, `receive_address?`, `exchange_value?`, `exchange_type?` |
| `WithdrawalAction` | `reason?` |
| `WithdrawalBatch` | `ids*`, `reason?` |
| `SubsidyUpdate` | `status?`, `tx_price?`, `price?`, `pics?`, `receive_name?`, `receive_tel?`, `sub_msg?` |
| `SubsidyAction` | `message`；拒绝接口要求非空 |
| `SubsidyBatch` | `ids*`, `message?` |
| `AgentOssConfig` | `ossKey*`, `ossKeySecret*`, `endPoint*`, `bucket*` |
| `AnalysisBuckets` | `coin*`, `success*`, `apps*` |
| `MemberDeviceBan` | `target*`, `banned*`, `expected_identifier*` |
| `MemberAddressUpdate` | `receive_address*`, `receive_name?`, `receive_tel?` |

创建/更新模型的完整字段类型和枚举请直接查看 Swagger 的 `Schemas` 区域，不要从页面输入框推断类型。

## 13. 错误处理

| 状态码 | 含义 | 前端处理 |
|---|---|---|
| 401 | token 缺失、无效、过期或账号停用 | 清除本地 token，跳转登录页 |
| 403 | 当前角色没有操作权限 | 隐藏按钮或提示权限不足，不自动重试 |
| 404 | 资源或关联对象不存在 | 刷新列表并提示资源不存在 |
| 409 | 状态冲突、数据已变化或存在关联数据 | 保留用户输入，提示刷新后重试 |
| 413 | 图片超过 2 MB | 提示压缩或更换图片 |
| 422 | 参数格式、范围或业务校验失败 | 展示 `detail`；字段错误时读取 FastAPI 错误数组 |
| 503 | 数据源或支付 provider 暂不可用 | 显示不可用/稍后重试，不能提示成功 |

业务错误通常为：

```json
{"detail":"资源不存在"}
```

参数错误通常为：

```json
{
  "detail": [
    {"type":"missing","loc":["body","username"],"msg":"Field required"}
  ]
}
```

## 14. 未闭环接口和前端限制

1. `GET /api/v1/risk/devices` 当前稳定返回 `503`，设备风控数据源和入选规则尚未确认。
2. 提现转账接口在未配置真实支付 provider 时返回 `503`，前端不得显示转账成功。
3. 广告统计、导入批次、导入错误和告警接口已注册，但当前广告页面没有完整工作流。
4. `PATCH /api/v1/member-addresses/{user_id}` 和清空会员金币接口已有后端能力，但当前主页面没有独立入口。
5. OpenAPI 当前使用通用详情路由 `/api/v1/{resource}/{item_id}`；文档中的资源具体详情路径用于前端语义说明，自动生成客户端应以 `/openapi.json` 为准。

## 15. 联调验收清单

- 登录、token 持久化、401 自动退出。
- 所有列表正确处理 `total/items/limit/offset`、空数据、分页边界和排序。
- PATCH 只提交变化字段，`null` 不作为清空值发送。
- 批量接口失败时不刷新为部分成功状态。
- 422 同时兼容字符串 `detail` 和错误数组 `detail`。
- CSV/图片上传使用正确的二进制 body 和 `Content-Type`。
- 导出接口使用 `blob()`，不能调用 `response.json()`。
- 支付 provider 未配置时显示失败状态。
- 设备风控 503 显示不可用态，不显示为空列表。

生成依据：运行时 `app.openapi()`、`public/*.js` 实际调用和后端测试。重新生成或核对接口时执行：

```powershell
python -c "from backend.app.main import app; print(len(app.openapi()['paths']))"
node scripts/check-js.cjs
python -m unittest discover -s backend/tests -q
```
