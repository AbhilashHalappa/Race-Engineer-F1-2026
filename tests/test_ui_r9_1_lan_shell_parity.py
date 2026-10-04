from pathlib import Path


def test_lan_info_pages_hide_dash_rpm_strip_and_use_compact_shell():
    src = Path('src/dashboard_server.py').read_text(encoding='utf-8')
    assert "#stage.infoMode #rev{visibility:hidden}" in src
    assert "$('stage').classList.toggle('infoMode',page!=='dash')" in src
    assert "$('rev').style.visibility=page==='dash'?'visible':'hidden'" in src
    assert ".dashBack{width:30px;padding:0;font-size:0;text-align:center}" in src
    assert "#stage.infoMode #nav{top:13px;left:auto;right:18px" in src
    assert "#stage.infoMode .pageTitle{left:28px;top:53px;font-size:22px" in src
    assert "#stage.infoMode .pageTitle:before{content:'F1 DASH'" in src
    assert "#stage.infoMode #mapPage .mapWrap{left:28px;top:122px;width:744px;height:270px}" in src
