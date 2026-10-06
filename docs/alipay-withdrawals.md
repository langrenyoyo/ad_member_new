# 支付宝提现接入和 APP 契约

代码已实现绑定收款资料、提现档位、申请冻结、审核驳回、支付宝转账、主动查单、同商户订单号重试、回调验签和对账命令。真实支付宝应用和密钥未配置，当前不会发送真实资金，也没有完成支付宝沙箱或生产联调。

## 支付宝配置

本版使用 **RSA2 公钥模式**，需支付宝应用拥有 `alipay.fund.trans.uni.transfer`（单笔转账到支付宝账户）和 `alipay.fund.trans.common.query` 权限，并开通对应商家转账产品。证书模式应用不能直接使用本版 PEM 公钥配置，需要接入应用证书、支付宝证书和根证书参数后联调。

安装 `backend/requirements.txt`。密钥文件存放在仓库外，使用 PEM 格式：应用 RSA 私钥、支付宝 RSA 公钥；不是应用公钥。至少 2048 位。不要将私钥放在聊天或提交到 Git。

本地 Python 启动不自动读取 `.env`，需在同一个 PowerShell 进程设置环境变量：

```powershell
$env:PAYMENT_PROVIDER = 'alipay'
$env:ALIPAY_ENV = 'sandbox'
$env:ALIPAY_APP_ID = '<支付宝应用 ID>'
$env:ALIPAY_PRIVATE_KEY_PATH = 'D:\private-keys\app-private.pem'
$env:ALIPAY_PUBLIC_KEY_PATH = 'D:\private-keys\alipay-public.pem'
$env:ALIPAY_TIMEOUT = '10'
$env:ALIPAY_NOTIFY_URL = 'https://<你的域名>/api/payments/alipay/notify'
python backend/run.py
```

`ALIPAY_NOTIFY_URL` 可留空，以主动查询为准。应根据已签约产品核实是否支持、如何配置转账通知。`ALIPAY_ENV=production` 才使用生产网关；生产模式禁止使用 sandbox。订单保存环境和 APP_ID，更换应用或环境后禁止处理旧订单，防止跨环境重复支付。

配置检查：管理端 `GET /api/v1/payment-status`，后台提现页面顶部也会显示状态。`available=true` 仅说明本地密钥配置可加载，不证明支付宝已授予转账权限或商家余额充足。

Docker Compose 已转发这些环境变量，但 PEM 文件必须通过部署时的只读 volume 挂载到容器，`*_KEY_PATH` 填容器内路径；不要把密钥 COPY 到镜像。

数据库：迁移至 `e927_alipay_payouts`，新增 `alipay_accounts`、`withdrawal_payouts`。空库升级、降级、重升已验证。旧提现记录没有冻结订单，不能直接自动打款，避免为历史导入记录重复扣款/付款。

## APP 接口

以下接口都使用用户 JWT；管理员 token 不能代替用户登录。

| 方法 | 路径 | 用途 |
|---|---|---|
| PUT | `/api/app/v1/me/alipay` | 绑定/修改支付宝账号和真实姓名 |
| GET | `/api/app/v1/me/alipay` | 查询脱敏收款资料 |
| GET | `/api/app/v1/withdrawal-options?game_id=237` | 获取提现档位、是否绑定、支付是否配置 |
| POST | `/api/app/v1/withdrawals` | 创建提现并冻结金币 |
| GET | `/api/app/v1/withdrawals?limit=20&offset=0` | 自己的提现列表 |
| GET | `/api/app/v1/withdrawals/{id}` | 自己的提现详情和打款结果 |

绑定请求：

```json
{"account":"手机号或邮箱","real_name":"真实姓名","current_password":"当前登录密码"}
```

服务端验证当前密码，返回脱敏账号。存在待审、排队、支付处理中订单时不能更换账号。此绑定是收款资料登记和登录身份验证，**不是支付宝 OAuth 实名认证**；返回 `identity_verified=false`。转账时账号和姓名一并传给支付宝校验。微信登录但没有可用登录密码的账号，需要先补齐账号密码设置/身份验证流程，不能绕过密码验证直接绑定。

