# 前后端 API 闭环分析

## 结论

当前运行中的 FastAPI 应用注册 **76 条路径**，前端核心页面已经覆盖主体、游戏、会员、游戏用户数据、提现、补贴、黑名单、金币流水、历史风控、白名单、个人资料、教程和主体分析接口。核心读写链路总体可用，但还不能称为全量闭环。

已确认的阻断点有两个：

1. `/api/v1/risk/devices` 已被前端调用，但真实设备风控数据源和入选规则缺失，运行时返回 `503`。
2. 提现转账前端调用 `/api/v1/withdrawals/batch-transfer`，服务端在没有真实支付 provider 时返回 `503`；当前不会伪造支付成功。

此外，广告导入、导入批次错误、广告告警、广告统计、部分批量提现接口和会员地址写入接口只有后端能力，前端没有对应操作入口。

## 按页面的闭环矩阵

| 页面/模块 | 读取接口 | 写入接口 | 状态 | 证据/缺口 |
|---|---|---|---|---|
| 登录与壳层 | `/api/auth/login`, `/api/auth/me` | 登录、退出为前端会话操作 | 已闭环 | 页面审计通过 |
| 仪表盘 | `dashboard/summary`, `dashboard/registrations` | 无 | 已闭环 | `dashboard.js` 实际消费字段 |
| 主体管理 | agents 列表/详情、筛选、dashboard、OSS | 主体 CRUD、批量状态、OSS、分析配置 | 已闭环 | 浏览器与导出专项通过 |
| 主体分析 | `agents/{id}/analysis`, `analysis-settings` | 分析区间 PATCH、会员状态 PATCH | 已闭环 | 图表、筛选、分页和设置入口已接入 |
| 主体游戏 | agents 详情、games 列表/详情 | 游戏 CRUD、上/下架 | 已闭环 | `agent-games.js` 字段与参数一致 |
| 会员管理 | members 列表/详情、筛选选项 | 会员编辑、状态/白名单/兑换切换、批量状态、金币弹窗 | 已闭环 | 会员编辑字段验证通过；创建入口按权限隐藏 |
| 游戏用户数据 | lottery、risk、members、withdrawals、login、daily、statistics、income、coin、addresses | 会员状态、金币、设备封禁、会员编辑、提现审核 | 基本闭环 | 真实数据口径仍需业务方确认 |
| 广告列表 | `/ads`, `/ads/export` | 无 | 部分闭环 | 统计、导入、批次、告警未接入前端 |
| 提现 | `/withdrawals`、详情、黑名单 | 编辑、单条审核、无理由/有理由拒绝、拉黑、批量拒绝/转账 | 部分闭环 | 真实支付 provider 未接通；批量通过/有理由批量拒绝未接入口 |
| 补贴 | `/subsidies`、通用详情 | 编辑、删除、单条/批量通过、拒绝、批量删除 | 已闭环 | 前端批量拒绝使用无理由 `batch-refuse` |
| 金币流水 | `/coin-logs` | 无 | 已闭环 | 列表、筛选、导出由通用表格控制器接入 |
| 白名单 | `/risk/whitelist`、会员详情 | 会员白名单/状态/兑换切换、编辑、金币 | 已闭环 | 写入依赖会员 PATCH 权限 |
| 风控历史 | `/risk/history` | 无 | 已闭环 | 搜索链接、日期、分页、导出已接入 |
| 设备风控 | `/risk/devices` | 页面控制器已接入 | 未闭环 | 接口当前稳定返回 `503`，不能用假数据替代 |
| 个人资料 | `/api/auth/me`, `/api/auth/operations` | 头像上传、资料 PATCH | 已闭环 | 密码修改由资料 PATCH 完成 |
| 教程 | `/tutorials`, `/tutorials/{id}` | 无 | 部分闭环 | API 与正文渲染闭环；参考九张原图资源缺失 |

## 后端接口但当前无前端入口

这些接口本身已注册，不能因此误判为前后端闭环：

- `POST /api/auth/change-password`：当前资料页使用 `PATCH /api/auth/me` 的密码字段。
- `GET /api/v1/dashboard/activity`：首页读取的是 `summary` 和 `registrations`。
- `GET /api/v1/ads/statistics`、`POST /api/v1/ads/import`、`GET /api/v1/ads/imports`、`GET /api/v1/ads/imports/{batch_id}/errors`、`GET /api/v1/ads/alerts`。
- `POST /api/v1/withdrawals/batch-approve`、`POST /api/v1/withdrawals/batch-reject`、`POST /api/v1/withdrawals/batch-transfer-scheduled`、`POST /api/v1/withdrawals/{withdrawal_id}/transfer`。
- `POST /api/v1/members/{member_id}/clear-coins`、`PATCH /api/v1/member-addresses/{user_id}`。
- 通用详情路由是兼容入口；具体资源已有详情接口时，文档和前端应优先使用具体路径。

## 已核验的请求/响应对齐

| 检查项 | 结果 |
|---|---|
| 前端认证前缀 `/api/auth` 与业务前缀 `/api/v1` | 一致 |
| 前端统一 Bearer token | 一致 |
| 主体、游戏、会员 CRUD 方法 | 一致 |
| 会员编辑 changed-only PATCH | 一致；验证脚本通过 |
| 主体批量状态 `{ids,status}` | 一致 |
| 游戏用户数据的游戏范围路由 | 一致 |
| 提现单条审核 payload：有理由拒绝使用 `reason` | 一致 |
| 补贴单条审核 payload：拒绝使用 `message` | 一致 |
| 补贴批量无理由拒绝使用 `batch-refuse` | 一致 |
| 头像/会员图片原始二进制上传 | 一致 |
| 设备风控正常数据响应 | 未通过，服务端 503 |
| 真实提现转账结果 | 未通过，支付 provider 未配置 |

## 建议的闭环顺序

1. 提供设备风控数据表、入选规则、字段样例，恢复 `/risk/devices` 的真实 `200` 响应，再补充正常/空数据/错误测试。
2. 接入支付沙箱、签名、异步回调和幂等键，让批量转账能够返回真实处理中/成功/失败状态。
3. 为广告统计、导入批次和告警增加前端页面，或者明确把这些接口标记为后台运维接口，不纳入前台闭环验收。
4. 为会员地址保存和清空金币增加明确 UI 或从 API 文档中标注为内部接口。
5. 将当前文档生成接入 CI：每次路由或前端 API 调用变化时重新导出 OpenAPI，并检查闭环矩阵是否需要更新。

## 验证命令

```powershell
python -c "from backend.app.main_from_txt import app; print(len(app.openapi()['paths']))"
node scripts/check-js.cjs
python -m unittest discover -s backend/tests -q
python audit_pages.py
```

当前预期：OpenAPI 路径 76；JS 语法和后端测试通过；页面审计唯一失败项是设备风控 503。
