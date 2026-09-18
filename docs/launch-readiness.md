# 上线 readiness 核查（2026-09-17）

| 项目 | 证据 | 结论 |
|---|---|---|
| 后端回归 | `python -m unittest discover -s backend/tests -v`，80 项通过（2026-09-18） | 通过 |
| 会员编辑资料、页签、生命周期 | `verify_member_edit_fields.py`、`verify_member_edit_lifecycle.py` | 通过（覆盖范围内） |
| 迁移链 | `verify_member_payment_migration.py`、`verify_member_lottery_migration.py`；会员相关 head 至 `e919_member_otherlevel` | 通过（临时数据库） |
| 密码安全 | `verify_member_password_contract.py` 及后端密码测试 | 哈希与响应脱敏通过 |
| 双端视觉/数据 | `visual-baseline/fixtures/index.html` 及导出对比 | 仅模拟场景通过，非全站结论 |
| 主体列表与 OSS（2026-09-18） | `docs/agent-list-parity-verification.md`；默认差异 0.0189%、OSS 0.1429%，七列宽一致，76 项后端及浏览器专项通过 | 覆盖范围内通过；完整权限映射、编辑表单与真实 OSS 对接仍待证明 |
| 主体数据分析（2026-09-18） | `docs/agent-analysis-parity-verification.md`；真实本地接口、六图、会员表、配置保存及 77 项后端/迁移/浏览器通过 | 覆盖范围内通过；跨 APP 身份、分桶及失败奖励统计口径仍需参考证据 |
| 会员筛选选择器 | `verify_member_lookups.py`、`test_member_filter_options_paging_scope_and_literal_search` | 覆盖范围内通过，真实权限范围待核验 |
| 真实支付 | `docs/payment-parity-gap.md` | 未通过：没有支付渠道、异步结果、幂等和补偿 |
| 支付适配器边界 | `verify_payment_provider_contract.py` | 通过：未配置或 sandbox 均不会报告已付款 |
| 生产启动保护 | `verify_production_guards.py` | 通过：未配置或测试支付渠道时拒绝 production 启动 |
| 对象存储上传 | `verify_member_image_upload.py`、`test_member_image_upload_persists_normalized_png`；本地文件存储已实现，生产共享存储尚未配置 | 未通过生产上线 |
| 会员认证与支付密码校验 | 仅后台写入哈希，未提供会员端认证流程 | 未通过 |
| 设备风控真实名单（2026-09-18） | `docs/device-risk-parity-verification.md`；移除风险日志冒充会员的错配后，接口明确 503，路由审计 12/13 | 未通过：需确认会员入选规则并接通数据源，模拟界面验收不能替代 |
| 提现编辑（2026-09-18） | `verify_withdrawal_crud_browser.py`、后端提现 CRUD 测试；详情读取、申请中编辑、差异提交、失败保留、已处理保护通过 | 覆盖范围内通过；参考无有效样本，字段级视觉/写入约束未证明 |
| 个人资料（2026-09-18） | `docs/profile-parity-verification.md`；头像、资料、日志专项和 73 项后端/35 个 JS 检查通过 | 覆盖范围内通过；参考写入规则、头像共享存储待核实 |
| 现有开发库迁移一致性（2026-09-18） | 新头像迁移完整链在临时库通过；现有库旧 `c7b8f9a2d1e4` 迁移重复 `ad_group` 失败 | 未通过：开发补列不等同正式升级，未重置或强行 stamp |
| 教程正文图片（2026-09-18） | 两篇目录/正文与参考新数据一致，列表/窗口/导出已有专项；九张原图源 HTTPS 超时，HTTP 和参考站同路径 404 | 未通过图片完整性：需可读取的原图目录或备用地址，未生成替代图片 |

当前状态：不满足正式上线门槛。模拟数据对比和局部回归证明了已覆盖范围内的行为，但不能替代支付渠道联调、生产数据库迁移演练、对象存储配置、认证安全评审和全页面验收。
