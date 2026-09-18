# 前端联调 API 契约

本文档是前端开发和联调入口，内容以当前运行时 `backend/app/main.py`（转发到 `main_from_txt.py`）及 `/openapi.json` 为准。文档只描述当前代码已经提供的行为，不把未接通的支付或设备风控当作成功能力。

## 1. 环境与请求基址

本地推荐使用 Node 静态壳代理，前端和 API 同源：

```text
前端：http://localhost:3000
API：由 Node 代理到 http://127.0.0.1:8000
Swagger：http://127.0.0.1:8000/docs
OpenAPI：http://127.0.0.1:8000/openapi.json
```

启动：

```powershell
python backend/run.py
npm run dev
```

直接部署 FastAPI 时，业务 API 使用 `/api/v1`，认证 API 使用 `/api/auth`。当前后端未配置 CORS；独立 Vite/React 开发服务器必须配置反向代理，不能直接跨域调用 8000 端口。

当前运行时规模：`76` 条路径、`90` 个 HTTP 操作。静态文件和健康检查不需要业务登录，其他认证接口或业务接口需要 Bearer token。

## 2. 统一约定

### 2.1 请求头

JSON 请求：

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

文件上传使用原始二进制，不要使用 JSON 或 `multipart/form-data`：

```http
Authorization: Bearer <access_token>
Content-Type: image/png
```

广告 CSV 导入还应发送：

```http
Content-Type: text/csv
X-File-Name: ads.csv
```

### 2.2 分页、排序与时间

普通列表响应统一为：

```json
{
  "total": 1,
  "items": [],
  "limit": 20,
  "offset": 0
}
```

- `limit` 默认 `20`，通常范围 `1..200`；广告导出最大 `50000`；教程默认 `10`。
- `offset` 默认 `0`，必须大于等于 `0`。
- `sort` 和 `order` 只能使用各接口文档列出的值，非法值返回 `422`。
- 同值排序会以 `id` 作为稳定次序。
- `datetime` 参数使用 ISO 8601。带时区输入转换为 UTC；无时区输入通常按 UTC 解释。
- 页面日期筛选的会员 `create_time` 使用北京时间格式：`YYYY-MM-DD` 或 `YYYY-MM-DD HH:mm:ss - YYYY-MM-DD HH:mm:ss`。
- `date_from/date_to` 类型参数是日期，不带时间和时区。
- 时间范围开始大于结束时返回 `422`。

### 2.3 状态与空值

- 一般启用状态：`0=禁用`，`1=启用`。
- 审核状态：`0=申请中/待审核`，`1=通过`，`2=内部驳回`；提现和补贴响应中的 `target_status` 会把内部 `2` 映射为对外状态 `4`。
- 没有数据时使用 `items: []` 和 `total: 0`，不要把空数组当成请求失败。
- 服务端可能返回 `null` 表示数据源未知，例如提现汇总的 `summary.blacklisted`；前端不得把它转换为 `0`。
- PATCH 只提交需要修改的字段；未提交字段保持原值。允许清空的文本使用空字符串，模型拒绝 `null` 的字段不要发送 `null`。

## 3. 认证

### 3.1 登录

```http
POST /api/auth/login
Content-Type: application/json
```

请求：

```json
{"username":"admin","password":"Admin123!"}
```

