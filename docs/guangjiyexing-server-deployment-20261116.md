# 光迹夜行独立服务器部署

部署日期：2026-11-16。服务器连接参数读取自 `apk/server.md`，本文不记录 SSH 密码。

## 访问和账号

- 管理后台：https://guangjiyexing.hehkun.cn/admin/
- 健康检查：https://guangjiyexing.hehkun.cn/api/health
- 管理员账号：`admin`
- 随机初始密码：本地 `artifacts/new-server-deploy/admin-credentials.json`，该目录已由 Git 忽略。
- 原宣传首页保留在 https://guangjiyexing.hehkun.cn/ 。

## 部署内容

- 项目代码：`/opt/guangjiyexing`，来源提交 `c357b0d03a564db89a82c8ff091806fee165138a`。
- 独立 Python 3.11.10：`/opt/guangjiyexing-runtime/python`。
- 虚拟环境：`/opt/guangjiyexing/.venv`。实际依赖版本记录在本地 `artifacts/new-server-deploy/requirements-resolved.txt`。
- 生产配置：`/opt/guangjiyexing/.env`，权限 `600`。
- 独立 SQLite：`/opt/guangjiyexing/backend/app.db`；迁移版本 `e941_system_password`。
- 上传目录：`/opt/guangjiyexing/uploads/members`。
- 服务：`guangjiyexing.service`，专用系统账号运行，仅监听 `127.0.0.1:8002`；已启用开机启动和失败重启。
- Nginx 扩展配置：`/www/server/panel/vhost/nginx/extension/guangjiyexing.hehkun.cn/application.conf`。
- 原站点配置与首页备份：`/opt/guangjiyexing/backups/pre-publish/`。
- 初始化数据库快照：`/opt/guangjiyexing/backups/initial-deployment.db`。

这是一套全新后台，没有迁移旧服务器会员和业务数据。微信、广告、短信、支付等第三方配置尚未录入；本次没有修改或重新发布 APK 的接口地址。

## 验证结果

- HTTPS 登录页与 61 个关联静态资源返回 200。
- 管理员实际登录成功；账号信息、会员、游戏、风控白名单接口返回 200。
- Chromium 浏览器完成登录并进入会员页面，无 JavaScript 页面异常。
- 健康检查返回 `{"status":"ok"}`，systemd 为 `active/enabled`，Nginx 配置检查通过。
- 宣传首页部署前后 SHA256 一致：`8e820fa002e1619e207aa002aebd4774237da6435d2d5bd7ea57f8aa784dc8dd`。
- 页面截图：`artifacts/new-server-deploy/admin-login.png`、`admin-members.png`。

## 日常维护

```sh
systemctl status guangjiyexing
journalctl -u guangjiyexing -n 100 --no-pager
systemctl restart guangjiyexing
nginx -t
```

撤销本次网站接入时，将上述 `application.conf` 移至备份目录，执行 `nginx -t && nginx -s reload`，再停止 `guangjiyexing.service`。原宣传站点仍使用原站点根目录。数据库快照为部署时备份，不是定时备份。
