from types import SimpleNamespace as NS

from src.rival_benchmark import TimeTrialRivalCapture
from src.reference_lap import validate_reference_lap


def pkt(pid, body, uid=777):
    return NS(header=NS(m_packetId=pid, m_sessionUID=uid, m_playerCarIndex=0), body=body)


def laprow(lap=1, d=0.0, t_ms=0, last_ms=0, invalid=0):
    return NS(m_currentLapNum=lap, m_lapDistance=d, m_currentLapTimeInMS=t_ms,
              m_lastLapTimeInMS=last_ms, m_currentLapInvalid=invalid)


def tel(speed=250, throttle=1.0, brake=0.0, steer=0.0, gear=7, rpm=12000):
    return NS(m_speed=speed, m_throttle=throttle, m_brake=brake, m_steer=steer,
              m_gear=gear, m_engineRPM=rpm, m_drs=1, m_clutch=0,
              m_revLightsPercent=80, m_brakesTemperature=(600, 600, 500, 500),
              m_tyresSurfaceTemperature=(95, 95, 90, 90),
              m_tyresInnerTemperature=(90, 90, 88, 88),
              m_tyresPressure=(23.0, 23.0, 21.0, 21.0), m_surfaceType=(0, 0, 0, 0))


def motion(x=0.0):
    return NS(m_gForceLateral=0.5, m_gForceLongitudinal=-0.8,
              m_worldPositionX=x, m_worldPositionY=0.0, m_worldPositionZ=1.0,
              m_worldVelocityX=40.0, m_worldVelocityY=0.0, m_worldVelocityZ=0.0,
              m_yaw=0.1, m_pitch=0.0, m_roll=0.0)


def arr(factory, n=24):
    return tuple(factory(i) for i in range(n))


def dataset(idx=2, lap_ms=80250, valid=1):
    return NS(m_carIdx=idx, m_teamId=7, m_lapTimeInMS=lap_ms,
              m_sector1TimeInMS=25000, m_sector2TimeInMS=28000, m_sector3TimeInMS=27250,
              m_tractionControl=0, m_gearboxAssist=1, m_antiLockBrakes=0,
              m_equalCarPerformance=1, m_customSetup=1, m_valid=valid)


def test_selected_tt_rival_builds_reference_and_uses_dataset_time(tmp_path):
    c = TimeTrialRivalCapture(enabled=True)
    c.observe(pkt(1, NS(m_trackId=0, m_trackLength=150.0, m_sessionType=12, m_formula=0,
                        m_equalCarPerformance=1, m_weather=0, m_trackTemperature=31, m_airTemperature=22)))
    parts = tuple(NS(m_name='FAST RIVAL' if i == 2 else 'X', m_driverId=9, m_teamId=7, m_raceNumber=4) for i in range(24))
    c.observe(pkt(4, NS(m_numActiveCars=3, m_participants=parts)))
    ds = dataset()
    c.observe(pkt(14, NS(m_rivalDataSet=ds))
    )
    c.observe(pkt(0, NS(m_carMotionData=arr(lambda i: motion(float(i))))))

    # Capture one complete ghost traversal at 5 m spacing.
    for j in range(30):
        d = j * 5.0
        rows = arr(lambda i: laprow(1, d if i == 2 else 0.0, j * 100 if i == 2 else 0))
        c.observe(pkt(2, NS(m_lapData=rows, m_timeTrialRivalCarIdx=2)))
        tels = arr(lambda i: tel(speed=260-j, throttle=.25 if 8 <= j <= 13 and i == 2 else 1.0,
                                 brake=.9 if 8 <= j <= 13 and i == 2 else 0.0,
                                 steer=.2 if i == 2 else 0.0))
        c.observe(pkt(6, NS(m_carTelemetryData=tels)))

    # Ghost wraps to start. Dataset lap time is authoritative.
    rows = arr(lambda i: laprow(1, 1.0 if i == 2 else 0.0, 50 if i == 2 else 0, 0))
    result = c.observe(pkt(2, NS(m_lapData=rows, m_timeTrialRivalCarIdx=2)))
    assert result is not None
    lap, meta = result
    assert lap['lap_time_s'] == 80.25
    assert lap['sample_count'] >= 20
    assert meta['source'] == 'EA_F1_TIME_TRIAL_RIVAL'
    assert meta['driver'] == 'FAST RIVAL'
    assert meta['car_index'] == 2
    assert meta['rival_selected'] is True
    assert meta['anti_lock_brakes'] == 0
    assert meta['traction_control'] == 0
    assert meta['sector1_time_s'] == 25.0
    assert any('world_x' in row for row in lap['_samples'].values())
    validate_reference_lap(lap)

    out = tmp_path / 'rival.json'
    c.save_best(out)
    assert out.exists()


def test_rival_index_comes_from_lap_packet_even_without_participant_name():
    c = TimeTrialRivalCapture(enabled=True)
    rows = arr(lambda i: laprow(1, 10.0 if i == 5 else 0.0, 100))
    c.observe(pkt(2, NS(m_lapData=rows, m_timeTrialRivalCarIdx=5)))
    assert c.rival_idx == 5


def test_invalid_rival_dataset_is_not_promoted():
    c = TimeTrialRivalCapture(enabled=True)
    c.session_meta['track_length_m'] = 150.0
    c.observe(pkt(14, NS(m_rivalDataSet=dataset(valid=0))))
    c.latest_lap = NS(m_lapData=arr(lambda i: laprow(1, 0.0, 0)))
    for j in range(25):
        c.latest_lap = NS(m_lapData=arr(lambda i: laprow(1, j*5.0 if i == 2 else 0.0, j*100)))
        c.observe(pkt(6, NS(m_carTelemetryData=arr(lambda i: tel()))))
    assert c._finish(1, 80000) is None
