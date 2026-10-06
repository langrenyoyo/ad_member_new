# APP JSON 请求日志

所有 `/api/app/v1/` 请求默认记录一条 `app_json_request` 日志，输出到 stderr；现有服务器由 systemd journal 收集，不写入业务数据库。`APP_JSON_AUDIT_ENABLED=0` 可关闭，修改后重启服务生效。

日志包含 UTC 时间、HTTP 方法、路径、响应状态、耗时、实际读取字节数、读取完整性和 `audit_id`。响应头 `X-App-Audit-Id` 可供 APP 上报排障，与业务响应 JSON 中的 `request_id` 是两个不同标识。认证头、Cookie、URL 查询参数及响应体不记录。

`body` 是解析后的原始 JSON 字段快照，包含额外字段，经过递归脱敏；不保留原始空格、重复 JSON 键或字节顺序。密码、Token、secret、authorization、私钥、签名、微信 code、收款账号/姓名/联系方式及 TAKU extra_data 等字段替换为 `[REDACTED]`。设备 ID、游戏 ID、client_request_id、event_id 和广告类型等调试字段保留。自定义字段不要传入无关个人资料。

| body_state | 含义 |
|---|---|
| json_redacted | 完整且有效的 JSON，脱敏后存于 body |
| oversize_omitted | 大于 32 KB，不保存内容，避免部分截断泄露敏感值 |
| invalid_json_omitted | 无效 JSON，不记录可能包含明文凭据的片段 |
| not_fully_consumed | 下游未读完整个请求体，仅记录已读字节数，不主动读取剩余数据 |
| non_json_omitted | 非 JSON，如图片上传，不保存二进制内容 |

完整读取的 JSON 请求另有 `body_sha256` 用于核对字节一致性。失败请求在下游消费请求体时同样可记录，包括参数校验 422；日志写入异常不会改变业务结果。关闭日志时不添加 audit 响应头。

服务器查看最近日志：

```bash
journalctl -u ad-member-new.service --since '10 minutes ago' --no-pager -o cat | grep '"event":"app_json_request"'
```

按响应头中的 audit_id 查找：

```bash
journalctl -u ad-member-new.service --since today --no-pager -o cat | grep -F '<audit_id>'
```

日志保留与磁盘限额由服务器 journald 配置管理。此功能启用前的历史请求体无法补录。只能看到 APP 发到本后端的数据，不能看到 APP 在本地传给 TAKU SDK 的参数，也不代表广告已发奖。
