# 禾合：中天短信验证码登录

## 文档核对

用户提供的 https://doc.zthysms.com/web/#/1?page_id=14 在本次检查中返回 `error_code=10101`，未能取得自定义发送协议，因此没有猜测该接口。

依据同站现行文档实现模板发送：

- 快速接入：https://doc.zthysms.com/web/#/1?page_id=236
- 模板短信发送：https://doc.zthysms.com/web/#/1?page_id=13
- 国内网关：`https://api.mix2.zthysms.com/v2/sendSmsTp`，POST UTF-8 JSON。
- `password = md5(md5(原始接口密码) + tKey)`，两次 MD5 均为小写十六进制，tKey 为秒级 Unix 时间戳。
- 只在 `code=200`、存在 `msgId` 且没有无效号码时认为提交成功；提交成功不等于手机已收到短信。

## 后台配置

在服务器 `/opt/guangjiyexing/.env` 配置以下变量，密码仅保存在服务器。Docker 部署同样支持这些变量。

```dotenv
SMS_PROVIDER=zthy
SMS_ZTHY_USERNAME=
SMS_ZTHY_PASSWORD=
SMS_ZTHY_SIGNATURE=
SMS_ZTHY_TEMPLATE_ID=
SMS_ZTHY_CODE_VARIABLE=code
SMS_ZTHY_TEMPLATE_PARAMS={}
```

用户名和密码必须是短信接口账号资料；签名按平台备案的原样填写，包括平台要求的括号。模板变量名必须与备案模板一致：例如模板验证码变量为 `var1`，则设置 `SMS_ZTHY_CODE_VARIABLE=var1`。如还有有效期变量 `var2`，可设置 `SMS_ZTHY_TEMPLATE_PARAMS={"var2":"5"}`。验证码变量始终由后台生成，不能用静态配置覆盖。

请确认账号已开通 API、具有可用余额，以及服务器出口 IP 已按账号要求授权。配置后执行 `systemctl restart guangjiyexing`。

## APP 兼容性和验证边界

当前禾合 1.0.3 已调用 `/api/app/v1/auth/sms/send` 和 `/auth/sms/login`，无需把短信密钥写入 APK，也无需为本次服务商切换重新打包。保留 6 位验证码、5 分钟有效期、60 秒重发间隔、手机号/IP 限额和最多 5 次错误尝试，以及邀请码与系统密码规则。

中天配置缺失时不会自动回退到其他供应商。省略 `SMS_PROVIDER` 时继续使用原阿里云服务，兼容现有部署。

自动测试覆盖签名与模板 JSON、成功响应、号码部分拒绝、超时/异常 JSON、缺失配置和错误信息屏蔽。真实短信送达及真机登录需补齐账号资料并指定测试手机号后再验证。不得把模拟测试描述为真实发送成功。
