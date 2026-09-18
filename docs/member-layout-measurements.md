# 会员列表布局测量修正

2026-09-17，同一组三条会员数据，读取对标及本地 DOM 的 `getBoundingClientRect` 和 `getComputedStyle`：

- 对标表格无外边距；本地继承 Bootstrap `.table` 的 20px 下外边距，导致分页和面板底部下移。会员表格已清除此边距。
- 对标数据单元格为 14px 字号、20px 行高、8px/15px 内边距。本地原为 13px 字号及 12px/8px 内边距，已修正；表头字号和分隔线同步修正。
- 对标筛选标签为 14px 字号、22px 行高、顶部 7px 及左右 15px 内边距。本地标签原无内边距，已修正。
- 对标分页文字为 14px，本地原为 13px，已修正。

`compare_members_fixture.py` 重拍验证：差异像素占比 5.1731%，平均 RGB 差异 3.98059；修改前分别为 6.6367%、4.67041。默认表头顺序断言通过。`verify_member_cell_search.py`、`verify_member_columns.py`、`verify_member_pagination_boundary.py` 通过。

尚未解决操作列内容/权限、筛选中的游戏及代理商选择控件、工具栏卡片和导出功能等差异。宽表仍横向滚动；未将固定截图宽度作为全屏幕布局标准。本次结果不证明所有分辨率和状态视觉一致。