提现请求：

```json
{"request_key":"每次新申请的UUID，重试保持相同","game_id":237,"amount_cents":500}
```

金额单位为整数分。金币消耗来自游戏 `tixian_price`（元）和 `tixian_coin` 的一一对应档位，客户端不能上报金币消耗。只允许从用户绑定游戏提现。检查停用状态、提现开关、黑名单、每日次数 `exchange_num` 和可用金币。每日次数按北京时间计算，驳回也占当日申请次数。

支付未配置返回 `503`，不会创建订单或冻结金币。余额不足/次数用尽等返回 `409`，不存在档位返回 `422`。幂等请求返回原提现，编号更换金额/游戏返回 `409`。用户只能读取自己的订单，其他用户订单返回 `404`。

## 资金与状态

申请时可用金币减少、冻结金币增加；审核驳回或支付宝签名确认 `FAIL` 时退回金币；确认 `SUCCESS` 才清除冻结并设置转账时间。APP 返回 `payout`：

| state | 含义 |
|---|---|
| pending_review | 待审核或已审核待打款，结合主记录 status 判断 |
| queued | 管理员已加入打款队列 |
| processing | 已发起/结果不确定，资金保持冻结 |
| succeeded | 支付宝确认成功 |
| failed | 支付宝确认失败，金币已退回 |
| rejected | 审核驳回，金币已退回 |

只有 `payout.state=succeeded` 表示到账。新订单 `plan_status=1` 表示确认成功，`2` 表示排队/处理中；旧后台字段显示语义不一致，APP 应使用 `payout.state`。收款快照和订单金额不可修改。

金币流水：`200` 申请冻结（负数），`201` 驳回/失败返还（正数），`202` 到账结清冻结（可用金币变化为零）。底层会员金币仍沿用旧浮点字段，提现计算统一量化到六位小数，订单冻结数量存储 Numeric；后续如迁移整个账本，应统一所有余额写入路径。

## 后台打款及对账

原有审核入口共用新资金规则，包含单条/批量审核、驳回和编辑状态。新订单审核通过后可点击支付宝转账；处理中可查询或查询后重试原订单号。

- `POST /api/v1/withdrawals/{id}/transfer`
- `POST /api/v1/withdrawals/{id}/query-transfer`
- `POST /api/v1/withdrawals/{id}/retry-transfer`：先查单，仅在支付宝签名返回订单不存在时使用原 `out_biz_no` 重试。
- `POST /api/v1/withdrawals/batch-transfer`：逐单执行，返回 `items/errors`，外部转账不能承诺整批原子回滚。
- `POST /api/v1/withdrawals/batch-transfer-scheduled`：入队，后台任务实际发送。

定期执行：

```powershell
python scripts/reconcile_alipay.py
python scripts/reconcile_alipay.py --execute
```

第一条只查询待确认订单；第二条还发送管理员已入队订单。部署时在具有相同数据库和支付宝配置的环境中每分钟调度。当前未安装机器定时任务，因为尚无支付宝凭据。查询不出结果时资金持续冻结，页面显示处理中，不伪造到账或自动退款。确认失败的订单不会重新打款；用户需要新申请。

通知入口 `/api/payments/alipay/notify` 校验 RSA2、APP_ID、重复字段，通知仅触发主动查单，不直接使用通知金额或状态修改钱包。请求和响应使用 RSA2；响应验签使用原 JSON 字节切片。

## 验证

- `python -m unittest discover -s backend/tests -v`：118 项通过，包括 13 项支付专项。
- `python scripts/verify_alipay_ui.py`：隔离数据库+模拟支付渠道，浏览器完成审核、打款、刷新结果和正确金额展示。
- `npm run check`：41 个 JS 文件语法检查。
- 空 SQLite 库升级 head、降级至 e926、重新升级通过。

未验证：真实支付宝商家产品权限、沙箱/生产回包和到账、证书模式、PostgreSQL 并发集成运行。真实上线前必须使用目标应用进行小额联调和对账验收。
