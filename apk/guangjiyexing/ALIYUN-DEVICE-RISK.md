# 阿里云设备风控 Android 接入（2026-10-09）

依据官方 [Android SDK 文档](https://help.aliyun.com/zh/fraud-detection/developer-reference/device-risk-detection-sdk-for-android)、[SDK 使用说明](https://help.aliyun.com/zh/fraud-detection/developer-reference/device-fraud-detection-sdk-compliance-description)及[服务端文档](https://help.aliyun.com/zh/fraud-detection/developer-reference/service-event-parameters-and-response-parameters-for-device-fraud-detection)。

## 已完成的代码接入

- 修正旧代码把初始化成功判为 0 的错误。SDK 的 SC_SUCCESS 为 **10000**，服务端 SAF 成功码为 **200**，两者不能混用。
- 等待异步初始化结果，单进程只初始化一次，等待超过 2 秒后在 IO 线程调用 getDeviceToken(bizId)。初始化超时可再次等待，但不重复初始化。
- 检查 SecurityToken.code 和 token 内容，保留 UF 弱网 Token，禁止缓存复用上次 Token，不输出 Token 或 AppKey。
- challenge 返回的 biz_id 原样用于取 Token，verify 仍由后端将同一个挑战 ID 作为 deviceTokenBizId 提交给 device_risk_pro。
- 修正反射 API 的 ProGuard 包匹配；检查多个 AAR 冲突、AppKey/AAR 缺失。
- 移除 Application 启动自动初始化。在开启风控的广告申请中展示用途和隐私政策，同意后需再次主动点击才采集；拒绝不影响本地学习。
- DataType 排除 NO_IDENTIFY_DEVICE_DATA 和 NO_EXTRA_DEVICE_DATA，保留基础信息和可变设备标识。此选择会降低对应检测能力，隐私说明必须与实际配置同步。没有新增电话和存储权限。

## 当前实包接入结果

用户已提供 Android-AliyunDevice-10060.aar；已核对真实类签名、10000 成功码、SecurityToken.code/token 以及 DataType 常量。SDK AppKey 已从 serverdata.md 提取到 Git 忽略的 local.properties；Gradle 参数优先于该本地配置，未将 AccessKey Secret 放入客户端。

开启 requireAliyunDeviceRisk=true 后 assembleDebug、testDebugUnitTest、lintDebug 均通过，20 项测试全部成功。APK 已验证包含 SecurityDevice 类和 arm64-v8a、armeabi-v7a、armeabi 三套 libsecuritydevice.so，包大小 56,834,203 字节。尚无 ADB 真机，未验证 AppKey 的云端有效性或真实设备 Token。

## 在其他构建环境配置

1. 登录[风险识别控制台](https://yundunnext.console.aliyun.com/?p=saf#/guide)，在设备 App 管理创建/选择当前 Android 应用，取得对应 **SDK AppKey**，下载匹配版本的 Android AAR。公开文档没有直接下载文件地址。
2. 将官方原始文件放到 `app/libs/Android-AliyunDevice-<版本>.aar`。本机已提供 10060 版本，AAR 被 Git 忽略，在其他构建环境需要另行配置。
3. 使用以下构建参数，或把 AppKey 配置在本地 Gradle 用户属性中：

```powershell
.\gradlew.bat :app:assembleDebug -PrequireAliyunDeviceRisk=true -PaliyunDeviceRiskAppKey=控制台SDKAppKey
```

`requireAliyunDeviceRisk=true` 会在缺少 AppKey/AAR 时直接构建失败；普通开发构建允许缺少组件，但运行时不会绕过已开启的后台风控。

4. 后端配置 `ALIBABA_CLOUD_ACCESS_KEY_ID`、`ALIBABA_CLOUD_ACCESS_KEY_SECRET`、`ALIYUN_RISK_REGION=cn-shanghai`。临时凭证另需 SecurityToken。按官方要求开通增强版服务及 RAM SAF 权限（文档列出 AliyunYundunSAFFullAccess）。AccessKey Secret 不能作为 SDK AppKey 放进 Android。
5. 在 ARM 真机上验收；官方不支持模拟器。确认 SDK 10000、后端 SAF 200、extend 设备 ID、风险标签及广告准入结果；测试拒绝同意、弱网、初始化失败、受限额度用尽等场景。

当前本机 APK 已包含真实 AAR 和 SDK AppKey；这不代表云服务权限已验证或完成真机验收。上线的完整隐私政策及第三方共享清单仍需纳入上述 SDK 披露。
