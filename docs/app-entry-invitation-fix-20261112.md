# 鸭只易记五项需求修复与验收

## 交付范围

Android 版本为 **1.0.5（versionCode 6）**，包名及发布签名沿用现有版本，可覆盖安装。后台、浏览器邀请页及 Android 源码随本次提交交付；未部署服务器。Android 工程路径为 `apk/ya_zhi_yi_ji`，本地签名密钥、SDK 配置及构建产物不入库。

| 需求 | 实现及边界 |
|---|---|
| 启动授权 | 登录前展示权限说明，跳转 Android「使用情况访问权限」。拒绝、按返回退出、从设置返回仍未授权均退出任务，不能进入业务页面。授权被撤销后再次恢复 APP 也会退出。沿用项目现有 PACKAGE_USAGE_STATS，用于查看应用使用情况；不是查询全部已安装应用的 QUERY_ALL_PACKAGES。|
| 自动公告 | 每次冷启动自动获取当前应用后台公告，关闭 × 后才进入业务页面。点击外部无效；加载失败提供重试，不能跳过。空公告展示“暂无公告内容”。从“我的”移除公告图标与目录入口。本次设计为一次冷启动弹一次，返回设置或广告后不反复弹出。|
| 广告记录 | 用户列表仅保留已观看的激励广告，每行仅时间及实际所得金币。副广、仅请求未展示的广告不进入列表；后台先过滤再分页和计数。金币取真实 CoinLog，未结算显示 0。副广采集、管理后台核查及发奖逻辑保留。|
| 登录方式 | APP 页面只保留短信验证码和微信登录，去掉账号密码登录、独立注册入口。短信/微信新用户按原后台规则自动注册，邀请码共用；不改动收款账户设置密码功能及旧版本后台兼容接口。|
| 邀请页面 | 展示六位邀请码、邀请链接、复制/分享操作、二维码。二维码由 APP 本地生成，与分享链接一致。浏览器邀请页提供短信注册/登录、Android 下载、打开已安装 APP；邀请链接携带 game_id 和 invite_code，APP 接收链接后自动填入邀请码。|

所有会员继续拥有邀请码。只有有效团长或代理的邀请码具备注册绑定资格；普通会员链接可展示，但不能绕过强制邀请码注册。浏览器对普通会员资格有明确提示，最终校验由后台执行。

安装新 APK 后，浏览器参数不会由 Android 自动保留到首次启动。已在浏览器完成注册的用户，通过同一手机号登录 APP 即可保留后台邀请关系；仅下载未注册的用户，可重新打开原邀请页点击“打开 APP”，或复制邀请码后填写。没有宣称实现应用商店级的安装归因。

## 接口与页面

API 前缀：`/api/app/v1`。

| 路径 | 方法/参数 | 用途 |
|---|---|---|
| `/policy` | GET，`game_id` | 无需登录获取公告、公告版本和注册规则。|
| `/invite-code` | GET，Bearer Access Token | 返回 `invite_code`、`level`，新增 `invite_path`、`registration_eligible`；所有会员均可展示。|
| `/invitations/resolve` | GET，`game_id`、`invite_code` | 新增公开接口，校验邀请码所属应用及邀请人状态，返回注册资格、下载地址、APP 打开地址。失效或跨应用返回 404，格式不合法返回 422。不返回手机号、会员 ID 或 Token。|
| `/auth/sms/send` | POST，`phone`、`game_id` | 沿用短信发送接口及频率限制，返回 `challenge_id`、`retry_after`、`expires_in`。|
| `/auth/sms/login` | POST，`phone`、`code`、`challenge_id`、`game_id`、`device_id`；新用户按规则传 `invite_code` | 浏览器与 APP 共用短信验证和自动注册。浏览器使用 `platform: web`，不传密码。验证码一次性使用，错误/过期按既有接口拒绝。|
| `/ads/history` | GET，Bearer Access Token；`game_id`、`page`/`page_size` 或 `limit`/`offset` | 会员及应用隔离，过滤已观看激励广告后再分页。APP 仅展示 `watched_at`、`coin_added`。|

