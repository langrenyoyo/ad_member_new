# 光迹夜行 V1.0

## PDF 分析

`guangjiyexing.pdf` 为两页版权认证材料，并非 UI 设计稿。可用于本次构建的应用信息：名称“光迹夜行”、包名 `com.guangji.nightroad`、版本 V1.0。证书没有提供页面截图、接口或微信/广告平台参数。原 PDF 未修改，个人证件信息未打入 APK。

## 新包

独立工程：`apk/guangjiyexing`。以当前鸭只易记 1.0.20 功能代码为基础，沿用此前参照 `apk/moban.apk` 制作的页面布局及橙白配色。参考 APK 包名为 `com.lixiaoqiang.youmifudai2026`、版本 1.1.5；未复制其包名或服务端身份。

新包版本 1.0、versionCode 1。替换应用内名称及图标，微信回调为 `com.guangji.nightroad.wxapi.WXEntryActivity`，邀请唤起 scheme 为 `guangjiyexing`。原鸭只易记工程不受影响，两包可以共存。

保留登录、系统密码设置、首页、答题、广告奖励与金币提示、邀请、会员、使用统计、提现和设置的功能框架。

## 联调限制

这是新包名的安装/联调版本，不代表第三方平台已开通：

- 尚未提供独立业务配置，暂沿用现有后端地址和游戏 ID 238；登录后业务数据属于原游戏，正式发布前须切换独立游戏 ID。
- 微信 AppID 留空，避免误用与原包名绑定的 AppID。微信登录入口保留，配置完成前会提示未配置。
- 广告和设备风控接口框架沿用原实现。新包名需要对应平台核验和配置，不能据此认定广告可展示或收益可结算。
- 邀请链接服务器仍需为新业务配置 `guangjiyexing` 唤起，才能完整联动。
- 使用现有本地发布证书签名，MD5 `f6d0647ac5999b4c522889b0746ffa70`；证书信息需登记在新应用的平台配置中。

构建：`python scripts/build_guangjiyexing.py`。构建日志与交付 APK 在 `artifacts/guangjiyexing-1.0`。实际微信授权、广告、提现等需参数齐全后真机验收。
