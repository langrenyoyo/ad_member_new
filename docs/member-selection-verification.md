# 会员行选择与跨页范围

2026-09-17 读取对标会员表格实际配置：`maintainSelected=false`、`clickToSelect=true`、`singleSelect=false`。配置留存在 `visual-baseline/reference-verified/member-selection/options.json`。

`compare_member_selection_fixture.py` 在双方列表接口注入 25 条记录，按实际 limit/offset 返回分页数据；逐端点击普通 Id 单元格选中/取消，勾选第一页记录后翻至第二页，再返回第一页。双方都不保留跨页勾选。此前将“跨页选择”列为待核验，不代表应实现跨页保留；本次已确认当前对标配置的真实行为。

本地新增普通单元格点击切换行选择，并同步全选/半选、单行编辑按钮、行选中标记和 aria-selected。交互控件自行处理事件，按钮、链接、输入和选择框不触发额外行切换。卡片字段标签与值仍可选择该行。

双端测试还验证翻页返回后导出全部 CSV，双方均包含 25 条，解析后的表头和字段值完全相等；证据位于 `visual-baseline/fixtures/member-selection`。`verify_member_card_view.py` 增加卡片单元格点击选择检查，通过；`verify_member_toolbar.py` 通过；JavaScript 语法检查通过。

以上覆盖当前登录账号及当前表格配置，不能推断其他权限账号或其他页面也不保留选择。业务写入权限、行操作表单及其余全站范围仍未完成一比一。
