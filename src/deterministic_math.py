"""Offline, deterministic arithmetic derived only from decoded EA telemetry.
No ML, cloud, probabilistic prediction, or invented hidden game state.
"""
from __future__ import annotations
import math
from .race_state.models import RaceState, Wheels
from .event_context import build_event_context

def _vals(w: Wheels|None):
    return [] if w is None else [v for v in (w.FL,w.FR,w.RL,w.RR) if isinstance(v,(int,float)) and math.isfinite(v)]
def _spread(w):
    v=_vals(w); return (max(v)-min(v)) if len(v)==4 else None
def _avg(items):
    v=[x for x in items if isinstance(x,(int,float)) and math.isfinite(x)]; return sum(v)/len(v) if v else None

def snapshot(state: RaceState)->dict[str, object]:
    c=state.player
    if not c: return {}
    ctx=build_event_context(state)
    m=ctx.metrics
    d={"event_profile":ctx.profile}
    # Race progress / exact counts
    if m.race_position_strategy and c.lap.current_lap is not None and state.session.total_laps:
        d['laps_remaining']=max(0,state.session.total_laps-c.lap.current_lap)
        if c.lap.lap_distance_m is not None and state.session.track_length_m:
            frac=max(0.0,min(1.0,c.lap.lap_distance_m/state.session.track_length_m))
            d['race_progress_percent']=100*((c.lap.current_lap-1+frac)/state.session.total_laps)
    # Four-corner arithmetic
    for name,w in [('tyre_wear',c.tyres.wear_percent),('tyre_surface_temp',c.tyres.surface_temperature_c),('tyre_inner_temp',c.tyres.inner_temperature_c),('tyre_pressure',c.tyres.pressure_psi),('tyre_damage',c.tyres.damage_percent),('tyre_blisters',c.tyres.blisters_percent),('brake_damage',c.damage.brakes_percent)]:
        vals=_vals(w)
        if vals:
            d[name+'_average']=_avg(vals); d[name+'_spread']=_spread(w); d[name+'_maximum']=max(vals); d[name+'_minimum']=min(vals)
            if len(vals)==4:
                d[name+'_front_average']=(w.FL+w.FR)/2; d[name+'_rear_average']=(w.RL+w.RR)/2
                d[name+'_front_rear_delta']=d[name+'_front_average']-d[name+'_rear_average']
                d[name+'_left_right_delta']=((w.FL+w.RL)/2)-((w.FR+w.RR)/2)
    # Fuel and ERS values that are exact from the current packet
    if m.fuel_strategy and c.fuel.remaining_laps is not None: d['fuel_remaining_laps']=c.fuel.remaining_laps
    if m.ers_energy_strategy and c.energy.harvest_limit_j not in (None,0) and c.energy.harvested_mguk_j is not None:
        d['ers_harvest_limit_used_percent']=100*c.energy.harvested_mguk_j/c.energy.harvest_limit_j
    # Direct gap arithmetic
    if c.lap.gap_to_car_in_front_s is not None: d['gap_ahead_s']=c.lap.gap_to_car_in_front_s
    if state.gap_behind_s is not None: d['gap_behind_s']=state.gap_behind_s
    # Extended packets
    ext=state.extended
    motion=ext.get('motion')
    if motion and state.player_index is not None:
        m=motion.m_carMotionData[state.player_index]
        d.update(g_lateral=m.m_gForceLateral/1000.0,g_longitudinal=m.m_gForceLongitudinal/1000.0,g_vertical=m.m_gForceVertical/1000.0,
                 world_speed_mps=math.sqrt(m.m_worldVelocityX**2+m.m_worldVelocityY**2+m.m_worldVelocityZ**2),yaw_rad=m.m_yaw,pitch_rad=m.m_pitch,roll_rad=m.m_roll)
    setup=ext.get('setups')
    if setup and state.player_index is not None:
        s=setup.m_carSetupData[state.player_index]
        d.update(setup_front_wing=s.m_frontWing,setup_rear_wing=s.m_rearWing,setup_brake_pressure_percent=s.m_brakePressure,setup_brake_bias_percent=s.m_brakeBias,setup_engine_braking_percent=s.m_engineBraking,setup_diff_on_throttle_percent=s.m_onThrottle,setup_diff_off_throttle_percent=s.m_offThrottle,next_front_wing=setup.m_nextFrontWingValue, setup_front_camber=s.m_frontCamber,setup_rear_camber=s.m_rearCamber,setup_front_toe=s.m_frontToe,setup_rear_toe=s.m_rearToe,setup_front_suspension=s.m_frontSuspension,setup_rear_suspension=s.m_rearSuspension,setup_front_arb=s.m_frontAntiRollBar,setup_rear_arb=s.m_rearAntiRollBar,setup_front_height=s.m_frontSuspensionHeight,setup_rear_height=s.m_rearSuspensionHeight,setup_ballast=s.m_ballast,setup_fuel_load=s.m_fuelLoad,setup_fl_pressure=s.m_frontLeftTyrePressure,setup_fr_pressure=s.m_frontRightTyrePressure,setup_rl_pressure=s.m_rearLeftTyrePressure,setup_rr_pressure=s.m_rearRightTyrePressure)
    mex=ext.get('motionex')
    if mex:
        ws=list(mex.m_wheelSpeed); sr=list(mex.m_wheelSlipRatio); sa=list(mex.m_wheelSlipAngle)
        d.update(wheel_speed_average=_avg(ws),wheel_speed_spread=max(ws)-min(ws),wheel_speed_min=min(ws),wheel_speed_max=max(ws),wheel_slip_ratio_max=max(abs(x) for x in sr),wheel_slip_ratio_average_abs=_avg([abs(x) for x in sr]),wheel_slip_angle_max=max(abs(x) for x in sa),wheel_slip_angle_average_abs=_avg([abs(x) for x in sa]),front_wheels_angle_rad=mex.m_frontWheelsAngle,front_aero_height=mex.m_frontAeroHeight,rear_aero_height=mex.m_rearAeroHeight,aero_height_delta=mex.m_frontAeroHeight-mex.m_rearAeroHeight,chassis_yaw_rad=mex.m_chassisYaw,chassis_pitch_rad=mex.m_chassisPitch,cog_height=mex.m_heightOfCOGAboveGround,local_speed_mps=math.sqrt(mex.m_localVelocityX**2+mex.m_localVelocityY**2+mex.m_localVelocityZ**2),angular_speed_rad_s=math.sqrt(mex.m_angularVelocityX**2+mex.m_angularVelocityY**2+mex.m_angularVelocityZ**2),angular_accel_rad_s2=math.sqrt(mex.m_angularAccelerationX**2+mex.m_angularAccelerationY**2+mex.m_angularAccelerationZ**2),suspension_position_spread=max(mex.m_suspensionPosition)-min(mex.m_suspensionPosition),suspension_velocity_max_abs=max(abs(x) for x in mex.m_suspensionVelocity),suspension_accel_max_abs=max(abs(x) for x in mex.m_suspensionAcceleration),wheel_lat_force_max_abs=max(abs(x) for x in mex.m_wheelLatForce),wheel_long_force_max_abs=max(abs(x) for x in mex.m_wheelLongForce),wheel_vertical_force_max=max(mex.m_wheelVertForce),front_roll_angle=mex.m_frontRollAngle,rear_roll_angle=mex.m_rearRollAngle,roll_angle_delta=mex.m_frontRollAngle-mex.m_rearRollAngle,wheel_camber_spread=max(mex.m_wheelCamber)-min(mex.m_wheelCamber),wheel_camber_gain_spread=max(mex.m_wheelCamberGain)-min(mex.m_wheelCamberGain))
    hist=ext.get('history')
    if hist and hist.m_carIdx==state.player_index:
        n=min(hist.m_numLaps,100); laps=hist.m_lapHistoryData[:n]
        valid=[x for x in laps if x.m_lapTimeInMS and (x.m_lapValidBitFlags&1)]
        if valid:
            d['history_best_lap_s']=min(x.m_lapTimeInMS for x in valid)/1000
            d['history_valid_laps']=len(valid)
        d['history_laps']=n; d['history_tyre_stints']=min(hist.m_numTyreStints,8)
    tt=ext.get('timetrial')
    if tt:
        a,b=tt.m_playerSessionBestDataSet,tt.m_personalBestDataSet
        if a.m_valid and a.m_lapTimeInMS: d['tt_session_best_s']=a.m_lapTimeInMS/1000
        if b.m_valid and b.m_lapTimeInMS: d['tt_personal_best_s']=b.m_lapTimeInMS/1000
        if a.m_valid and b.m_valid and a.m_lapTimeInMS and b.m_lapTimeInMS: d['tt_delta_to_pb_s']=(a.m_lapTimeInMS-b.m_lapTimeInMS)/1000
    lp=ext.get('lappos')
    if lp and state.player_index is not None and lp.m_numLaps:
        idx=(min(lp.m_numLaps,50)-1)*24+state.player_index
        if idx < len(lp.m_positionForVehicleIdx): d['recorded_lap_position']=lp.m_positionForVehicleIdx[idx] or None
    return d

def short_report(state:RaceState)->str:
    d=snapshot(state)
    if not d: return 'Live car data is unavailable.'
    c=state.player
    ctx=build_event_context(state)
    m=ctx.metrics
    parts=[]
    if m.race_position_strategy and c and c.lap.position: parts.append(f'P{c.lap.position}')
    if c and c.lap.previous_lap_time_s: parts.append(f'last lap {c.lap.previous_lap_time_s:.3f}')
    if 'laps_remaining' in d: parts.append(f"{d['laps_remaining']} laps remaining")
    if m.fuel_strategy and c and c.fuel.remaining_laps is not None: parts.append(f"fuel {c.fuel.remaining_laps:.1f} laps")
    if m.tyre_wear_strategy and 'tyre_wear_maximum' in d: parts.append(f"max tyre wear {d['tyre_wear_maximum']:.0f} percent")
    if ctx.profile=='time_trial' and 'tt_session_best_s' in d: parts.append(f"session best {d['tt_session_best_s']:.3f}")
    return '. '.join(parts)+'.' if parts else 'Live status available.'
