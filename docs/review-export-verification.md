# 提现和补贴导出复验

商品名称含中文、`&` 和 `<商品>` 时，旧 XML 输出未经转义，实际下载文件无法解析。现统一使用 XMLSerializer 生成 XML，保留原字段和行结构。离开页面后，未完成的导出不会继续下载旧页面数据。

验证结果：

- `verify_review_export.py`：205 条记录全量 CSV、选择记录的六种格式、金额显示、隐藏列与操作列排除、补贴选择记录导出、特殊字符 XML 解析和离页停止下载。
- `verify_agent_navigation_scope.py`：主体 9000 的 25 条提现全量 CSV 保留主体条件，选择一条导出 XML 不再请求全量数据，商品名称特殊字符往返一致。
- `verify_agents_export_formats.py`：原有主体列表六种格式导出回归通过。

可查看模拟数据产物：`visual-baseline/fixtures/withdrawals-export/export.csv`、`selected.xml` 和 `report.json`。没有写入业务数据库。本轮证明本地文件有效性和范围传递，尚未完成对标站相同数据六种格式的直接比较。
