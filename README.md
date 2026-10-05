# 成语问答 Android APP

一个离线优先的成语学习与答题 Android MVP，使用 Kotlin、Jetpack Compose、Room 和 MVVM 架构实现。

## 已实现功能

- 300 条内置成语题库，包含释义、拼音、出处、例句、近义词、反义词和难度
- 释义选择题
- 成语填空题
- 简单、中等、困难筛选
- 按题库分类筛选
- 每局 10 题
- 即时答题反馈
- 积分和连续答对奖励
- 答题结果、正确率和用时统计
- 错题本
- 错题复习
- 成语详情页
- 成语收藏
- 学习统计和连续学习天数
- 声音提示开关
- 触感反馈开关
- 深色模式
- 清除学习记录
- 无网络离线使用
- “我的”页面和首页 / 我的双 Tab 导航
- 首页快速入口进入错题本和学习统计
- 手机号密码注册、登录、Token 刷新和退出登录
- 用户 API 会话恢复和当前用户信息同步
- AnyThink 广告 SDK Core 及 GDT、百度、快手、穿山甲和 Kuying 适配器依赖

## 技术栈

- Kotlin 2.0
- Jetpack Compose
- Material 3
- Room
- KSP
- Kotlin Coroutines
- StateFlow
- SharedPreferences 本地会话
- Android Gradle Plugin 8.5.2
- Gradle Wrapper 8.14.5
- compileSdk / targetSdk 35
- minSdk 26

## 构建与测试

确保本机已经安装 Android SDK，并让 `local.properties` 中的 `sdk.dir` 指向 SDK 根目录。

```bash
./gradlew testDebugUnitTest
./gradlew lintDebug
./gradlew assembleDebug
```

Debug APK 输出位置：

```text
app/build/outputs/apk/debug/app-debug.apk
```

也可以直接使用 Android Studio 打开项目根目录，等待 Gradle Sync 完成后运行 `app` 模块。

## 当前版本说明

答题记录、积分、错题和设置保存在本地，登录相关功能通过用户 APP API 与服务端同步。账号云端同步、排行榜、好友对战和 AI 题目生成属于后续版本范围。

## 用户登录 API

用户 API 基地址为 `https://admember.yunjizhilian.asia/api/app/v1/`，客户端已接入：

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /me`
- `GET /bootstrap?game_id=238`

请求会携带文档要求的 `X-App-Id`、`X-App-Version`、`X-Platform` 和安装实例 `X-Device-Id`，登录凭证使用服务端返回的 Access Token 和 Refresh Token。Token 保存于本地会话中，应用启动时会恢复当前用户；网络暂时不可用时保留缓存用户状态，服务端明确返回凭证失效时清理会话。

应用启动恢复会话后会调用 `bootstrap`，读取用户、游戏状态、广告总开关、广告位配置和服务端时间；当前默认使用 `game_id=238`。初始化失败不会阻塞本地题库和离线答题，登录成功后也会立即执行一次初始化。

接口文档当前没有定义微信业务登录接口，因此微信按钮目前只调起微信 SDK 并接收授权 `code/state`，不会创建伪造的本地登录会话，也不会把授权结果提交后端。手机号登录、当前用户和应用初始化接口已经可以按文档进行真实联调。

## 广告 SDK 配置

项目已经接入 AnyThink Core 6.6.51 及你提供的广告网络适配器。应用启动时会优先读取 `bootstrap.data.ad_config.app_id` 和 `bootstrap.data.ad_config.app_key` 初始化 SDK；服务端未返回时才回退到构建参数 `BuildConfig.ANYTHINK_APP_ID` 和 `BuildConfig.ANYTHINK_APP_KEY`。两套凭证都为空时跳过初始化，因此不配置广告凭证也可以正常运行和测试答题功能。

构建时通过 Gradle 参数注入凭证：

```bash
./gradlew assembleDebug \
  -PanythinkAppId=你的AnyThinkAppId \
  -PanythinkAppKey=你的AnyThinkAppKey
```

本地 `.aar` 或 `.jar` 文件可以放入 `app/libs/`。应用拿到 `bootstrap` 后，会在游戏和广告总开关均开启且凭证有效时初始化 AnyThink；首页只会读取 `placement` 或 `ad_type` 为 `splash`、`open`、`open_screen`、`app_open` 的广告位作为开屏，并读取 `banner`、`home_banner` 或 `bottom_banner` 作为首页横幅。开屏只在一次进程启动中请求一次，横幅 View 离开首页时会释放。

因此后台需要至少配置对应的开屏和横幅广告位，例如：

```json
{
  "placement": "splash",
  "ad_type": "splash",
  "ad_unit_id": "你的开屏广告位ID"
}
```

```json
{
  "placement": "banner",
  "ad_type": "banner",
  "ad_unit_id": "你的横幅广告位ID"
}
```

当前联调账号返回的后台配置只有 `rewarded` 广告位，所以客户端会跳过开屏和横幅；不会把激励广告位错误地当作其它广告形式使用。

手机号和密码通过 HTTPS 发送到用户 API，服务端负责密码哈希和账号校验；客户端不会保存密码。微信 SDK 调试登录使用微信 AppID `wx91cfc0d66f031470`，当前 Android 包名配置为 `com.fajuohw.skfjuhwgifguye`，只调起微信并接收授权 `code/state`，暂不提交后端。AppSecret 不写入客户端；后续接入业务登录时由服务端使用授权码换取微信身份。
