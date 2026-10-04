import json
from pathlib import Path

from src.measured_performance import Sample
from src.rival_benchmark import TimeTrialRivalCapture
from src.race_state_receiver import RaceStateReceiver


def sample(d,t,speed,gear=8,yaw=0.0):
    return Sample(d=d,t=t,speed=speed,throttle=1.0,brake=0.0,steering=0.0,gear=gear,rpm=11000,g_lat=0.0,g_long=0.0,slip=None)


def test_rival_sanity_filters_multi_bin_speed_spike_and_gear_glitch():
    cap=TimeTrialRivalCapture(enabled=True)
    cap.track.current_lap=2
    rows=[
        sample(0,0.00,300,8), sample(5,0.05,302,8),
        sample(10,0.10,486,6), sample(15,0.15,486,8), sample(20,0.20,470,5),
        sample(25,0.25,304,8), sample(30,0.30,305,8),
    ]
    for r in rows:
        cap.extra_samples[(2,r.d)]={"yaw":0.0}
    clean=cap._clean_numeric_trace(rows)
    assert max(x.speed for x in clean) < 380
    assert [x.gear for x in clean][2:5] == [8,8,8]


def test_rival_kinematic_g_is_derived_when_ea_ghost_g_is_zero():
    cap=TimeTrialRivalCapture(enabled=True)
    cap.track.current_lap=1
    rows=[sample(0,0.0,200), sample(5,0.1,195), sample(10,0.2,190)]
    for i,r in enumerate(rows):
        cap.extra_samples[(1,r.d)]={"yaw":i*0.015}
    out=cap._derive_kinematic_g(rows)
    assert out[1].g_long < 0
    assert abs(out[1].g_lat) > 0


def test_reference_selector_scans_and_switches_stored_reference(tmp_path):
    receiver=RaceStateReceiver(tts_enabled=False, wheel_telemetry=False)
    receiver.reference_directory=tmp_path
    payload={
        "format":"RACE_ENGINEER_REFERENCE_LAP","version":"1.0",
        "metadata":{"driver":"Fast Rival","source":"EA_F1_TIME_TRIAL_RIVAL"},
        "lap":{"lap":1,"valid":True,"sample_count":20,"lap_time_s":77.338,"sections":[],"_samples":{
            str(float(i*5)):{"d":float(i*5),"t":i*0.05,"speed":300.0+i*0.1,"throttle":1.0,"brake":0.0,"steering":0.0,"gear":8,"rpm":11000+i}
            for i in range(20)
        }}
    }
    p=tmp_path/'melbourne_fast.json'; p.write_text(json.dumps(payload),encoding='utf-8')
    opts=receiver.reference_lap_options()
    assert len(opts)==1 and '1:17.338' in opts[0]['label']
    ok,msg=receiver.select_reference_lap(str(p))
    assert ok and 'Fast Rival' in msg
    assert receiver.current_reference_selection()==str(p)
    ok,msg=receiver.select_reference_lap('__AUTO__')
    assert ok and receiver.current_reference_selection()=='__SESSION_BEST__'


def test_control_center_has_reference_selector_and_current_banner():
    window=Path('src/overlay/window.py').read_text(encoding='utf-8')
    main=Path('src/main.py').read_text(encoding='utf-8')
    assert 'REFERENCE LAP' in window
    assert 'refresh_reference_options' in window
    assert 'select_reference_lap' in window
    assert 'V0.9.17.2.5 REFERENCE AUTHORITY + TRACK SYNC' in main
