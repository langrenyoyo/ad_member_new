# 游戏弹窗核验（2026-09-18）

当前目标仍未完成，本文只记录本轮实际修复及验证。

## 修复范围

- 游戏用户数据页签顺序恢复为抽奖、风控、提现、用户、登陆、每日活跃、统计。
- 提现申请时间和更新时间分别使用 `created_range`、`updated_range`，转换为各自的 UTC 查询参数。
- 游戏提现恢复金币汇总、上级/商品/内部号/作弊审查及默认隐藏列，金额列按参考控制器的十分之一换算为元。
- 恢复单笔同意、拒绝、有理由拒绝和批量同意/拒绝；失败保留选择，成功刷新，卡片切换保留选择，分页加载清空选择，关闭父弹窗取消未提交确认。
- 恢复五项金额、三项会员指标、金额与注册 ECharts 图表、图例及工具栏；统计重载隔离旧请求，关闭销毁图表。点击量缺失仍保留 null。
- 修复最大化按钮的损坏 HTML、登陆设备列名称和排序指示符。
- 窄屏金额卡片可换行；图表标题、图例和工具栏分行，避免重叠。
- 用户数据、游戏提现、教程专项默认使用当前 `3000` 服务；教程关闭检查等待原生 dialog 的异步 close 清理。

## 本轮验证

- `npm run check`：34 个 JavaScript 文件通过。
- `python -m unittest discover -s backend/tests -v`：57 项通过。
- `verify_all.py` 和 `audit_pages.py`：各 13 个主页面通过。
- `verify_game_userdata_browser.py`：七页签、日期、排序分页、隐藏列、卡片、六格式导出、图例和清理通过。
- `verify_game_withdrawals_browser.py`：单笔/批量审核、取消、理由校验、403 重试、金额、选择状态、更新时间和清理通过；写入均拦截到内存 fixture。
- `verify_game_statistics_layout.py`：1920、1024、390 像素宽度的容器溢出与 canvas 像素检查通过；桌面和手机截图已人工检查。
- `verify_filter_pages.py`：金币流水、白名单、风控历史的选择、搜索、提交、清空和离开清理通过。
- `verify_review_all.py`：提现/补贴 All 分批加载、总数变化、重复 ID、旧请求、失败重试和离开保护通过。

截图：`visual-baseline/verified/game-statistics-{1920,1024,390}.png`、`game-withdrawals-dialog.png`、`game-userdata-dialog.png`。这些是当前本地功能证据，不是全站像素一致证明。

## 未完成项

- 教程列表、详情、搜索及关闭交互通过，但原图片域名 `api.xmchujian.com` 的 9 张 PNG 无法加载；下载重试同样失败，完整教程测试仍失败。
- 游戏统计尚缺参考站地域地图/分布图、数据更新时间和完整连续日期口径。当前不能声称统计页一比一。
- 游戏会员页本轮追加核验见下文；行为弹窗筛选等仍需逐项审计，旧记录中的通过状态不能证明当前源码仍具备全部行为。
- 主提现/补贴页面的编辑、删除、拉黑、转账、审核权限展示及剩余整页视觉差异需要继续核验。
- 金币流水、白名单、风控历史尚需固定数据双端视觉对照。
- 真实支付未完成配置与端到端核验，审核通过不等于付款完成。

本地预览：`http://localhost:3000`，后端：`http://localhost:8000`。

## 游戏会员页追加修复

本轮重新检查当前源码，确认会员页三个开关、批量启停和金币表单缺失，已按保存的 `game-userdata-controller.js` 及 `member-behavior-forms.json` 恢复：

- 兑换、白名单、状态开关调用现有会员 PATCH；操作期间锁定，失败保留状态。
- 本页选择、全选、“更多”中的批量启用/禁用调用按游戏校验的现有批量接口；失败保留选择，成功刷新后清空，卡片切换保留选择。
- 修改金币打开时读取最新会员并校验游戏归属，支持重置、取消、有限数值校验、403 后保留输入重试；关闭父弹窗时清理子弹窗及读取请求。
- 恢复上级昵称、隐藏的上级账号、兑换、头像及最后登录字段，行为和金币按钮放入操作列。导出排除操作列，保留开关对应的文字值。
- 达标时间显示原始存储文字，筛选使用严格日期范围校验和包含两端的比较，不额外转换时区；支持现有达标时间排序。后端增加游戏隔离、日期边界、复合筛选和非法日期回归断言。
- 行为弹窗在没有父弹窗时也会随路由切换关闭，并取消未完成读取。

`verify_game_member_switches.py` 已切换到 `3000`，修正损坏的中文断言、地址页签选择器以及把“多 APP”错误期望为“单 APP”的断言。扩展验证达标时间、导出、父弹窗关闭、390px 卡片和金币表单布局；所有会员写入均拦截到内存 fixture。此测试、原用户数据/游戏提现专项、统计响应式专项、行为契约测试和 34 文件 JS 检查通过；57 项后端测试通过。

