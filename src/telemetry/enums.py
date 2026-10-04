"""Readable values from EA's Season 8 PDF appendices and structure comments."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EnumValue:
    raw: int
    name: str


def label(table: dict[int, str], value: int) -> EnumValue:
    return EnumValue(value, table.get(value, f'UNKNOWN({value})'))


WEATHER = dict(enumerate(('Clear', 'Light cloud', 'Overcast', 'Light rain', 'Heavy rain', 'Storm')))
SESSION_TYPES = dict(enumerate(('Unknown', 'Practice 1', 'Practice 2', 'Practice 3',
    'Short Practice', 'Qualifying 1', 'Qualifying 2', 'Qualifying 3', 'Short Qualifying',
    'One-Shot Qualifying', 'Sprint Shootout 1', 'Sprint Shootout 2', 'Sprint Shootout 3',
    'Short Sprint Shootout', 'One-Shot Sprint Shootout', 'Race', 'Race 2', 'Race 3', 'Time Trial')))
TRACKS = {-1: 'Unknown', 0: 'Melbourne', 2: 'Shanghai', 3: 'Sakhir (Bahrain)',
    4: 'Catalunya', 5: 'Monaco', 6: 'Montreal', 7: 'Silverstone', 9: 'Hungaroring',
    10: 'Spa', 11: 'Monza', 12: 'Singapore', 13: 'Suzuka', 14: 'Abu Dhabi', 15: 'Texas',
    16: 'Brazil', 17: 'Austria', 19: 'Mexico', 20: 'Baku (Azerbaijan)', 26: 'Zandvoort',
    27: 'Imola', 29: 'Jeddah', 30: 'Miami', 31: 'Las Vegas', 32: 'Losail',
    39: 'Silverstone (Reverse)', 40: 'Austria (Reverse)', 41: 'Zandvoort (Reverse)', 42: 'Madrid'}
TEAMS = {0: 'Mercedes', 1: 'Ferrari', 2: 'Red Bull Racing', 3: 'Williams',
    4: 'Aston Martin', 5: 'Alpine', 6: 'RB', 7: 'Haas', 8: 'McLaren', 9: 'Sauber',
    41: 'F1 Generic', 104: 'F1 Custom Team', 129: 'Konnersport',
    142: "APXGP '24", 154: "APXGP '25", 155: "Konnersport '24"}
for start, year in ((158, 24), (465, 25), (489, 26)):
    for index, name in enumerate(('Art GP', 'Campos', 'Rodin Motorsport', 'AIX Racing',
            'DAMS', 'Hitech', 'MP Motorsport', 'Prema', 'Trident', 'Van Amersfoort Racing', 'Invicta')):
        TEAMS[start + index] = f"{name} '{year}"
for index in range(10):
    TEAMS[185 + index] = f"{TEAMS[index]} '24"
for index, name in enumerate(('Mercedes', 'Ferrari', 'Red Bull Racing', 'Williams',
        'Aston Martin', 'Alpine', 'RB', 'Haas', 'McLaren', 'Audi', 'Cadillac')):
    TEAMS[476 + index] = f"{name} '26"
SAFETY_CAR = {0: 'None', 1: 'Full', 2: 'Virtual', 3: 'Formation lap'}
PIT_STATUS = {0: 'None', 1: 'Pitting', 2: 'In pit area'}
DRIVER_STATUS = {0: 'In garage', 1: 'Flying lap', 2: 'In lap', 3: 'Out lap', 4: 'On track'}
RESULT_STATUS = {0: 'Invalid', 1: 'Inactive', 2: 'Active', 3: 'Finished',
                 4: 'Did not finish', 5: 'Disqualified', 6: 'Not classified', 7: 'Retired'}
FUEL_MIX = {0: 'Lean', 1: 'Standard', 2: 'Rich', 3: 'Max'}
ERS_MODE = {0: 'None', 1: 'Medium', 2: 'Hotlap', 3: 'Boost'}
ACTIVE_AERO = {0: 'Corner mode', 1: 'Straight mode'}
TEMPERATURE_CHANGE = {0: 'Up', 1: 'Down', 2: 'No change'}
ACTUAL_COMPOUND = {7: 'Intermediate', 8: 'Wet', 9: 'Classic dry', 10: 'Classic wet',
    11: 'F2 super soft', 12: 'F2 soft', 13: 'F2 medium', 14: 'F2 hard', 15: 'F2 wet',
    16: 'C5', 17: 'C4', 18: 'C3', 19: 'C2', 20: 'C1', 21: 'C0', 22: 'C6'}
VISUAL_COMPOUND = {7: 'Intermediate', 8: 'Wet', 9: 'Classic dry', 10: 'Classic wet',
    15: 'F2 wet', 16: 'Soft', 17: 'Medium', 18: 'Hard',
    19: 'F2 super soft', 20: 'F2 soft', 21: 'F2 medium', 22: 'F2 hard'}

MARSHAL_FLAG = {-1: 'Unknown', 0: 'None', 1: 'Green', 2: 'Blue', 3: 'Yellow'}

PENALTY_TYPES = {
    0: 'Drive-through', 1: 'Stop-go', 2: 'Grid penalty', 3: 'Penalty reminder',
    4: 'Time penalty', 5: 'Warning', 6: 'Disqualified', 7: 'Removed from formation lap',
    8: 'Parked too long timer', 9: 'Tyre regulations', 10: 'This lap invalidated',
    11: 'This and next lap invalidated', 12: 'This lap invalidated without reason',
    13: 'This and next lap invalidated without reason', 14: 'This and previous lap invalidated',
    15: 'This and previous lap invalidated without reason', 16: 'Retired', 17: 'Black flag timer',
}

INFRINGEMENT_TYPES = {
    0: 'blocking by slow driving', 1: 'blocking by wrong-way driving', 2: 'reversing off the start line',
    3: 'a major collision', 4: 'a collision', 5: 'failing to hand back a position after a collision',
    6: 'failing to hand back multiple positions after a collision', 7: 'corner cutting and gaining time',
    8: 'corner cutting while overtaking', 9: 'corner cutting while overtaking multiple cars',
    10: 'crossing the pit exit line', 11: 'ignoring blue flags', 12: 'ignoring yellow flags',
    13: 'ignoring a drive-through penalty', 14: 'too many drive-through penalties',
    15: 'a drive-through reminder', 16: 'a drive-through reminder to serve this lap', 17: 'speeding in the pit lane',
    18: 'being parked for too long', 19: 'ignoring tyre regulations', 20: 'too many penalties',
    21: 'multiple warnings', 22: 'approaching disqualification', 23: 'tyre regulations',
    24: 'multiple tyre regulations', 25: 'corner cutting', 26: 'running wide',
    27: 'corner cutting or running wide with a minor time gain', 28: 'corner cutting or running wide with a significant time gain',
    29: 'corner cutting or running wide with an extreme time gain', 30: 'wall riding', 31: 'using a flashback',
    32: 'resetting to track', 33: 'blocking the pit lane', 34: 'a jump start', 35: 'a Safety Car collision',
    36: 'an illegal overtake under the Safety Car', 37: 'exceeding the allowed Safety Car pace',
    38: 'exceeding the allowed Virtual Safety Car pace', 39: 'driving below the allowed formation-lap speed',
    40: 'formation-lap parking', 41: 'a mechanical failure', 42: 'terminal damage',
    43: 'falling too far back under the Safety Car', 44: 'the black-flag timer', 45: 'an unserved stop-go penalty',
    46: 'an unserved drive-through penalty', 47: 'an engine component change', 48: 'a gearbox change',
    49: 'a Parc Ferme change', 50: 'a league grid penalty', 51: 'a retry penalty', 52: 'an illegal time gain',
    53: 'the mandatory pit stop', 54: 'an assigned attribute',
}

PARTIAL_MODE_REASONS = {0: 'wet track', 1: 'Safety Car deployed', 2: 'red flag'}
DRS_DISABLED_REASONS = {0: 'wet track', 1: 'Safety Car deployed', 2: 'red flag', 3: 'minimum lap not reached'}
RETIREMENT_REASONS = {0: 'invalid', 1: 'retired', 2: 'finished', 3: 'terminal damage', 4: 'inactive',
    5: 'not enough laps completed', 6: 'black flagged', 7: 'red flagged', 8: 'mechanical failure',
    9: 'session skipped', 10: 'session simulated'}
SAFETY_CAR_EVENT = {0: 'Deployed', 1: 'Returning', 2: 'Returned', 3: 'Resume race'}
COLLISION_SEVERITY = {0: 'low', 1: 'medium', 2: 'high'}


def flag(raw: int) -> bool | None:
    """Unknown boolean values remain unavailable, never coerced to True."""
    return {0: False, 1: True}.get(raw)
