# 禾合支付宝提现证书接入

已读取 `crt/hehe`：应用证书、支付宝 RSA2 公钥证书链、支付宝根证书包、CSR、应用公钥和原始私钥。

- 支付宝 AppID：`2021006175692009`。
- 应用私钥与应用证书匹配；应用和支付宝签名证书有效至 2031-07-17。
- 后端新增证书模式：计算 `app_cert_sn` 和 RSA 根证书序列号集合 `alipay_root_cert_sn`，随请求一起签名；使用支付宝证书公钥验证原始响应 JSON 和回调签名。
- 保留原公钥模式兼容；不改变订单冻结、审核、幂等转账、失败退款与查询确认逻辑。
- `crt/` 已加入 Git 忽略规则，私钥不进入 APK。

新服务器已更新 `/opt/guangjiyexing/backend/app/payment.py`，证书和转换后的 PKCS8 PEM 私钥保存在 `/opt/guangjiyexing/secrets/alipay/`，目录权限 700、文件权限 600，专用服务账号可读。环境变量写入 `/opt/guangjiyexing/.env`，生产模式已启用。原配置与代码备份位于 `/opt/guangjiyexing/backups/alipay-integration/`，含敏感环境备份，勿公开。

验证：14 项既有提现测试、1 项证书模式测试通过。线上使用随机商户订单号调用只读 `alipay.fund.trans.common.query`，返回 `40004 / ORDER_NOT_EXIST`，响应 RSA2 验签通过。服务运行和健康检查正常。没有发起真实转账；查询成功不等于真实转账和到账已验收。

尚缺业务配置：禾合应用 ID 1 的 `tixian_price` 和 `tixian_coin` 均为空，APP 提现档位接口会返回 409。需由运营确定提现金额与各档金币数后配置，不能擅自制定兑换规则。当前 APK 已有支付宝绑定与提现接口，无需为证书接入重新打包。
