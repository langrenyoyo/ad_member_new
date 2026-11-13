# 鸭只易记 1.0.15 微信登录发布

- Android versionCode：16，包名：`com.heshangzhilian.yazhiyiji`。
- 微信 AppID：`wx78490a3096bdafb0`，业务游戏 ID：238。
- 正式签名 MD5：`f6d0647ac5999b4c522889b0746ffa70`。
- 公开配置位于 `apk/ya_zhi_yi_ji/wechat.properties`，可通过现有 Gradle 参数覆盖。
- AppSecret 仅保存在服务器 games 表的 `wx_secert` 字段；该历史拼写字段已加入请求日志脱敏规则。
- 包含此前完成的橙白页面、字体布局、激励奖励提示及授权后的应用使用数据功能。

## 验证

Android 单元测试、lintDebug、assembleRelease 成功；相关后端测试 48 项通过。
APK SHA256：`35cd45a8db392fceed4b0dc2ec8ada1c6c390d0727569a561873c6903e6c630a`。
实际微信授权仍需在安装微信的 Android 真机上验证，且微信开放平台中的包名和签名须匹配。

## 部署

`scripts/deploy_wechat_release.py` 从本地被 Git 忽略的 `serverdata.md` 读取连接参数及密钥，检查远端 main 与本地提交一致后备份数据库、拉取、执行 Alembic 迁移、更新游戏微信配置并重启服务。
部署结果保存到被 Git 忽略的 `artifacts/wechat-release-1.0.15/deployment.json`。
健康检查和无效授权码检查仅验证服务与登录处理路径，不能代替真机微信授权。
