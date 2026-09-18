# 支付及提现确认流程核查

当前真实支付未实现。活动后端 `backend/app/main.py` 导入 `main_from_txt.py`；`backend/app/payment.py` 尚无可用渠道实现。

## 已修复：提前标记转账

此前批量实时、批量计划、单笔转账及编辑 `plan_status=1` 都能直接更新本地状态，甚至在返回 `payment_confirmed=false` 时仍写入操作人和时间。现在这些入口先校验记录及转账前置状态，再检查支付集成；当前返回 HTTP 503，提示“支付渠道尚未接通，未执行转账，提现记录保持原状态”。

任意 `PAYMENT_PROVIDER` 字符串不会让占位实现成为可用渠道。生产启动检查也按实现可用性判断，当前没有真实渠道，因此不具备生产启动条件。

`test_unconfigured_payment_all_entrypoints_preserve_records` 在隔离数据库中验证四个入口、重复请求、重复 ID、非法批次、权限和失败回滚；失败后记录与请求前完全一致，没有执行真实支付。

## 待完成：真实支付全流程

仍需渠道请求、业务单号与幂等、逐笔结果、超时对账、异步回调、结果落库、计划调度和失败补偿。不能仅把 `available` 改成 true 就上线：必须同步替换原先的直接状态更新路径，以渠道确认结果驱动状态转换。渠道异常、部分成功及并发重试还没有集成验收证据。

## 黑名单统计口径

对标 `is_true` 表示“内部号”，不是黑名单依据，证据见 `visual-baseline/reference-verified/member-edit-controls.json`。此前按内部号计算的黑名单待提现金额已移除。

接口返回 `summary.blacklisted: null` 及 `summary_unavailable.blacklisted: "blacklist_source_unverified"`，调用方须按未知值处理，不能转换成零。真实黑名单来源、状态和统计规则仍待核实接入。隔离数据库回归已验证切换内部号标志不改变统计口径。

## 前端范围验证

`verify_withdrawal_confirmation_scope.py` 覆盖导航取消、状态对象替换后拒绝旧提交和当前页面正常提交。`verify_review_regressions.py` 覆盖审核请求、原因校验及过期响应处理。这些浏览器模拟测试不代表真实支付或全站一比一验收。
