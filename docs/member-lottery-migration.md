# 会员抽奖字段升级修复

新增迁移 `e918_member_lottery_repair`，上游为 `e917_member_password_hashes`。历史 `e916` 有已经记录版本号但不含第二组抽奖字段的数据库，修改旧迁移文件不能修复这些数据库。因此本次采用新迁移，按实际列存在情况补齐 `raffle_num2`、`star_countdown2`、`over_countdown2`，不覆盖已有值，也不把第一组设置复制到第二组。

旧迁移允许下载地址 `down_load` 为 NULL，但当前模型要求字符串。新迁移将历史 NULL 规范为空字符串，并加上 NOT NULL 约束；已有下载链接保持原值。会员 PATCH 明确拒绝 `down_load: null`，整次请求不会保存其他修改。

验证使用临时 SQLite 数据库，没有升级业务数据库：

- `verify_member_lottery_migration.py` 覆盖缺少第二组字段的 e916、缺少第二组字段的 e917、字段完整的 e917。
- 每种形态验证已有字段和下载链接保留、历史 NULL 转换、约束、重复升级、降级再升级和 SQLite 完整性。
- `verify_member_payment_migration.py` 继续覆盖更早版本的身份、收款姓名、实名状态及密码字段迁移。
- `test_member_lottery_download_settings_roundtrip` 验证接口读写及无效下载值的原子拒绝。

降级到 e917 会放宽下载地址的非空约束，但保留第二组字段及数据，因为这些字段可能在修复前就已存在，不能安全地判定为本迁移独有。这不是历史结构的逐列回退。

部署时需按项目数据库升级流程执行 Alembic 到 head。上述证据只覆盖 SQLite；其他数据库引擎及正式环境的升级尚未验收。
