# APP 下载文件

发布时将签名 APK 上传为 `yazhiyiji-latest.apk`，浏览器邀请页通过后台解析接口获取此下载地址。

APK 不纳入 Git；仅拉取代码不会更新下载包。也可使用后台环境变量 `APP_DOWNLOAD_URL` 指定 HTTPS 下载地址或站内 `/downloads/...` 地址。
