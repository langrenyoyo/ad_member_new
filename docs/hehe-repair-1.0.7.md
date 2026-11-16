# 禾合 1.0.7 修复与真机复测

日期：2026-11-17（北京时间）。包名 `com.fajuohw.skfjuihwgifguye`，版本代码8，沿用原签名覆盖安装，保留登录及学习数据。

## 已修复并验证

- 建立禾合运营主体ID1，将应用ID1和原主体ID0下的本应用会员关联到有效主体。未绕过主体或提现校验；提现页已显示 **1元／1金币** 档位。
- 福利活动接口不再报“主体已停用”。当前无已发布活动，展示正常空态；未创建虚构活动或修改提交资料页面。
- 开启已配置的Taku广告与可信人民币eCPM奖励结算，启用前校验RSA密钥。维持1金币=1元，分佣关闭，不添加测试金币。
- 真机完成插屏→激励视频→插屏，出现 **“奖励已到账，+0.05金币”**。后台会话状态rewarded，余额0.05；金币流水只有一笔对应收入，备注为加密人民币eCPM奖励。
- 无公告内容时不再自动弹出空公告。覆盖安装后直接进入首页，学习数据仍为11题、60学习积分。
- 邀请页将普通会员邀请码不具备强制注册资格的说明前置。保留团长/代理邀请码注册规则，不擅自提升测试会员等级。
- 邀请页使用服务端返回的应用协议，禾合配置为`hehe://invite`；新版保留旧光迹协议兼容入口。ADB已验证新协议可交付给新版MainActivity。
- 发布邀请页APK下载地址，HTTPS HEAD返回200，文件50,644,502字节，上传后SHA256与本地一致。
- 修改密码说明更新为微信首次登录设置系统密码、支付宝绑定验证已有密码。补贴记录页旧品牌改为HEHE DAILY。
- 前轮疑似登录丢失已定位：`invite-back.xml`、`profile.xml`和`profile-bottom.xml`实际属于手机上的旧包`com.guangji.nightroad`。新版账户与冷启动正常；已停止旧包运行，未卸载或清除旧数据。

## 验证

- 后端邀请落地页测试：6项通过，含协议配置与非法协议回退。
- Android：testDebugUnitTest、lintDebug、assembleRelease通过；apksigner验证通过，ADB覆盖安装成功。
- 线上服务重启后active，邀请解析和APK下载可用。
- 服务端变更前已备份数据库、环境文件及两个部署文件。数据库/环境备份：`/opt/guangjiyexing/backups/hehe-repair-20261116-194911`（目录时间使用服务器UTC时钟）。

## 交付

- [APK下载](https://hehe.hehkun.cn/downloads/hehe-latest.apk)
- [本地APK](../artifacts/hehe-repair-1.0.7/hehe-1.0.7-release.apk)
- APK SHA256：`cca07dd989d3bd324ebff8fc5f3eddcacff93a8c5b515906d7f2ac8826fa49b7`
- 签名证书MD5：`ed9bf0dc3b892873aa38fa46a4cc2cbd`
- 签名证书SHA1：`3850f405634d7e8777b40e263183063dec025ce9`

## 真机截图

- [提现档位恢复](../artifacts/hehe-full-device-test/repair-wallet.png)
- [福利正常空态](../artifacts/hehe-full-device-test/repair-welfare.png)
- [奖励金币弹窗](../artifacts/hehe-full-device-test/repair107-coins-popup.png)
- [奖励流水及余额](../artifacts/hehe-full-device-test/repair107-current.png)
- [邀请资格提示](../artifacts/hehe-full-device-test/repair107-invite.png)
- [新版启动首页](../artifacts/hehe-full-device-test/repair107-start.png)
- [补贴页品牌修正](../artifacts/hehe-full-device-test/repair107-subsidies.png)

## 仍需业务资料或进一步测试

- 真实提现仍未执行：会员余额0.05金币，低于1金币档位，且未绑定真实支付宝账号。
- 福利申请/审核/发放仍需后台发布真实活动后复测。
- 普通会员U07O2B仍不是可用于强制注册的邀请码；需运营在后台按实际身份配置团长/代理后用于拉新。
- 本轮未重新测试短信（按用户先前要求暂不测试），未新增测试账号。
- 原生广告尝试出现“暂时无法获得广告”，未向用户暴露SDK错误；真实激励/插屏已展示并结算成功，不代表所有广告位每次都有填充。

前轮报告中的主体阻塞、广告未开启、下载缺失和登录待复现结论，以本记录的复测结果为准。
