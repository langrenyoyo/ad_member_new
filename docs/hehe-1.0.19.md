# 禾合补贴按提现申请金额达标

补贴资格改为按北京时间当天成功创建的提现申请金额累计，达到活动 withdrawal_cents 即可申请。待审核、处理中、到账、拒绝、失败均计入，不要求已转账；未创建成功的请求不计入。每日名额、截图审核、同日次数及待审核申请限制不变。

新增 submitted_withdrawal_cents 和 withdrawal_basis=submitted；兼容旧客户端的 confirmed_withdrawal_cents 字段返回同一资格金额。旧版标签可能仍写“已确认”，1.0.19 改为“今日提现申请”。历史补贴快照保留旧的到账规则说明。

测试：补贴19项及30个子测试通过，包含北京时间跨日、待审核/拒绝订单计入、不同会员隔离、名额并发和驳回重试。

APK versionCode 20，包名 com.fajuohw.skfjuihwgifguye。
