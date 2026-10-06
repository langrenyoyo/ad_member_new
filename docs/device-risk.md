# 清机与双清广告风控

后台入口：风控管理 → 设备风控 → 清机与双清广告风控，输入游戏 ID 加载。风险管理员和超级管理员可修改规则、人工放行/标记风险，其他管理员只读。规则默认关闭，配置和人工处置均有审计记录。

## 识别与限次口径

- 服务器调用阿里云 SAF `ExecuteRequest`（2019-05-21），使用增强版 `device_risk_pro`，将响应 `Data.extend` 设备标识哈希后关联设备；APP 自报 `device_id` 不参与可信设备判定。
- 同一游戏中，同一阿里云设备首次出现新的安装实例，且已有历史安装实例时，标记为**疑似清数据或重装**。首次见到的设备不直接判为清机。
- 可填写阿里云控制台/服务商已确认的清机标签代码。公开文档没有承诺通用的恢复出厂标签，不能将 root、模拟器标签直接等同于双清。
- 设备标识不保证恢复出厂后永久不变；安装 UUID 由客户端保存，能被篡改或恢复备份。当前规则属于风险信号，不能百分之百识别物理双清。更强识别依赖阿里云实际产品能力及真机验证。
- 识别和限次为两个开关，限次要求先开启识别。每日条数 0–10000，0 表示风险设备不允许新申请广告。风险有效期 1–365 天，默认 7 天；修改期限仅作用于后续识别。
- 按北京时间每日成功批准的广告会话计数，覆盖所有广告类型；同一游戏同设备跨账号共享额度，同时检查当前账号当天的批准次数，取较大值。正常设备不受限，但识别开启期间的批准次数也会记录。
- 限次不因客户端报告广告失败而退还；同一有效会话的幂等重试不重复计数。已批准广告仍按原规则回调发奖。识别关闭期间不计入设备额度，重新开启后保留当日已有计数。
- 人工放行豁免该设备限次但仍要求云端校验；人工标记风险持续到人工恢复自动判定或放行。每日次数在北京时间零点按日期自然切换，不需要定时任务。

## 部署

1. 后端设置 `ALIBABA_CLOUD_ACCESS_KEY_ID`、`ALIBABA_CLOUD_ACCESS_KEY_SECRET`；临时凭据额外配置 `ALIBABA_CLOUD_SECURITY_TOKEN`。`ALIYUN_RISK_REGION=cn-shanghai`。
2. 开通增强版设备风险识别并给后端凭据授予对应 SAF 调用权限。密钥不能放入 APP；后台“凭据已配置”仅检查存在性，不证明服务已开通。
3. 在项目根目录运行 `python -m alembic upgrade head`，迁移版本 `e928_device_risk`，随后重启后端并更新静态资源。
4. 先让 APP 完成下述参数链路，再按游戏开启规则。当前代码测试使用模拟云端响应，上线前必须用真实 SDK/token 联调。

## APP 对接（均需要 APP Bearer token）

SDK 已集成还需接入以下服务端流程，每次新广告申请获取一次校验凭证：

1. `GET /api/app/v1/device-risk/config?game_id=238`：读取 `data.enabled`、`limit_enabled`、`daily_limit`。关闭时沿用原广告申请流程。
2. `POST /api/app/v1/device-risk/challenge`：`{"game_id":238,"install_id":"本次安装持久保存的随机UUID"}`。返回 `data.challenge_id`、`biz_id`、`expires_at`，5 分钟有效，每会员每分钟最多 10 次。install_id 长度 16–128，APP 正常启动/升级不要重新生成；禁用备份还原该值，清数据或重装时生成新值。
3. 在 Android 工作线程调用 SDK `getDeviceToken(biz_id)`，使用本次返回的 biz_id；不要复用启动时以其他 bizId 生成的 token。遵循 SDK 初始化和等待要求。
4. `POST /api/app/v1/device-risk/verify`：`{"challenge_id":"步骤2返回值","aliyun_device_token":"SDK返回值"}`。后端调用云端并绑定设备、账号、游戏，返回 `data.risk_check_id`、内部 `device_id`、`suspected_reset`、`limited`、`daily_limit`、`used`、`remaining`。`remaining=null` 表示当前不限次。
5. `POST /api/app/v1/ads/request` 保留原有字段并增加 `risk_check_id`：`{"game_id":238,"device_id":"原客户端设备ID","placement":"rewarded","ad_type":"rewarded","client_request_id":"本次广告请求UUID","risk_check_id":"步骤4返回值"}`。凭证只能批准一个会话，过期需重新申请；同一会话重试须保留原 client_request_id 和 risk_check_id。

错误：403 未校验/凭证不属于当前用户；409 过期或重复验证；429 限额已满或 challenge 请求过频；503 阿里云未配置/调用失败/未返回设备标识。校验失败不会降级放行，APP 应停止加载新广告并展示错误，不能自造设备码或循环重试。获取 challenge 后应及时完成广告申请，整个凭证有效期从 challenge 创建时起算 5 分钟。

## 管理接口

- `GET/PUT /api/v1/games/{game_id}/device-risk`：`enabled`、`limit_enabled`、`daily_limit`、`risk_days`、`reset_tags`。PUT 是完整规则更新，未传字段使用默认值。
- `GET /api/v1/device-risk/devices?game_id=238&limit=20&offset=0`：分页查看已校验设备、关联会员、风险原因、标签、有效期、今日设备次数。
- `PATCH /api/v1/device-risk/devices/{id}`：`{"mode":"auto|allow|restrict","reason":"必填处置原因"}`。

不存储原始 SDK token 和原始阿里云设备标识；保存哈希、云端请求号、风险标签及关联关系用于审计。TAKU 发奖依然由其独立的签名回调决定，设备校验不会代替 TAKU 回调。
