"""Compare actual server-page selection behavior with 25 synthetic members."""
import json
import csv,io
from pathlib import Path
from urllib.parse import parse_qs,urlparse

def page_rows(route,rows):
    q=parse_qs(urlparse(route.request.url).query)
    start=int(q.get('offset',['0'])[0]);limit=int(q.get('limit',[str(len(rows))])[0])
    return rows[start:start+limit]

source=Path('compare_members_fixture.py').read_text(encoding='utf-8')
prefix=source[:source.index('    layout={}')].replace('fixtures/members','fixtures/member-selection')
prefix=prefix.replace('range(3)','range(25)').replace('vip=i,','vip=i%3,')
prefix=prefix.replace("{'total':3,'rows':reference}","{'total':25,'rows':page_rows(route,reference)}")
prefix=prefix.replace("{'total':3,'items':rows}","{'total':25,'items':page_rows(route,rows)}")
prefix=prefix.replace('total:rows.length,rows','total:25,rows').replace('}",reference)','}",reference[:10])')
prefix=prefix.replace("count()==3","count()==10")
tail='''    results={}
    for side,page,table,checkbox,next_button,previous in [('reference',ref,'#table','#table tbody input[type=checkbox]','.page-next a','.page-pre a'),('local',local,'#content .table','[data-select]','#nextPage','#prevPage')]:
        page.locator(table+' tbody tr').first.locator('td').nth(1).click()
        assert page.locator(checkbox+':checked').count()==1
        page.locator(table+' tbody tr').first.locator('td').nth(1).click()
        assert page.locator(checkbox+':checked').count()==0
        page.locator(checkbox).first.check()
        page.locator(next_button).click()
        page.wait_for_function("selector=>document.querySelector(selector).textContent.includes('9210')",arg=table)
        assert page.locator(checkbox+':checked').count()==0
        page.locator(previous).click()
        page.wait_for_function("selector=>document.querySelector(selector).textContent.includes('9200')",arg=table)
        assert page.locator(checkbox+':checked').count()==0
        results[side]={'row_click_toggles':True,'next_page_clears':True,'return_page_stays_clear':True}
    exported={}
    for side,page in [('reference',ref),('local',local)]:
        page.locator('.export>button' if side=='reference' else '.member-export summary').click()
        with page.expect_download() as event:
            page.locator('.export li[data-type="csv"]' if side=='reference' else '[data-member-export=csv]').click()
        content=Path(event.value.path()).read_text(encoding='utf-8-sig')
        (out/(side+'.csv')).write_text(content,encoding='utf-8')
        exported[side]=list(csv.reader(io.StringIO(content)))
        assert len(exported[side])==26
    assert exported['reference']==exported['local']
    results['export_after_page_return']={'equal':True,'rows':25}
    (out/'comparison.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(results)
    browser.close()
'''
exec(compile(prefix+tail,__file__,'exec'))
