from types import SimpleNamespace as NS

from src.ai_benchmark import AIBenchmarkCapture
from src.reference_lap import validate_reference_lap


def pkt(pid, body, uid=123):
    return NS(header=NS(m_packetId=pid, m_sessionUID=uid, m_playerCarIndex=0), body=body)


def laprow(lap=1, d=0.0, t_ms=0, last_ms=0, invalid=0):
    return NS(m_currentLapNum=lap, m_lapDistance=d, m_currentLapTimeInMS=t_ms,
              m_lastLapTimeInMS=last_ms, m_currentLapInvalid=invalid)


def tel(speed=200, throttle=1.0, brake=0.0, steer=0.0, gear=7, rpm=11000):
    return NS(m_speed=speed, m_throttle=throttle, m_brake=brake, m_steer=steer,
              m_gear=gear, m_engineRPM=rpm)


def motion(x=0.0):
    return NS(m_gForceLateral=500, m_gForceLongitudinal=-800,
              m_worldPositionX=x, m_worldPositionY=0.0, m_worldPositionZ=1.0, m_yaw=0.1)


def arrays(value, n=24):
    return tuple(value(i) for i in range(n))


def test_ai_capture_builds_fastest_valid_reference(tmp_path):
    c = AIBenchmarkCapture(enabled=True, min_difficulty=100)
    c.observe(pkt(1, NS(m_trackId=3, m_trackLength=5000, m_sessionType=10, m_formula=0,
                        m_aiDifficulty=110, m_equalCarPerformance=1, m_weather=0,
                        m_trackTemperature=30, m_airTemperature=20)))
    participants=[]
    for i in range(24):
        participants.append(NS(m_aiControlled=1 if i==1 else 0, m_name='FAST AI' if i==1 else 'X',
                               m_driverId=7, m_teamId=2, m_raceNumber=4))
    c.observe(pkt(4, NS(m_numActiveCars=2, m_participants=tuple(participants))))
    c.observe(pkt(0, NS(m_carMotionData=arrays(lambda i: motion(float(i))))))

    # Feed >20 distinct 5 m bins for AI car 1.
    for j in range(30):
        rows=arrays(lambda i: laprow(1, j*5.0 if i==1 else 0.0, j*100 if i==1 else 0))
        c.observe(pkt(2, NS(m_lapData=rows)))
        tels=arrays(lambda i: tel(speed=210-j if i==1 else 0, throttle=.2 if 8<=j<=13 and i==1 else 1.0,
                                      brake=.8 if 8<=j<=13 and i==1 else 0.0,
                                      steer=.2 if i==1 else 0.0))
        c.observe(pkt(6, NS(m_carTelemetryData=tels)))

    # New lap packet carries previous lap's authoritative last-lap time.
    rows=arrays(lambda i: laprow(2 if i==1 else 1, 0.0, 0, 85000 if i==1 else 0))
    result=c.observe(pkt(2, NS(m_lapData=rows)))
    assert result is not None
    lap, meta=result
    assert lap['valid'] is True
    assert lap['lap_time_s'] == 85.0
    assert lap['sample_count'] >= 20
    assert meta['driver'] == 'FAST AI'
    assert meta['ai_difficulty'] == 110
    assert meta['track_id'] == 3
    assert meta['source'] == 'EA_F1_AI_CAR'
    assert lap['sections']
    assert any('world_x' in row for row in lap['_samples'].values())
    validate_reference_lap(lap)

    path=tmp_path/'ai_ref.json'
    payload=c.save_best(path)
    assert path.exists()
    assert payload['metadata']['driver'] == 'FAST AI'


def test_ai_capture_ignores_below_minimum_difficulty():
    c=AIBenchmarkCapture(enabled=True, min_difficulty=100)
    c.observe(pkt(1, NS(m_trackId=1, m_trackLength=4000, m_sessionType=10, m_formula=0,
                        m_aiDifficulty=90, m_equalCarPerformance=1, m_weather=0,
                        m_trackTemperature=30, m_airTemperature=20)))
    ps=tuple(NS(m_aiControlled=1 if i==1 else 0, m_name='AI', m_driverId=1, m_teamId=1, m_raceNumber=1) for i in range(24))
    c.observe(pkt(4, NS(m_numActiveCars=2, m_participants=ps)))
    rows=tuple(laprow(1, i*5 if j==1 else 0, i*100 if j==1 else 0) for j in range(24) for i in [0])
    # Telemetry observation should not collect while session difficulty is below threshold.
    c.latest_lap=NS(m_lapData=tuple(laprow(1, 100.0 if i==1 else 0.0, 1000) for i in range(24)))
    c.observe(pkt(6, NS(m_carTelemetryData=tuple(tel() for _ in range(24)))))
    assert not c.tracks.get(1, NS(samples={})).samples
