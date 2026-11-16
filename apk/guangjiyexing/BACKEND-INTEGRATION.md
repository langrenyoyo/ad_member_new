# 后端对接与验收

本客户端对接本项目 `/api/app/v1/`，激励广告使用 TAKU 服务端回调结算。

## 当前流程

1. 登录并读取账号所属游戏的 bootstrap；请求前刷新即将过期的 Token，业务接口 401 后最多刷新重试一次。
2. 读取设备风控配置；开启时完成 challenge → 阿里云设备 Token → verify。`limited=true` 表示受限设备，只有 `remaining=0` 才在客户端阻止广告申请。
3. 创建一次广告会话；网络传输失败时顺序重试一次，保留同一个 `client_request_id` 和 `risk_check_id`。
4. 在 SDK load 前，用 `ATAdConst.KEY.USER_ID`、`USER_CUSTOM_DATA` 原样传入服务端响应。加载成功自动展示，加载期间禁止重复点击。SDK 实例不使用已完成会话预加载下一条广告。
5. 上报曝光和激励完成；客户端不自行加金币。完成后每两秒查询本次会话，最多约 30 秒，确认 rewarded 后刷新钱包。超时显示待确认，可重新进入钱包或广告记录查看。
6. 加载或播放失败、未获激励关闭时，通过包含 session_token 的 fail 上报。曝光、奖励和结束 SDK 回调去重。

金币以 BigDecimal 解析。广告历史只显示结算状态，不把后端会话配置快照当作实际奖励金额；实际余额以钱包为准。提现读取 `tiers/coin_cost` 和 `payout.amount_cents`，支付宝绑定读取 `account_masked`。

## 本机构建

使用 JDK 17，`local.properties` 的 `sdk.dir` 指向本机 Android SDK（该文件不提交）。

```powershell
$env:JAVA_HOME = 'D:\Android\Java\jdk-17.0.20.1+1'
$env:GRADLE_USER_HOME = 'D:\Android\gradle-cache'
.\gradlew.bat :app:assembleDebug :app:testDebugUnitTest :app:lintDebug
```

Gradle 版本由 wrapper 固定为 8.14.5。测试覆盖小数金额、提现 JSON、绑定状态、UTC 时间、限次、失败上报凭据和 SDK 事件去重。APK 输出在 `app/build/outputs/apk/debug/app-debug.apk`。

## 真机仍需验证

- 本地单测不会触达线上钱包，不会模拟线上发奖。
- 登录测试账号，完整观看新广告，关联 request_id、会话和平台 trans_id，检查回调、金币流水与钱包增量。
- TAKU 控制台必须开启该广告位的服务端激励，回调中的 extra_data 必须等于本次申请返回的原始字符串。
- `app/libs` 未提供阿里云私有 SDK AAR。游戏开启设备风控前，需放入真实 AAR 并配置 `aliyunDeviceRiskAppKey`；未配置时客户端明确阻止加载，不绕过后端风控。
- 微信登录仍取决于平台登记的 AppID、包名、签名和后台游戏配置，debug 签名需要单独核实。
- 后端此前发现的非标准 602 响应异常、奖励快照与实际金额不一致，属于服务端问题，本次客户端改动未部署或修复服务器。

## 2026-10-09 本机验证结果

- `assembleDebug` 成功，输出 APK 49,619,655 字节；v2 签名校验通过。
- `testDebugUnitTest`：11 个测试，0 失败、0 错误。
- `lintDebug` 成功：0 errors、90 warnings；主要为向量资源、未使用资源及 SDK 单例持有对象的提示。
- ADB 设备列表为空，未进行本轮真机展示、TAKU 真实回调或真实发奖。
- 新 APK 使用本机 debug keystore，签名与原 `apk/鸭只易记-debug.apk` 不同。不能直接覆盖安装旧签名版本；优先取得原 debug keystore 重签。如选择卸载重装，会清除旧应用数据，应由使用者明确选择后操作。微信开放平台也需核对 debug 签名。