## 游戏会员视觉对照

新增 `compare_game_members_fixture.py`：登录参考站后阻止所有非 GET/HEAD 页面请求，两端使用三条相同的固定会员数据，无业务写入。截图及测量位于 `visual-baseline/fixtures/game-members/`。

- 按参考页实测恢复页签底色和间距、表格字体与内边距、行为按钮和状态标签颜色、开关图标及工具栏间距。
- 两端表格宽度均为 1476px；本地行高 61px，参考为 61.75px，尚有差异。
- 最后一次整张 1536×822 截图对照，通道差大于 10 的像素比例为 5.7541%，平均 RGB 差为 4.6045。该画布包含大量空白，比例不能当作整体完成度。
- 手机截图 `game-member-mobile.png` 和 `game-member-coins-mobile.png` 已检查，无容器横向溢出或文字重叠。

该次核验时尚未完成的编辑入口与分页，已在以下追加工作中补齐。清空金币的完整记账语义、权限对应的控件可见性及精确列宽仍有待核对；行为页各页签筛选和数据口径也未完成。金币修改复用现有会员余额更新接口，尚未证明其流水语义等同于参考站。

## 游戏会员编辑与分页追加核验

- 恢复操作列的铅笔编辑按钮，复用原会员编辑器的四个页签、图片上传、日期选择和仅提交修改字段的逻辑。打开时读取最新会员并核验游戏归属。
- 子编辑窗进入原生 dialog 顶层；最小化时移入父弹窗并解除自身的模态状态，恢复后重新进入顶层。最小化期间父页面可操作，草稿及当前页签保留。
- 关闭、Escape、父弹窗关闭和路由变化会取消未完成的读取、清理日期与上传状态，并把共享编辑器放回原位置。旧保存响应不能刷新已关闭的游戏窗口，也不能覆盖随后打开的普通会员编辑器。
- 按参考控制器恢复点击行选择、双击行编辑；按钮、开关、链接和表单控件不触发行选择。
- 修复 390px 编辑窗口页签文字裁切。桌面窗口仍为参考站的 800×600，手机端四个页签完整显示。
- 读取参考站实际运行配置，确认页容量为 `10/15/20/25/50/All`，支持首尾循环翻页及页码跳转；小数据集按参考规则隐藏不必要的页容量选项和单页导航。
- `All` 每批读取最多 200 条并保留游戏范围、筛选和排序。总数变化、空批次、重复 ID 或权限错误均保留上一份完整表格、页码与选择；切换请求或关闭窗口后，旧响应不再写入页面。
- 表头内边距、排序图标和行内按钮对齐方式按参考调整。固定数据对照中，两端行高现均为 61.75px，表宽均为 1476px。列宽与部分图标、文字对齐仍存在差异。

本次通过：

- `verify_game_member_editor.py`：行选择/双击编辑、游戏归属校验、四页签、窗口状态与焦点、图片上传、日期选择/重置、不修改直接保存、只提交修改字段、重复提交锁定、403 重试、旧读取/保存隔离、父弹窗与路由清理、手机布局。
- `verify_game_pagination.py`：450 条数据的分批全部加载、大小菜单、循环翻页、合法/非法跳转、筛选排序、四类批次失败、选择保留、旧响应隔离、总数缩小后回退、提现页复用、390px 布局与关闭清理。
- 原会员专项：`verify_member_edit_lifecycle.py`、`verify_member_edit_window.py`、`verify_member_edit_fields.py`、`verify_member_image_upload.py`、`verify_member_date_picker.py`、`verify_member_password_contract.py`、`verify_member_create_lifecycle.py`。
- 游戏专项：`verify_game_member_switches.py`、`verify_game_userdata_browser.py`、`verify_game_withdrawals_browser.py`、`verify_game_table_markup.py`。
- `npm run check`：34 个 JavaScript 文件通过。本次没有修改后端代码，未重复运行全部后端测试；前述 57 项是上一轮结果。

新专项的业务写入全部使用浏览器内存 fixture。更新旧测试的页容量选择器及排序标题断言，适配参考样式的菜单与装饰性排序图标。

最新固定数据截图对照在等待请求和字体加载、结束过渡动画后采集：差异像素比例为 3.0655%，平均 RGB 差为 2.1347。比较脚本同时保存参考分页运行配置及 DOM，位于 `visual-baseline/fixtures/game-members/measurements.json`。此指标仍只适用于这一张含大量空白的截图，不能作为全站完成度。

新增截图：`visual-baseline/verified/game-member-editor.png`、`game-member-editor-mobile.png`、`game-pagination-mobile.png`。

整体一比一目标仍未完成：除前述游戏会员差异外，统计地域/日期口径、行为筛选、主提现与补贴剩余操作、教程原图以及真实支付端到端验证仍需继续推进。