成功 `200`：

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 28800,
  "user": {
    "id": 1,
    "username": "admin",
    "mobile": "",
    "avatar": "/assets/img/avatar.png",
    "display_name": "管理员",
    "role": "superadmin",
    "status": 1,
    "last_login_at": "2026-09-18T10:00:00"
  }
}
```

登录失败返回 `401`，错误体见第 4 节。token 过期或管理员被停用也返回 `401`，前端应清除本地 token 并回到登录页。

### 3.2 当前用户与资料

| 方法 | 路径 | 成功响应 |
|---|---|---|
| GET | `/api/auth/me` | 管理员对象 |
| PATCH | `/api/auth/me` | 更新后的管理员对象 |
| GET | `/api/auth/operations?q=&limit=10&offset=0&sort=id&order=desc` | 分页操作日志 |
| POST | `/api/auth/change-password` | `204`，无响应体 |

资料 PATCH 请求：

```json
{"display_name":"新昵称","password":"至少 10 个字符","avatar":"/api/member-images/<48位十六进制>.png"}
```

`display_name` 必填；密码为空字符串表示不改密码。头像必须先通过上传接口获得合法 URL。

## 4. 错误契约

自定义业务错误通常是：

```json
{"detail":"提现记录不存在"}
```

字段校验错误是 FastAPI 标准结构：

```json
{
  "detail": [
    {"type":"missing","loc":["body","username"],"msg":"Field required","input":null}
  ]
}
```

| 状态码 | 含义 | 前端处理 |
|---|---|---|
| 401 | token 缺失、无效、过期或账号停用 | 清除 token，回登录页 |
| 403 | 当前角色没有该操作权限 | 隐藏按钮或提示权限不足，不自动重试 |
| 404 | 资源或关联对象不存在 | 刷新列表或提示资源不存在 |
| 409 | 状态冲突、数据已变化、存在关联数据 | 保留用户输入，提示刷新后重试 |
| 413 | 图片超过 2 MB | 提示压缩或更换图片 |
| 422 | 参数格式、范围、必填项或业务校验失败 | 展示 `detail`，定位到表单字段 |
| 503 | 业务数据源或支付 provider 不可用 | 展示未完成/稍后重试，不能提示成功 |

批量接口具有原子校验语义：只要 ID 缺失、状态不匹配或参数不合法，整批失败，不应按部分成功刷新本地状态。

## 5. 角色权限矩阵

`superadmin` 绕过角色限制。所有已登录角色都可以读取普通列表和详情，但写入能力如下：

| 能力 | superadmin | operator | reviewer | risk |
|---|---:|---:|---:|---:|
| 主体/游戏/会员 CRUD | 是 | 是 | 否 | 否 |
| 主体批量状态、OSS、分析配置 | 是 | 是 | 否 | 否 |
| 会员白名单 PATCH | 是 | 是 | 否 | 是（仅 `is_white`） |
| 会员设备封禁 | 是 | 是 | 否 | 是 |
| 清空会员金币 | 是 | 是 | 否 | 否 |
| 提现审核、拒绝、转账 | 是 | 否 | 是 | 否 |
| 提现黑名单新增/切换 | 是 | 否 | 是 | 是 |
| 补贴审核和批量操作 | 是 | 否 | 是 | 否 |
| 广告 CSV 导入 | 是 | 是 | 否 | 否 |
| 头像/会员图片上传 | 头像：是；会员图：是 | 会员图：是 | 会员图：否 | 会员图：否 |

列表响应中的 `permissions` 是页面按钮显示依据；服务端权限仍是最终判断，不能只依赖前端隐藏按钮。

## 6. 核心资源字段

### 6.1 主体、游戏、会员

主体列表项字段：

```text
id, parent_id, name, user_name, status, game_ad_status, ht_status,
is_gx, created_at, updated_at
```

主体列表另外返回：

```json
{
  "permissions":{"create":true,"edit":true,"delete":true,"oss":true,"batch_status":true,"dashboard":true},
  "summary":{"enabled":1,"ad_enabled":1,"ht_enabled":0,"gx_enabled":0}
}
```

游戏列表项字段：

```text
id, agent_id, name, game_icon, game_key, game_url, status, ad_status,
lucky_enable, is_landscape, is_game, is_mobile, is_imei, raffle_num,
star_countdown, over_countdown, star_coin, over_coin, coin_get,
exchange_num, commission_status, commission_source, commission_rate,
tixian_price, tixian_coin, tixian_wx, wx_appid, wx_secert, other_url,
settings_json, game_ad_status, game_lottery_num, created_at, updated_at
```

会员列表/详情项字段：

```text
id, agent_id, game_id, parent_id, username, name, image_url, otherlevel,
device_id, sex, real_name, card_no, address, receive_name, ip,
coin, freeze_coin, coin_user, coin_user_month, coin_user_day, vip,
status, exchange_enable, game_addiction_enable, game_addiction_time,
is_white, ht_status, ht_id, ht_top_id, beishu, percent_zhi,
percent_jian, percent_dai, percent_dai_two, raffle_open, raffle_num,
star_countdown, over_countdown, down_load, raffle_num2, star_countdown2,
over_countdown2, realname_enable, is_true, last_login_ip,
last_login_time, last_login_device_id, created_at, updated_at
```

核心资源接口：

| 资源 | 列表 | 创建 | 详情 | 更新 | 删除 |
|---|---|---|---|---|---|
| 主体 | `GET /api/v1/agents` | `POST /api/v1/agents` | `GET /api/v1/agents/{id}` | `PATCH /api/v1/agents/{id}` | `DELETE /api/v1/agents/{id}` |
| 游戏 | `GET /api/v1/games` | `POST /api/v1/games` | `GET /api/v1/games/{id}` | `PATCH /api/v1/games/{id}` | `DELETE /api/v1/games/{id}` |
| 会员 | `GET /api/v1/members` | `POST /api/v1/members` | `GET /api/v1/members/{id}` | `PATCH /api/v1/members/{id}` | `DELETE /api/v1/members/{id}` |

创建和更新模型的精确字段、类型、枚举以 `/openapi.json` 中的 `AgentCreate`、`GameCreate`、`MemberCreate`、`AgentUpdate`、`GameUpdate`、`MemberUpdate` 为准。

### 6.2 广告

广告列表项字段：

```text
id, parent_id, parent_payment_name, user_id, user_account, receive_name,
game_name, ecpm, coin, agent_id, game_id, estimate_income,
ad_network_platform_name, is_lottery, is_rw, reward_type, ad_type,
sub_ad_type, ad_group, is_type, is_fu, fu_type, is_look, status,
watched_at, ad_code, request_id, trans_id, created_at
```

常用筛选参数：`q,parent_id,user_id,game_name,agent_name,game_id,agent_id,coin_min,coin_max,estimate_income_min,estimate_income_max,ad_platform,ad_type,sub_ad_type,is_fu,fu_type,is_look,ad_group,status,watched_from,watched_to,limit,offset`。

统计响应形状：

```json
{
  "group_by":"day",
  "group_label":"日期",
  "summary":{},
  "items":[],
  "limit":20
}
```

导出 `GET /api/v1/ads/export` 返回 `text/csv; charset=utf-8`，响应头包含下载文件名。导入 `POST /api/v1/ads/import` 返回：

```json
{
  "batch_id":1,
  "total":2,
  "accepted":1,
  "rejected":1,
  "errors":[{"row":3,"errors":["request_id 已存在"],"request_id":"abc","raw_data":"{}"}]
}
```

导入支持 UTF-8、UTF-8 BOM 和 GBK/GB18030。导入字段别名和数字字段以 `docs/api.md` 的广告导入章节及运行时实现为准。

### 6.3 提现、补贴、流水、风控

提现项字段：

```text
id, user_id, agent_id, game_id, receive_name, receive_tel, receive_address,
exchange_value, exchange_type, status, target_status, plan_status, sub_msg,
reason, audit_operator_id, audit_operator_name, audited_at,
transfer_operator_id, transfer_operator_name, transferred_at, created_at,
updated_at
```

提现列表额外返回：

```json
{
  "summary":{"withdrawn":0,"pending":0,"blacklisted":null},
  "summary_unavailable":{"blacklisted":"blacklist_source_unverified"},
  "permissions":{"edit":true,"review":true,"row_review":true,"transfer":true,"blacklist":true}
}
```

补贴项字段：

```text
id, user_id, agent_id, game_id, tx_price, price, pics, status, target_status,
sub_msg, audit_operator_id, audit_operator_name, audited_at, created_at,
updated_at
```

金币流水项字段：`id,user_id,agent_id,game_id,coin_before,coin,coin_after,type,remark,created_at`。

风控历史项字段：`id,user_id,agent_id,game_id,tagcode,tags,hardware_main_id,ip,action,risk_score,risk_level,created_at`。

提现审核示例：

```http
POST /api/v1/withdrawals/123/reject
{"reason":"收款信息不完整"}
```

批量审核：

```json
{"ids":[123,124],"reason":"可选；batch-reject 拒绝时必须非空"}
```

无理由拒绝使用 `/batch-refuse`；真实转账使用 `/batch-transfer`。支付 provider 未配置时该接口返回 `503`，提现状态和转账状态保持不变。

补贴拒绝字段名是 `message`，不要复用提现的 `reason`：

```json
{"ids":[123],"message":"资料不完整"}
```

## 7. 游戏用户数据接口

行为弹窗使用会员或游戏范围接口：

| 页面数据 | 接口 | 主要筛选 |
|---|---|---|
| 抽奖 | `/api/v1/lottery-records` 或 `/api/v1/games/{game_id}/lottery-records` | `user_id,game_id,ip,tags,network_status,is_white,status,created_from,created_to` |
| 风控历史 | `/api/v1/risk/history` | `user_id,game_id,ip,tags,created_from,created_to` |
| 每日收益 | `/api/v1/member-daily-income` | `user_id,game_id,date_from,date_to,sort,order` |
| 金币流水 | `/api/v1/coin-logs` | `user_id,game_id,type,remark,created_from,created_to` |
| 提现记录 | `/api/v1/withdrawals` | `user_id,game_id,status,receive_name,receive_tel` |
| 分销用户 | `/api/v1/members` | `id,agent_id,game_id` |
| 登录历史 | `/api/v1/login-logs` 或 `/api/v1/games/{game_id}/login-logs` | `user_id,username,ip,created_from,created_to` |
| 收货地址 | `/api/v1/member-addresses?user_id={id}` | `game_id,receive_name,receive_tel,receive_address` |

游戏统计 `GET /api/v1/games/{game_id}/statistics` 返回 `metrics`、`income`、`activity`、`registrations`、`regions`、`mapdata`、`metric_series` 和 `registration_series`。其中缺少独立数据源的点击量返回 `null`，前端应显示未知或空态。

## 8. 写入接口速查

| 能力 | 方法与路径 | 请求体 |
|---|---|---|
| 主体批量状态 | `POST /api/v1/agents/batch-status` | `{ids:[1,2],status:0}` |
| 会员批量状态 | `POST /api/v1/members/batch-status` | `{ids:[1,2],status:1}`，可带 `agent_id` |
| 游戏内会员批量状态 | `POST /api/v1/games/{game_id}/members/batch-status` | `{ids:[1,2],status:1}` |
| 清空金币 | `POST /api/v1/members/{member_id}/clear-coins` | `{reason?:string}` |
| 设备封禁 | `PATCH /api/v1/members/{member_id}/device-ban` | `{target:"device",banned:true,expected_identifier:"..."}` |
| 会员地址 | `PATCH /api/v1/member-addresses/{user_id}` | `{receive_address:string,receive_name?,receive_tel?}` |
| 提现黑名单 | `POST /api/v1/withdrawals/{id}/blacklist` | `{receive_name,receive_tel}` |
| 黑名单状态 | `PATCH /api/v1/withdrawal-blacklist/{id}` | `{status:0|1}` |
| 主体 OSS | `PATCH /api/v1/agents/{id}/oss` | `{ossKey,ossKeySecret,endPoint,bucket}` |
| 分析分组 | `PATCH /api/v1/agents/{id}/analysis-settings` | `{coin:[],success:[],apps:[]}` |

## 9. 图片、导出和资源

- `POST /api/auth/avatar`：登录用户上传头像，成功 `201`，返回 `{url}`。
- `POST /api/v1/member-images`：operator 上传会员图片，成功 `201`，返回 `{url}`。
- 支持 PNG、JPEG、WebP、GIF；最大 2 MB；宽高最大 4096；服务端统一保存为 PNG。
- 图片 URL 形如 `/api/member-images/<48位十六进制>.png`，只能读取规范化 PNG。
- 导出接口返回文件流，不要调用 `response.json()`；应读取 `blob()` 并使用 `Content-Disposition` 或页面默认文件名。

## 10. 当前不可按成功流验收的接口

这些接口已经存在，但不代表业务闭环：

1. `GET /api/v1/risk/devices`：当前稳定返回 `503`，因为设备风控数据源和入选规则尚未确认。
2. `POST /api/v1/withdrawals/{id}/transfer`、`/batch-transfer`、`/batch-transfer-scheduled`：未配置支付 provider 时返回 `503`，不能伪造成功。
3. 广告统计、导入批次、导入错误、告警接口已由后端提供，但当前页面没有完整操作入口。
4. `PATCH /api/v1/member-addresses/{user_id}` 和清空金币接口已有后端能力，当前主前端没有独立入口。

## 11. 验收清单

前端联调至少应验证：

- 登录、token 持久化、401 自动退出、403 按权限隐藏按钮。
- 列表的 `total/items/limit/offset`、空数据、分页边界和排序。
- PATCH 只提交变化字段；409 后不覆盖用户当前编辑内容。
- 批量请求失败时整批不刷新为部分成功。
- 422 同时兼容字符串 `detail` 和字段错误数组 `detail`。
- CSV/图片使用二进制响应和正确的 Content-Type。
- 支付未配置时展示失败状态，不显示转账成功。
- 设备风控页面对 503 显示不可用态，而不是空列表成功态。

运行验证：

```powershell
python -c "from backend.app.main import app; print(len(app.openapi()['paths']))"
node scripts/check-js.cjs
python -m unittest discover -s backend/tests -q
python audit_pages.py
```

当前预期：OpenAPI 路径 `76`；JavaScript 和后端测试通过；页面审计唯一已知失败是设备风控 `503`。
