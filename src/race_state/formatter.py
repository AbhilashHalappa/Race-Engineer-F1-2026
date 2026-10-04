"""Console presentation only; no strategy and no binary interpretation."""

from .models import RaceState, Wheels
from ..telemetry.enums import EnumValue


def value(item, precision=2) -> str:
    if item is None:
        return 'N/A'
    if isinstance(item, EnumValue):
        return f'{item.name} [{item.raw}]'
    if isinstance(item, bool):
        return 'Yes' if item else 'No'
    if isinstance(item, float):
        return f'{item:.{precision}f}'
    return str(item)


def wheel_row(name: str, item: Wheels | None) -> str:
    return f'  {name:14}' + ' '.join(f'{value(getattr(item, key) if item else None):>8}' for key in ('FL', 'FR', 'RL', 'RR'))


def format_state(state: RaceState, now: float) -> str:
    lines = ['\n' + '=' * 60]
    latest = max((t.received_at for t in state.updated.values()), default=None)
    if latest is None:
        lines += ['Waiting for F1 telemetry (decoded race state)...']
    else:
        lines += ['F1 2026 - LIVE' if now - latest <= 5 else 'F1 2026 - STALE (no recent decoded state)']
    s, p = state.session, state.player
    lines += ['Session', f'  UID: {value(s.uid)} | Track: {value(s.track)}',
        f'  Type: {value(s.session_type)} | Weather: {value(s.weather)}',
        f'  Track/Air C: {value(s.track_temperature_c)} / {value(s.air_temperature_c)}',
        f'  Laps: {value(p.lap.current_lap if p else None)} / {value(s.total_laps)} | Time left: {value(s.time_left_s)} s',
        f'  Safety car: {value(s.safety_car)} | Paused: {value(s.paused)} | Ended: {value(s.ended)}']
    if s.forecast:
        lines.append('  Forecast (game supplied): ' + '; '.join(
            f'+{f.offset_minutes}m {f.weather.name}, rain {f.rain_percent}%' for f in s.forecast[:4]))
    else:
        lines.append('  Forecast: N/A')
    if p is None:
        lines.append('Player / Car / Fuel / ERS / Tyres / Damage / Race: N/A')
    else:
        lap, car, aero, tyres, damage = p.lap, p.telemetry, p.aero, p.tyres, p.damage
        lines += ['Player', f'  Index: {p.index} | Driver: {value(p.identity.name)} | Team: {value(p.identity.team)}',
            f'  Position: {value(lap.position)} | Lap: {value(lap.current_lap)} | Sector: {value(lap.sector)}',
            f'  Lap current/previous s: {value(lap.current_lap_time_s, 3)} / {value(lap.previous_lap_time_s, 3)}',
            f'  Status: {value(lap.driver_status)} | Pit: {value(lap.pit_status)}',
            f'  Penalties: {value(lap.penalties_s)} s | Warnings: {value(lap.warnings)}',
            'Car', f'  Speed: {value(car.speed_kph)} km/h | Gear: {value(car.gear)} | RPM: {value(car.rpm)}',
            f'  Throttle: {value(car.throttle * 100 if car.throttle is not None else None)}% | Brake: {value(car.brake * 100 if car.brake is not None else None)}%',
            f'  DRS: {value(car.drs)} | Active aero: {value(aero.active_aero_mode)}',
            f'  Aero available: {value(aero.active_aero_available)} | Activation distance: {value(aero.active_aero_activation_distance_m)} m',
            f'  Overtake available/active: {value(aero.overtake_available)} / {value(aero.overtake_active)} | Distance: {value(aero.overtake_activation_distance_m)} m',
            'Fuel', f'  Remaining/capacity: {value(p.fuel.remaining_mass)} / {value(p.fuel.capacity)} (EA raw mass)',
            f'  Remaining laps (MFD): {value(p.fuel.remaining_laps)} | Mix: {value(p.fuel.mix)}',
            'ERS', f'  Store: {value(p.energy.store_j)} J | Deploy mode: {value(p.energy.deploy_mode)}',
            f'  Harvested MGUK/MGUH: {value(p.energy.harvested_mguk_j)} / {value(p.energy.harvested_mguh_j)} J',
            f'  Deployed this lap: {value(p.energy.deployed_this_lap_j)} J',
            f'Tyres: {value(tyres.actual_compound)} | Age: {value(tyres.age_laps)} laps | Set: {value(tyres.fitted_set_index)}',
            '                        FL       FR       RL       RR',
            wheel_row('Wear %', tyres.wear_percent), wheel_row('Surface C', tyres.surface_temperature_c),
            wheel_row('Inner C', tyres.inner_temperature_c), wheel_row('Pressure PSI', tyres.pressure_psi),
            wheel_row('Damage %', tyres.damage_percent),
            'Damage', f'  Wings FL/FR/rear: {value(damage.front_left_wing_percent)} / {value(damage.front_right_wing_percent)} / {value(damage.rear_wing_percent)} %',
            f'  Floor/diffuser/sidepod: {value(damage.floor_percent)} / {value(damage.diffuser_percent)} / {value(damage.sidepod_percent)} %',
            'Race']
        for name, index in [('Ahead', state.ahead_index), ('Behind', state.behind_index)]:
            other = state.field.get(index)
            lines.append(f'  {name}: ' + (f'car {index}, {value(other.identity.name)}' if other else 'N/A'))
        lines.append(f'  Reported delta ahead/behind: {value(lap.gap_to_car_in_front_s, 3)} / {value(state.gap_behind_s, 3)} s')
    if state.events:
        lines.append('Latest events: ' + ', '.join(e.name for e in state.events[-3:]))
    else:
        lines.append('Latest events: N/A')
    lines.append('Freshness (age; STALE after 5s, display threshold only):')
    for cat in ('session', 'participants', 'lap', 'telemetry', 'status', 'damage', 'tyres', 'telemetry2'):
        stamp = state.updated.get(cat) if cat in ('session', 'participants') else (p.updated.get(cat) if p else None)
        age = stamp.age(now) if stamp else None
        lines.append(f'  {cat}: ' + ('N/A' if age is None else f'{age:.1f}s' + (' STALE' if age > 5 else '')))
    return '\n'.join(lines)
