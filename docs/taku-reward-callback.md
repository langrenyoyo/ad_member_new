# TAKU 服务端激励回调

协议依据：https://help.takuad.com/docs/msbnkj ，2026-10-03 核对。

## 部署与启用顺序

本次先部署接口，不切换现有游戏 provider，不追溯发放历史奖励。
TAKU SDK 需 >= 5.7.56。客户端升级、服务端密钥和平台广告位配置全部就绪后，再将游戏广告联盟 provider 设置为 `taku`。

1. 在服务器 `/www/wwwroot/ad_member_new/.env` 配置 `TAKU_SEC_KEY`，值为 TAKU 服务端激励签名的 `sec_key`。不要填入管理后台 App Key，该字段会下发客户端。当前实现使用一个密钥，接入的广告位必须使用该密钥；不同密钥的广告位需要先扩展密钥映射。
2. 重启 `ad-member-new.service` 使环境变量生效。
3. 更新 App：请求广告会话后，在加载 SDK 广告前设置 `UserID = data.taku_user_id`、`UserCustomData = data.taku_extra_data`。透传值必须原样使用，不要只发送会话 ID，不要使用用户名或设备 ID 作为 UserID。
4. App `/complete` 在 TAKU 模式只报告等待验证，不发金币。通过 `/ads/history` 和 `/wallet` 刷新状态和余额；平台回调先到时 `/complete` 返回已奖励。
5. 确认游戏激励广告位 ID 正确，将 provider 切换为 `taku`，在 TAKU 激励视频广告位开启服务端激励，并填入下方完整 URL。部署接口本身不会替你修改 TAKU 控制台。

## 控制台回调 URL

```text
https://admember.yunjizhilian.asia/api/callbacks/taku/reward?user_id={user_id}&trans_id={trans_id}&reward_amount={reward_amount}&reward_name={reward_name}&placement_id={placement_id}&extra_data={extra_data}&network_firm_id={network_firm_id}&adsource_id={adsource_id}&scenario_id={scenario_id}&sign={sign}
```

接口使用 GET，不需要后台或 App Bearer Token。不能填写 `/ads/request` 或 `/complete`。

控制台 `is_test=1` 连通性探测返回 200，不验签、不写库、不发奖励。该探测成功不代表真实回调配置已就绪。

## 验签与结算

按官方顺序对 URL 解码后的参数原值（UTF-8）计算 MD5：

```text
trans_id=...&placement_id=...&adsource_id=...&reward_amount=...&reward_name=...&sec_key=...
```

如 URL 配置 `ilrd={ilrd}`，最后追加 `&ilrd=...`（包括空值），原始字符串直接参与签名，不能重新格式化 JSON。推荐先使用不含 ILRD 的 URL；添加 ILRD 前需要按实际数据大小调整反向代理 GET 请求行限制，避免 414。

成功/重复成功返回 HTTP 200；签名不符返回 HTTP 601；参数、归属、广告位或状态不符返回 HTTP 602。密钥缺失返回 503。依官方文档，TAKU 收到 200/601/602 均不重试；请求超时才按平台策略重试，因此应监控回调失败，不能假设平台会补发所有错误。

验证用户、provider、广告位和服务端生成的会话透传凭据。平台签名不包含 user_id 和 extra_data；额外的 HMAC 仅保护本系统会话上下文，不能改变平台签名覆盖范围。不能把客户端自行提供的回调 URL 或内容当作平台验签结果。平台交易 ID 全局唯一，已处理交易不能绑定另一会话，同一会话不能用另一交易再次发奖。

TAKU 回调在数据库事务中锁定会员/会话、写唯一事件、金币流水和广告列表记录；SQLite 使用 BEGIN IMMEDIATE，PostgreSQL 使用行锁。奖励使用创建会话时服务端确定的 reward_coin，忽略回调中的 reward_amount 作为发奖金额。TAKU 模式从客户端完成接口移除发奖，避免双渠道重复结算。

有效平台通知允许在会话创建后 24 小时内结算（即使客户端短会话已超时）；已失败会话不结算。过期时间窗口是本项目策略，不是 TAKU 官方参数。

广告列表记录关联 request_id、trans_id、会员、游戏和广告位，状态为“成功”。金币采用实际奖励；ECPM 保持 0，不把客户端 ILRD 或奖励金币伪装成广告收入。ILRD（如有）保存于回调事件作分析参考，不用于奖励计算。

## 验证

```powershell
python -m unittest backend.tests.test_taku_callback -v
python -m unittest discover -s backend/tests -v
```

测试使用临时数据库，覆盖签名、空/非空 ILRD、归属不符、探测、重复/并发通知、失败会话、延迟回调和客户端等待结算。真实 TAKU 回调仍须在配置密钥并更新 App 后联调。

官方建议第三方广告网络优先使用各自 S2S 激励验证；本次实现 TAKU 自身激励回调，不包含穿山甲、优量汇等网络的独立协议或展示收益 S2S 接口。
