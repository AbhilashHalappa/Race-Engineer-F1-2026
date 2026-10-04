from src.performance_hub_ui import performance_hub_page_html


def test_reactive_review_reload_has_busy_helper_and_change_handlers():
    html = performance_hub_page_html()
    assert "function setReviewBusy(busy)" in html
    assert "$('reviewRef').addEventListener('change',()=>scheduleReviewReload('ref'))" in html
    assert "$('reviewLap').addEventListener('change',()=>scheduleReviewReload('lap'))" in html
    assert "await loadReview()" in html
    assert "setReviewBusy(true)" in html
    assert "setReviewBusy(false)" in html


def test_track_change_clears_stale_session_review_before_fetch():
    html = performance_hub_page_html()
    assert "function clearReviewContext" in html
    assert "if(changed)clearReviewContext({hide:true})" in html
    assert "currentReviewId=null" in html
    assert "reviewData=null" in html
    assert "review.classList.remove('open')" in html
    assert "Select a session from the selected track." in html


def test_track_fetch_is_guarded_against_out_of_order_responses():
    html = performance_hub_page_html()
    assert "let trackRequestSeq=0,trackAbort=null" in html
    assert "if(trackAbort)trackAbort.abort()" in html
    assert "if(seq!==trackRequestSeq||String(currentTrack)!==target)return" in html
