"""Reuse identical list fixtures to capture both sides in card view."""
from pathlib import Path

source=Path('compare_members_fixture.py').read_text(encoding='utf-8')
source=source.replace("fixtures/members","fixtures/member-card")
source=source.replace("    ref.evaluate('document.fonts.ready');", "    ref.evaluate(\"jQuery('#table').bootstrapTable('toggleView')\")\n    ref.evaluate('document.fonts.ready');")
source=source.replace("    local.evaluate('document.fonts.ready');", "    local.locator('#memberViewToggle').click()\n    local.evaluate('document.fonts.ready');")
source=source.replace("    assert layout['local']['headers']==layout['reference']['headers']", "    assert local.locator('.member-card-table').count()==1\n    assert local.locator('thead').is_hidden()\n    assert local.locator('td[data-field=receive_name] .member-card-label:visible').count()==3")
source=source.replace('member list with 3 identical browser fixtures', 'member card view with 3 identical browser fixtures, fixed viewport clips lower rows')
exec(compile(source,__file__,'exec'))
