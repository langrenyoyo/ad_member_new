# 会员卡片视图

对标会员页注入相同三行测试数据后调用 Bootstrap Table 的 `toggleView`，读取卡片 DOM 并截图，证据位于 `visual-baseline/reference-verified/member-card`。对标将每行展开为字段名称/值，保留复选框、操作控件和显示列设置，隐藏表头。

本地工具栏新增“切换卡片视图”。切换通过原表格 DOM 的展示模式实现，不额外请求、不复制操作按钮、不丢失行选择。字段标签来自既有列定义；隐藏列、分页、搜索、编辑继续使用原有事件。视图选择在刷新/分页期间保留，空结果也能切换，离开会员页清理工具栏。

验证通过：`verify_member_card_view.py` 覆盖本地切换、名称与值、选择和编辑、隐藏列、分页/搜索保留视图、空结果及退出清理；`verify_member_toolbar.py`、`verify_member_columns.py` 通过。`node --check public/app.js` 通过。

`compare_member_card_fixture.py` 为卡片视图单独生成 reference/local/diff/data/report，已加入汇总报告。原默认列表对比保留。新增卡片标签后，原收款姓名断言调整为匹配值容器，避免将同名列标签误计为数据。

卡片截图仅覆盖固定 1690×1030 内容视口，其中第三行大部分位于截图外，不能据此证明全部卡片视觉一致。操作列权限、筛选选择器、导出工具及字段行距仍有差异。未验证窄屏全部状态，也未将卡片模式当作全站一比一完成证据。
