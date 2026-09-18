"""Compare open member calendars with the same explicit date range."""
from pathlib import Path

source=Path('compare_members_fixture.py').read_text(encoding='utf-8')
source=source.replace('fixtures/members','fixtures/member-calendar')
source=source.replace("local.locator('tbody')", "local.locator('#content .table tbody')")
picker_script="""selector=>{const p=jQuery(selector).data('daterangepicker');p.setStartDate('2026-09-10 00:00:00');p.setEndDate('2026-09-16 23:59:59');p.show();p.updateView();p.updateCalendars();return {styles:['.calendar-table td','.calendar-table th','.ranges li','.calendar-table','.calendar', '.daterangepicker'].map(selector=>{const e=selector==='.daterangepicker'?p.container[0]:p.container[0].querySelector(selector);if(!e)return {selector};const c=getComputedStyle(e);return {selector,font:c.font,padding:c.padding,border:c.border,margin:c.margin,color:c.color,rect:e.getBoundingClientRect().toJSON()}}),locale:p.locale,start:p.startDate.format('YYYY-MM-DD HH:mm:ss'),end:p.endDate.format('YYYY-MM-DD HH:mm:ss')}}"""
reference="""    ref.locator('input[name=create_time]').click()
    ref.locator('.daterangepicker:visible').wait_for()
    reference_calendar=ref.evaluate(picker_script,'input[name=create_time]')
    ref.evaluate('document.fonts.ready');"""
local="""    local.locator('[data-mf=create_time]').click()
    local.locator('.daterangepicker:visible').wait_for()
    local_calendar=local.evaluate(picker_script,'[data-mf=create_time]')
    (out/'calendar.json').write_text(json.dumps({'reference':reference_calendar,'local':local_calendar},ensure_ascii=False,indent=2),encoding='utf-8')
    assert reference_calendar['start']==local_calendar['start'] and reference_calendar['end']==local_calendar['end']
    assert reference_calendar['locale']==local_calendar['locale']
    local.evaluate('document.fonts.ready');"""
source=source.replace("    ref.evaluate('document.fonts.ready');",reference)
source=source.replace("    local.evaluate('document.fonts.ready');",local)
source=source.replace('member list with 3 identical browser fixtures','member calendar open with identical explicit September 2026 range and 3 rows')
exec(compile(source,__file__,'exec'))
