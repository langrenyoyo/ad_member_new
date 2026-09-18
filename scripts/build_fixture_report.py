"""Build an offline visual evidence viewer from existing fixture captures."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'visual-baseline' / 'fixtures'
PAGES = [
    ('ads', '广告列表', '相同 3 条广告记录，折叠筛选；核对 20 个字段、五列双向排序、七类点击筛选和六格式导出。日历及选择器尺寸已对齐；分页和选择器另有局部对比，权限和完整统计语义仍待核验。'),
    ('ads-lookup-first', '广告游戏筛选：首屏', '相同 12 个选项，首屏 10 个；核对下拉内容、尺寸和位置。'),
    ('ads-lookup-last', '广告游戏筛选：末页', '同一组生成数据，键盘翻页显示剩余 2 项。'),
    ('ads-lookup-empty', '广告游戏筛选：空结果', '相同无匹配关键词，空结果弹层比较。'),
    ('ads-lookup-agent-first', '广告代理筛选：首屏', '相同 12 个选项；按参考取整规则校正右侧展开位置。'),
    ('ads-lookup-agent-last', '广告代理筛选：末页', '同一组生成数据，末页 2 项。'),
    ('ads-lookup-agent-empty', '广告代理筛选：空结果', '相同无匹配关键词；局部截图，真实可见权限范围另行核验。'),
    ('subsidies', '补贴列表', '相同 3 条补贴记录和图片，折叠筛选；核对四个单元格搜索请求。审核操作、权限与后台汇总语义仍未完整验证。'),
    ('member-lookup-agent-first', '代理商筛选：下拉首屏', '相同 12 个生成代理商，首屏 10 个；仅下拉层截图，不验证账号可见范围。'),
    ('member-lookup-agent-last', '代理商筛选：下拉末页', '键盘翻到第 2 页，核对剩余两个选项与分页栏。'),
    ('member-lookup-agent-empty', '代理商筛选：无匹配结果', '相同无匹配关键词，核对空结果面板。'),
    ('member-lookup-first', '游戏筛选：下拉首屏', '相同 12 个生成选项，首屏 10 个；仅裁剪下拉层，截图像素尺寸受小数坐标取整影响。'),
    ('member-lookup-last', '游戏筛选：下拉末页', '右方向键翻到第 2 页，剩余 2 个生成选项；验证分页内容与面板几何。'),
    ('member-lookup-empty', '游戏筛选：无匹配结果', '相同无匹配搜索词，仅比较空结果下拉层；不代表账号可见范围或服务端语义一致。'),
    ('member-rebind', '会员改绑关系', '相同模拟 ID 和三个关系字段；对标仅打开和填入模拟值，不提交保存，不验证关系联动业务规则。'),
    ('member-basic-bottom', '会员基础信息：底部', '统一模拟数据，滚动至底部；核对页签随内容滚动和固定确认栏，不等同于完整基础表单验收。'),
    ('member-time-time', '达标时间：时分秒', '固定同一日期时间，比较时间面板内部，不验证弹层定位。'),
    ('member-time-hours', '达标时间：小时选择', '固定同一日期时间，比较小时网格。'),
    ('member-time-minutes', '达标时间：分钟选择', '固定同一日期时间，比较分钟网格。'),
    ('member-time-seconds', '达标时间：秒选择', '固定同一日期时间，比较秒网格。'),
    ('member-date-picker', '会员达标时间日历', '固定 2026-09-17 12:34:56，仅比较日期弹层裁剪；不代表弹层在表单中的定位或全部时间面板已验收。'),
    ('member-basic', '会员基础信息', '相同模拟身份字段，空头像、空密码，基础页签顶部截图；完整滚动表单和附件选择尚未验收。'),
    ('member-agent', '会员代理设置', '同一套模拟代理开关和四项比例；仅比较代理页签与窗口，不验证服务端分佣规则。'),
    ('member-download', '会员下载设置', '相同模拟下载地址；仅比较下载页签与窗口，不验证链接内容和下载安装行为。'),
    ('member-lottery', '会员抽奖设置', '同一套模拟数据：12/7 次，倒计时 3.5～9 与 1.25～8.75。仅比较抽奖页签和弹窗，不向对标提交业务修改，不验证服务端抽奖规则。'),
    ('member-coin', '会员修改金币弹窗', '相同的可用金币 12.5、冻结金币 3，800×600 弹窗区域；对标仅打开和填入模拟值，未提交。'),
    ('member-calendar', '会员日期日历', '两端打开日历并设置同一段 2026 年 9 月日期范围；比较展开状态，未覆盖所有月份、快捷范围及屏幕尺寸。'),
    ('member-card', '会员卡片视图', '相同的 3 条会员记录，卡片模式；固定视口未展示全部下方记录。操作权限、筛选控件和工具栏仍有差异。'),
    ('dashboard', '仪表盘', '相同的 31 天趋势数据、新增与登录数量；仅比较内容区域。'),
    ('agent-dashboard', '主体统计', '相同主体名称、31 天注册数据及今日数量；仅比较内容区域，目标页面和业务统计规则另行验收。'),
    ('agents', '主体列表', '相同的 3 条记录：启用、禁用、上下级、中文长名称及特殊字符。权限按钮仍有差异。'),
    ('login', '登录页', '相同的空表单状态，1920×1080；未提交登录，不验证错误提示与认证规则。'),
    ('withdrawals', '提现列表', '相同的 3 条申请中、通过、失败记录；折叠筛选，包含金额边界值。操作权限、工具栏和列宽仍有差异。'),
    ('members', '会员列表', '相同的 3 条会员记录；区分实名认证姓名与支付宝姓名。列顺序已核对，工具栏、权限操作和筛选控件仍有差异。'),
]
sections = []
summary = []
overview = []
for key, title, scope in PAGES:
    folder = ROOT / key
    report = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
    if report.get('comparison_valid') is False:
        raise ValueError(f'Invalid comparison: {key}; recapture before publishing')
    for filename in ('reference.png', 'local.png', 'diff.png'):
        if not (folder / filename).is_file():
            raise FileNotFoundError(folder / filename)
    percent = report['changed_pixel_ratio'] * 100
    overview.append(f'<tr><td>{html.escape(title)}</td><td>{percent:.4f}%</td><td>{html.escape(scope)}</td></tr>')
    summary.append({'page': key, 'scope': scope, **report})
    data_link = f'<a href="{key}/data.json">模拟数据 JSON</a> · ' if (folder / 'data.json').exists() else ''
    sections.append(f'''<section><h2>{title}</h2><p>{scope}</p>
<p>差异像素占比：<strong>{percent:.4f}%</strong>；平均 RGB 差异：{report['mean_rgb']:.5f}</p>
<p>{data_link}<a href="{key}/report.json">原始指标</a></p>
<label>显示图片 <select data-page="{key}"><option value="reference">对标</option><option value="local">本地</option><option value="diff">差异图</option></select></label>
<a id="link-{key}" href="{key}/reference.png"><img id="image-{key}" src="{key}/reference.png" alt="{html.escape(title)}截图"></a></section>''')

export_checks = []
for key in ('member-export', 'member-hidden-export'):
    checks = json.loads((ROOT / key / 'comparison.json').read_text(encoding='utf-8'))
    export_checks.extend(checks)
export_summary = f'<p>已有会员导出证据：{sum(check.get("equal") is True for check in export_checks)} / {len(export_checks)} 组一致（普通列与隐藏列，六种格式，各含全部及所选记录）。仅代表这些模拟数据与导出场景。</p>'
overview_html = '<table><thead><tr><th>页面或状态</th><th>差异像素</th><th>比较范围</th></tr></thead><tbody>' + ''.join(overview) + '</tbody></table>'

document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>同数据对比报告</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{max-width:1200px;margin:32px auto;padding:0 20px;font:16px/1.7 system-ui;color:#243044;background:#f4f6f8}section{background:white;padding:24px;margin:24px 0;border:1px solid #d8dee5}img{display:block;width:100%;margin-top:16px;border:1px solid #ddd}select{font:inherit}a{color:#2455af}</style>
<h1>同数据对比报告</h1>
<p><a href="member-export/comparison.json">会员导出双端对比（六格式 × 全部/所选，共 12 组）</a> · <a href="member-export/data.json">导出模拟数据</a></p>
<p><a href="member-hidden-export/comparison.json">会员隐藏列导出对比</a> · <a href="member-hidden-export/data.json">隐藏列模拟数据（含零值和前导零账号）</a></p>
<p><a href="member-selection/comparison.json">会员跨页勾选与翻页后 25 条导出对比</a></p>
<p><a href="../reference-verified/member-coin-dialog/client-validation.json">金币表单前端校验观察（写请求已拦截，未验证对标服务端）</a></p>
<p><a href="../../../docs/launch-readiness.md">上线核查清单</a></p>
<p><a href="../../../docs/review-fixture-comparison.md">提现与补贴本轮范围和待办</a> · <a href="review-controls/report.json">标签、工具栏、选择器原始对照</a> · <a href="review-pagination/report.json">两页 16 种分页对照</a> · <a href="ads-pagination/comparison.json">广告 8 种分页对照</a></p>
<p><a href="review-controls/withdrawals-tools-reference.png">审核工具栏参考</a> · <a href="review-controls/withdrawals-tools-local.png">本地</a> · <a href="review-controls/withdrawals-tools-diff.png">差异</a> · <a href="review-pagination/withdrawals-10-reference.png">分页参考</a> · <a href="review-pagination/withdrawals-10-local.png">本地</a> · <a href="review-pagination/withdrawals-10-diff.png">差异</a></p>
<p>浏览器注入模拟数据，不写入业务数据库。以下为已有截图证据的汇总，非本次重新运行全套检查。</p>
<p>差异像素指任一 RGB 通道差值大于 10 的像素；占比使用整张截图面积，空白区域会稀释结果。该指标不能换算成功能完成率或全站还原率。</p>
<p><strong>当前不能判定全站一比一或可以上线。</strong>尚需覆盖其余页面、弹窗、交互状态、权限、业务统计规则与上线检查。</p>
''' + export_summary + overview_html + '\n'.join(sections) + '''<script>
document.querySelectorAll('select').forEach(el=>el.addEventListener('change',()=>{
 const path=el.dataset.page+'/'+el.value+'.png';
 document.getElementById('image-'+el.dataset.page).src=path;
 document.getElementById('link-'+el.dataset.page).href=path;
}));</script></html>'''
(ROOT / 'index.html').write_text(document, encoding='utf-8')
(ROOT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(ROOT / 'index.html')
