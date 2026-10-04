from src.performance_hub_ui import performance_hub_page_html


def test_r6_uses_linked_multichannel_workstation_inside_existing_telemetry_tab():
    html = performance_hub_page_html()
    assert 'id=tab-telemetry' in html
    assert 'LINKED TELEMETRY WORKSTATION' in html
    assert 'id=telemetryCharts' in html
    assert 'class=linkedChartGrid' in html
    # R6 must not reintroduce the rejected top-level workspace navigation.
    assert 'TRACK OVERVIEW</button>' not in html
    assert 'SESSION REVIEW</button>' not in html


def test_r6_core_and_advanced_channels_are_data_gated():
    html = performance_hub_page_html()
    for key in ('speed_kph', 'brake', 'throttle', 'steering', 'gear', 'ers', 'delta_s'):
        assert f"{key}:" in html
    for key in ('rpm', 'lateral_acceleration', 'longitudinal_acceleration', 'tyre_temperatures', 'tyre_pressures', 'brake_temperatures'):
        assert f"{key}:" in html
    assert 'Advanced channels appear automatically when they exist in the stored telemetry.' in html
    assert 'function channelAvailable(key)' in html


def test_r6_links_cursor_corner_zoom_range_and_map():
    html = performance_hub_page_html()
    assert 'function setTelemetryCursor(d)' in html
    assert 'function updateMapCursor(d)' in html
    assert 'id=mapCursorMarker' in html
    assert 'function renderTelemetryCornerButtons()' in html
    assert "zoomRange=[Math.min(a,d),Math.max(a,d)]" in html
    assert 'Click a corner to zoom every chart.' in html
    assert 'shared cursor' in html


def test_r6_supports_full_lap_density_reorder_and_persistent_ui_preferences():
    html = performance_hub_page_html()
    assert 'id=resetZoom' in html
    assert 'id=graphDensity' in html
    assert 'function cycleGraphDensity()' in html
    assert 'function moveTelemetryChannel(key,dir)' in html
    assert "race.telemetry.order" in html
    assert "race.telemetry.hidden" in html
    assert "race.telemetry.chartMode" in html


def test_r6_legend_names_selected_lap_and_reference():
    html = performance_hub_page_html()
    assert 'id=telemetryDriverLegend' in html
    assert 'id=telemetryReferenceLegend' in html
    assert "reviewData?.visual_reference?.label||'Reference'" in html


def test_r6_track_map_expands_to_use_available_workstation_space():
    html = performance_hub_page_html()
    assert 'min-height:clamp(520px,68vh,760px)' in html
    assert 'min-height:clamp(400px,54vh,650px)' in html
    # The SVG viewBox now follows the physical track aspect ratio rather than
    # forcing the old wide 700x350 canvas that made tall circuits appear tiny.
    assert 'ry=Math.max(1,mxy-mny)' in html
    assert 'H=Math.max(430,Math.min(760,Math.round(W*(ry/rx))))' in html
