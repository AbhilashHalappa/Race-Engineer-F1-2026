from __future__ import annotations

import json
from pathlib import Path

import src.track_geometry as track_geometry
from src.user_time import format_profile_timestamp
from src.performance_hub_ui import performance_hub_page_html


def test_profile_timestamp_can_render_india_time():
    value=format_profile_timestamp('2026-09-29T06:20:28','Asia/Kolkata')
    assert value.endswith('IST')
    assert value.startswith('2026-09-29 11:50:28')


def test_physical_turn_reader_uses_structured_track_maps(tmp_path, monkeypatch):
    monkeypatch.setattr(track_geometry, 'TRACK_MAPS', tmp_path)
    payload={
        'track_length_m': 1000.0,
        'turns': [
            {'corner_id':i,'label':f'T{i}','start_m':float(i*40),'apex_m':float(i*40+10),'end_m':float(i*40+20)}
            for i in range(1,15)
        ],
    }
    (tmp_path/'CATALUNYA.json').write_text(json.dumps(payload), encoding='utf-8')
    rows=track_geometry.persisted_physical_turns('Catalunya',1000.0)
    assert len(rows)==14
    assert rows[0]['corner_id']==1
    assert rows[-1]['corner_id']==14


def test_performance_hub_has_profile_timezone_icons_and_corner_authority_renderer():
    html=performance_hub_page_html()
    assert "timeZone:tz" in html
    assert "profileTimeZone=d.time_zone||'UTC'" in html
    assert 'function assistIcons' in html
    assert 'class=assistMini>${assistIcons(ass)}</td>' in html
    assert 'function effectiveCorners' in html
    assert 'effectiveCorners(g).map' in html