后续会员行为弹窗的单 APP 列/筛选、分页导出、精确风控范围、金币汇总、抽奖顶部设备/计数面板、设备封禁状态管理与 APP 详情窗口已追加实现并验证，详见 [会员行为弹窗核验](member-behavior-verification-2026-09-18.md)。该文同时记录实时设备数据接入、游戏端封禁执行、多 APP 关联和地址簿等未完成项。

## 游戏统计四图追加核验

已恢复五个金额卡片、金额统计、三个会员计数、中国地区地图、地区条形图及注册曲线的顺序和桌面布局。按参考 DOM 实测对齐卡片字号/行距、图标/颜色、白色背景、边框和图表网格。注册曲线使用参考绿色，金额图保留两条线、两个柱系列及极值/均值标记。

统计接口保留原有稀疏序列字段，新增北京时间当天及前 30 天的连续 `series_dates`、`metric_series` 和 `registration_series`。收入、金币与注册数缺日补零；没有采集证据的日活及点击量保留空值。新增地区账号数、累计金币、占游戏会员总数的比例与地区排序数组，来源仍为本地会员地址与累计金币字段。更新时间来自本游戏广告记录的最新 `updated_at`，没有记录时不显示更新日期。这些本地聚合规则有测试，尚未证明与参考后端口径相同。

地图资源按需加载，采用 `echarts-maps/echarts-countries-js` 的未修改资源，保留 ODbL 许可及页面署名。脚本网络失败、HTTP 成功但未注册地图时均可重试。离开统计页签、关闭窗口和路由变化会中止请求并释放四张图，迟到响应不能重新写回页面。窄弹窗按内容宽度改为两列金额卡片；窄地图默认不绘制拥挤的省名，通过点击/悬浮显示名称和数据。移动端适配不代表参考移动端像素已一致。

`compare_game_statistics_fixture.py` 对两边注入相同的九日趋势、五个金额值、三个计数和两个地区项；参考站登录后禁止业务写入。使用 1536×822 的参考内容画布与 1920×1080 本地窗口内等大的内容区，等待字体和动画完成。证据在 `visual-baseline/fixtures/game-statistics/`：

| 区域 | 差异像素占比（通道差大于 10） | 平均 RGB 差 |
|---|---:|---:|
| 首屏内容 | 1.8437% | 0.8663 |
| 金额图 | 0% | 0 |
| 地区条形图 | 0% | 0 |
| 注册曲线 | 0% | 0 |
| 地图 | 1.2260% | 1.2462 |

以上仅证明该组固定数据和桌面尺寸的画布结果，不是全站完成度，也不覆盖所有图表状态。参考站实际未注册 `macarons`，两边地图主题均回退为默认；无需引入另一个主题。参考地图与所用上游资源在台湾、内蒙古、黑龙江的边界坐标/编码偏移不同，另有 20 个省级标签中心位置不同，暂保留真实差异。参考 `mapdata` 包含 35 个地区项，本地只返回识别到的地址地区；未知地区未补成零。参考地域来源、点击量来源、收入更新时间及跨日口径仍需确认。

本轮验证：

- `python -m unittest discover -s backend/tests -v`：63 项通过，临时数据库；覆盖连续 31 天、北京时间边界、空值、地区统计及游戏隔离。
- `npm run check`：35 个 JavaScript 文件通过。
- `verify_game_statistics_layout.py`：1920/1024/390 截图、无容器溢出、金额单行、四图非空、地图实际着色像素、地区选择/取消/提示、数据视图、线柱切换/还原、PNG 下载及释放通过。
- `verify_game_statistics_lifecycle.py`：接口失败、地图网络失败、未注册地图的成功响应、重试、空数据、迟到响应、切换/关闭中止及路由清理通过。
- `verify_game_userdata_browser.py`、`verify_game_userdata_contract.py`、`verify_game_withdrawals_browser.py`、`verify_game_pagination.py`、`verify_member_behavior_multi.py`、`verify_behavior_contract.py` 通过。旧结构测试改用 3000 并等待四张画布完成，移除对废弃 CSS 类名的断言。

截图 `game-statistics-{1920,1024,390}.png` 和 `game-statistics-map-{1920,1024,390}.png` 位于 `visual-baseline/verified/`，已人工检查。测试业务写入使用内存 fixture，没有真实支付或参考站业务写入。全站一比一仍未完成。

## Game Statistics Map Asset Recheck (2026-09-18)

The local `public/vendor/china-map.js` now matches the read-only reference resource loaded from `assets/js/china.js?v=1.0.661`. SHA-256: `6e763608cb7a0e2fa571ebca3127f6d10940068853b5b404c234feb2f5be15e6`; size: 62860 bytes.

`compare_game_statistics_fixture.py` now reports identical map geometry and 0% changed pixels for the map, region bars, metrics, and registration charts. The responsive and lifecycle statistics verifiers still pass.