邀请网页：`/invite.html?game_id=238&invite_code=XXXXXX`，配套静态文件 `/invite.js`、`/invite.css`。

打开 APP：`yazhiyiji://invite?game_id=238&invite_code=XXXXXX`。Android 仅接受当前构建所属应用 ID 和六位英文数字码；已登录用户不会自动更改邀请关系。

网页认证 Token 不写入 URL、localStorage 或 sessionStorage。sessionStorage 仅保存浏览器本次会话的随机设备 ID；浏览器登录成功后，引导同一账号在 APP 登录。

## 已完成验证

- Android Debug、Release 各 **71 项单元测试通过**。包含邀请 URL 参数和二维码解码验证；两种构建 Lint 均无错误，现有及新增提示共 105 个 Warning、4 个 Information。
- 相关后台 **24 项测试、92 个子用例通过**，全部使用临时数据库，覆盖混合副广后的正确分页、真实金币流水、身份/应用隔离、普通会员资格、短信自动注册与验证码防重放。
- 浏览器 Chromium 手机尺寸实测通过：有效邀请、短信注册成功、普通会员提示、无效链接阻断、下载/APP 打开地址、Token 不落地、无运行错误；实际下载 APK 的 SHA256 与正式发布包一致。
- 华为 JEF-AN20、Android 12 真机覆盖安装发布包成功；拒绝授权退出、系统授权页返回未授权退出、授权后自动公告、点外部不关闭、点 × 进入首页均已验证。保留原 APP 账号与本地学习记录。
- 发布版真机“我的”已移除公告入口；广告记录只有观看时间与金币；邀请链接与二维码已显示。直接从手机截图解码二维码，结果与复制/分享用的浏览器链接一致。
- 独立 `.devtest` 真机验收包连接本地隔离服务，验证非空公告、浏览器唤起 APP 后自动填码、仅微信/验证码入口、短信登录成功及普通会员邀请码展示。隔离服务内有 25 条激励及 10 条副广，用户列表只返回 25 条激励记录。

证据目录：[artifacts/app-entry-20261112](../artifacts/app-entry-20261112/)。包含构建日志、后台用例日志、浏览器截图、真机截图和 XML。最终包信息及哈希见目录中的 `release-manifest.json`。

全量后台回归为 **265 项通过、2 项失败、140 个子用例通过**。失败项为 `test_whitelist_names_sort_dates_and_fixed_membership`、`test_whitelist_switch_permissions_and_removal`：用例未带管理员认证访问白名单接口，返回认证错误而非列表，随后发生 KeyError。已核对该接口与 Git HEAD 完全相同，本次未修改它，也未放宽其认证要求。首次合并执行还暴露既有测试导入顺序导致管理员密码环境不一致；重新以 CoreCrud 的隔离环境初始化后，得到上述结果。生产数据库未用于新增验收数据。

## 上线操作及待验收

1. 部署 `backend/app/main_from_txt.py`、`backend/app/member_policy.py`、新增 `backend/app/invite_landing.py`，重启后台服务；无新增表和数据库迁移。
2. 发布 `public/invite.html`、`public/invite.js`、`public/invite.css`。确认域名能访问这些路径和 `/api/app/v1/invitations/resolve`。
3. 将发布 APK 放在站点的 `public/downloads/yazhiyiji-latest.apk`，或为后台设置 `APP_DOWNLOAD_URL`（HTTPS 下载地址或站内 `/downloads/...`）。文件不存在且没有配置时，页面明确提示暂未发布，不给出虚假下载按钮。发布包已在本地放入该默认路径，Git 忽略 APK，服务器需另行上传。
4. 用户安装新版 APK。仅部署后台不会改变旧 APK 的权限、公告或登录页面。
5. 上线后验证真实短信供应商、微信授权、外网浏览器扫码注册和 APK 下载；本轮浏览器及新注册链路使用本地隔离短信服务，未向生产发送测试短信。微信真实授权本轮未重新验收。

APK 的历史记录客户端过滤可兼容旧服务器，但浏览器邀请页及后台正确分页需要同步部署本次服务器代码。ZXing 3.5.3 用于本地二维码生成，许可证已随 APK 资源及源码交付。
