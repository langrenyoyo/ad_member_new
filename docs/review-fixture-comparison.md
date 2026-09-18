# 提现与补贴对照（2026-09-18）

目标仍未完成整页、全功能及数据口径验收。本轮使用浏览器拦截的固定记录，不写业务数据库；参考页业务写入在控件和分页对照脚本中被拦截。

## 已核对范围

| 区域 | 证据 | 当前结果 |
|---|---|---|
| 状态标签、右侧列表/列设置/导出/搜索按钮 | `compare_review_controls.py` | 两页六个局部截图差异像素 0 |
| 三条记录的分页文字 | 同上 | 两页局部截图差异像素 0 |
| 205 条记录的八个页码窗口 | `compare_review_pagination.py` | 两页共 16 个截图平均 RGB 差异与差异像素占比均为 0 |
| 游戏/代理选择器 | `compare_review_controls.py` | 四个首屏下拉图差异约 0.0069% 至 0.1804%；边缘小数像素裁剪受底层内容影响，未宣称零差异 |
| 提现整页内容区 | `compare_withdrawals_fixture.py` | 三条固定记录，差异像素 3.7939% |
| 补贴整页内容区 | `SUBSIDY_COMPARE_CAPTURE=1 python compare_subsidies_fixture.py` | 三条固定记录与图片，差异像素 3.2656% |

原始图片、DOM 测量和 JSON 报告位于 `visual-baseline/fixtures/review-controls/`、`review-pagination/`、`withdrawals/`、`subsidies/`。局部零差异只对记录的状态和视口成立，不能换算成全站完成率。

## 功能验证

提现和补贴游戏/代理筛选使用认证的 SelectPage 查询，每页 10 项，不再预先读取前 200 条游戏和主体。支持文本搜索、键盘翻页、ID 回填、清空、重置和主体范围锁定；迟到的旧 ID 成功或失败响应不覆盖当前选择，离开页面清理请求和弹层。

分页支持 10/15/20/25/50/All、首尾循环、参考页码窗口、按钮或回车跳转，以及页大小记忆。All 按最多 200 条分批获取，保持筛选和排序；检测总数改变、空批次、重复 ID，显示可重试错误并保留上次完整结果。旧筛选响应或页面离开后的响应不能更新当前界面。

通过的主要命令：

- `python verify_review_lookups.py`
- `python verify_review_all.py`
- `python verify_review_export.py`
- `python verify_review_regressions.py`
- `python verify_review_filters.py`
- `python verify_review_dates.py`
- `python verify_review_layout.py`
- `python verify_agent_navigation_scope.py`
- `python verify_review_responsive.py`

1920、1024、390 宽度的控件边界已检查，手机截图在侧栏过渡结束后捕获。截图位于 `visual-baseline/verified/`；未据此宣称移动端与参考站一致。

## 发现并修复的共享回归

金币流水、白名单、风控历史调用已不存在的 `adsOptions()`，导致三页渲染错误。已迁移到同一认证分页选择器，`verify_filter_pages.py` 在隔离响应下验证三页 205 项搜索、分页、清空和重置。另修复 SelectPage 翻到第二页后输入新关键词仍查询旧页码的问题。

旧 `verify_all.py` 只打印错误状态，退出码仍为 0；旧 `audit_pages.py` 未检查已渲染的错误块。因此旧检查不能作为这三个页面的成功加载证据。两份脚本现已等待加载结束并断言错误块/提示为空，13 个主路由重新通过。后端没有修改，本轮未重复运行后端测试。

## 仍待完成

参考提现页的编辑、拉黑、黑名单、转账和汇总入口已分别接入；本地新增申请中记录的工具栏/行内编辑与详情读取，提交只包含变化字段，已处理记录拒绝编辑并写审计。补贴页编辑/删除已接入。由于参考当前无有效提现样本，提现编辑表单完整结构和字段级像素仍无法核对；权限映射、审核状态与真实支付语义还需核对，分页和公共控件完成不代表这些流程已实现一比一。
