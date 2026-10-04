"""Selected EA 2026 layouts; field order transcribed from official structures.
Verified against Season 8 PDF. Header is decoded separately.
See RACE_ENGINEER_STABLE_V2.md for historical source/layout notes.
"""

from dataclasses import dataclass
from .binary import Layout

@dataclass(frozen=True, slots=True)
class MarshalZone:
    m_zoneStart: float
    m_zoneFlag: int

MarshalZone_LAYOUT = Layout(MarshalZone, [
    ('m_zoneStart', 'f', 1, False),
    ('m_zoneFlag', 'b', 1, False),
])

@dataclass(frozen=True, slots=True)
class ActiveAeroZone:
    m_zoneStart: float
    m_zoneEnd: float

ActiveAeroZone_LAYOUT = Layout(ActiveAeroZone, [
    ('m_zoneStart', 'f', 1, False),
    ('m_zoneEnd', 'f', 1, False),
])

@dataclass(frozen=True, slots=True)
class DRSZone:
    m_zoneStart: float
    m_zoneEnd: float

DRSZone_LAYOUT = Layout(DRSZone, [
    ('m_zoneStart', 'f', 1, False),
    ('m_zoneEnd', 'f', 1, False),
])

@dataclass(frozen=True, slots=True)
class WeatherForecastSample:
    m_sessionType: int
    m_timeOffset: int
    m_weather: int
    m_trackTemperature: int
    m_trackTemperatureChange: int
    m_airTemperature: int
    m_airTemperatureChange: int
    m_rainPercentage: int

WeatherForecastSample_LAYOUT = Layout(WeatherForecastSample, [
    ('m_sessionType', 'B', 1, False),
    ('m_timeOffset', 'B', 1, False),
    ('m_weather', 'B', 1, False),
    ('m_trackTemperature', 'b', 1, False),
    ('m_trackTemperatureChange', 'b', 1, False),
    ('m_airTemperature', 'b', 1, False),
    ('m_airTemperatureChange', 'b', 1, False),
    ('m_rainPercentage', 'B', 1, False),
])

@dataclass(frozen=True, slots=True)
class PacketSessionData:
    m_weather: int
    m_trackTemperature: int
    m_airTemperature: int
    m_totalLaps: int
    m_trackLength: int
    m_sessionType: int
    m_trackId: int
    m_formula: int
    m_sessionTimeLeft: int
    m_sessionDuration: int
    m_pitSpeedLimit: int
    m_gamePaused: int
    m_isSpectating: int
    m_spectatorCarIndex: int
    m_sliProNativeSupport: int
    m_numMarshalZones: int
    m_marshalZones: tuple[MarshalZone, ...]
    m_safetyCarStatus: int
    m_networkGame: int
    m_numWeatherForecastSamples: int
    m_weatherForecastSamples: tuple[WeatherForecastSample, ...]
    m_forecastAccuracy: int
    m_aiDifficulty: int
    m_seasonLinkIdentifier: int
    m_weekendLinkIdentifier: int
    m_sessionLinkIdentifier: int
    m_pitStopWindowIdealLap: int
    m_pitStopWindowLatestLap: int
    m_pitStopRejoinPosition: int
    m_steeringAssist: int
    m_brakingAssist: int
    m_gearboxAssist: int
    m_pitAssist: int
    m_pitReleaseAssist: int
    m_ERSAssist: int
    m_DRSAssist: int
    m_dynamicRacingLine: int
    m_dynamicRacingLineType: int
    m_gameMode: int
    m_ruleSet: int
    m_timeOfDay: int
    m_sessionLength: int
    m_speedUnitsLeadPlayer: int
    m_temperatureUnitsLeadPlayer: int
    m_speedUnitsSecondaryPlayer: int
    m_temperatureUnitsSecondaryPlayer: int
    m_numSafetyCarPeriods: int
    m_numVirtualSafetyCarPeriods: int
    m_numRedFlagPeriods: int
    m_equalCarPerformance: int
    m_recoveryMode: int
    m_flashbackLimit: int
    m_surfaceType: int
    m_lowFuelMode: int
    m_raceStarts: int
    m_tyreTemperature: int
    m_pitLaneTyreSim: int
    m_carDamage: int
    m_carDamageRate: int
    m_collisions: int
    m_collisionsOffForFirstLapOnly: int
    m_mpUnsafePitRelease: int
    m_mpOffForGriefing: int
    m_cornerCuttingStringency: int
    m_parcFermeRules: int
    m_pitStopExperience: int
    m_safetyCar: int
    m_safetyCarExperience: int
    m_formationLap: int
    m_formationLapExperience: int
    m_redFlags: int
    m_affectsLicenceLevelSolo: int
    m_affectsLicenceLevelMP: int
    m_numSessionsInWeekend: int
    m_weekendStructure: tuple[int, ...]
    m_sector2LapDistanceStart: float
    m_sector3LapDistanceStart: float
    m_activeAeroTrackStatus: int
    m_numActiveAeroZonesFull: int
    m_activeAeroZonesFull: tuple[ActiveAeroZone, ...]
    m_numActiveAeroZonesPartial: int
    m_activeAeroZonesPartial: tuple[ActiveAeroZone, ...]
    m_numDRSZones: int
    m_drsZones: tuple[DRSZone, ...]
    m_startReactionTime: float
    m_antiLockBrakesAssist: int
    m_tractionControlAssist: int
    m_dynamicRacingLineHiVis: int
    m_dynamicRacingLineColourBlind: int
    m_recurringRewindPrompt: int

PacketSessionData_LAYOUT = Layout(PacketSessionData, [
    ('m_weather', 'B', 1, False),
    ('m_trackTemperature', 'b', 1, False),
    ('m_airTemperature', 'b', 1, False),
    ('m_totalLaps', 'B', 1, False),
    ('m_trackLength', 'H', 1, False),
    ('m_sessionType', 'B', 1, False),
    ('m_trackId', 'b', 1, False),
    ('m_formula', 'B', 1, False),
    ('m_sessionTimeLeft', 'H', 1, False),
    ('m_sessionDuration', 'H', 1, False),
    ('m_pitSpeedLimit', 'B', 1, False),
    ('m_gamePaused', 'B', 1, False),
    ('m_isSpectating', 'B', 1, False),
    ('m_spectatorCarIndex', 'B', 1, False),
    ('m_sliProNativeSupport', 'B', 1, False),
    ('m_numMarshalZones', 'B', 1, False),
    ('m_marshalZones', MarshalZone_LAYOUT, 21, True),
    ('m_safetyCarStatus', 'B', 1, False),
    ('m_networkGame', 'B', 1, False),
    ('m_numWeatherForecastSamples', 'B', 1, False),
    ('m_weatherForecastSamples', WeatherForecastSample_LAYOUT, 64, True),
    ('m_forecastAccuracy', 'B', 1, False),
    ('m_aiDifficulty', 'B', 1, False),
    ('m_seasonLinkIdentifier', 'I', 1, False),
    ('m_weekendLinkIdentifier', 'I', 1, False),
    ('m_sessionLinkIdentifier', 'I', 1, False),
    ('m_pitStopWindowIdealLap', 'B', 1, False),
    ('m_pitStopWindowLatestLap', 'B', 1, False),
    ('m_pitStopRejoinPosition', 'B', 1, False),
    ('m_steeringAssist', 'B', 1, False),
    ('m_brakingAssist', 'B', 1, False),
    ('m_gearboxAssist', 'B', 1, False),
    ('m_pitAssist', 'B', 1, False),
    ('m_pitReleaseAssist', 'B', 1, False),
    ('m_ERSAssist', 'B', 1, False),
    ('m_DRSAssist', 'B', 1, False),
    ('m_dynamicRacingLine', 'B', 1, False),
    ('m_dynamicRacingLineType', 'B', 1, False),
    ('m_gameMode', 'B', 1, False),
    ('m_ruleSet', 'B', 1, False),
    ('m_timeOfDay', 'I', 1, False),
    ('m_sessionLength', 'B', 1, False),
    ('m_speedUnitsLeadPlayer', 'B', 1, False),
    ('m_temperatureUnitsLeadPlayer', 'B', 1, False),
    ('m_speedUnitsSecondaryPlayer', 'B', 1, False),
    ('m_temperatureUnitsSecondaryPlayer', 'B', 1, False),
    ('m_numSafetyCarPeriods', 'B', 1, False),
    ('m_numVirtualSafetyCarPeriods', 'B', 1, False),
    ('m_numRedFlagPeriods', 'B', 1, False),
    ('m_equalCarPerformance', 'B', 1, False),
    ('m_recoveryMode', 'B', 1, False),
    ('m_flashbackLimit', 'B', 1, False),
    ('m_surfaceType', 'B', 1, False),
    ('m_lowFuelMode', 'B', 1, False),
    ('m_raceStarts', 'B', 1, False),
    ('m_tyreTemperature', 'B', 1, False),
    ('m_pitLaneTyreSim', 'B', 1, False),
    ('m_carDamage', 'B', 1, False),
    ('m_carDamageRate', 'B', 1, False),
    ('m_collisions', 'B', 1, False),
    ('m_collisionsOffForFirstLapOnly', 'B', 1, False),
    ('m_mpUnsafePitRelease', 'B', 1, False),
    ('m_mpOffForGriefing', 'B', 1, False),
    ('m_cornerCuttingStringency', 'B', 1, False),
    ('m_parcFermeRules', 'B', 1, False),
    ('m_pitStopExperience', 'B', 1, False),
    ('m_safetyCar', 'B', 1, False),
    ('m_safetyCarExperience', 'B', 1, False),
    ('m_formationLap', 'B', 1, False),
    ('m_formationLapExperience', 'B', 1, False),
    ('m_redFlags', 'B', 1, False),
    ('m_affectsLicenceLevelSolo', 'B', 1, False),
    ('m_affectsLicenceLevelMP', 'B', 1, False),
    ('m_numSessionsInWeekend', 'B', 1, False),
    ('m_weekendStructure', 'B', 12, True),
    ('m_sector2LapDistanceStart', 'f', 1, False),
    ('m_sector3LapDistanceStart', 'f', 1, False),
    ('m_activeAeroTrackStatus', 'B', 1, False),
    ('m_numActiveAeroZonesFull', 'B', 1, False),
    ('m_activeAeroZonesFull', ActiveAeroZone_LAYOUT, 8, True),
    ('m_numActiveAeroZonesPartial', 'B', 1, False),
    ('m_activeAeroZonesPartial', ActiveAeroZone_LAYOUT, 8, True),
    ('m_numDRSZones', 'B', 1, False),
    ('m_drsZones', DRSZone_LAYOUT, 4, True),
    ('m_startReactionTime', 'f', 1, False),
    ('m_antiLockBrakesAssist', 'B', 1, False),
    ('m_tractionControlAssist', 'B', 1, False),
    ('m_dynamicRacingLineHiVis', 'B', 1, False),
    ('m_dynamicRacingLineColourBlind', 'B', 1, False),
    ('m_recurringRewindPrompt', 'B', 1, False),
])

@dataclass(frozen=True, slots=True)
class LapData:
    m_lastLapTimeInMS: int
    m_currentLapTimeInMS: int
    m_sector1TimeMSPart: int
    m_sector1TimeMinutesPart: int
    m_sector2TimeMSPart: int
    m_sector2TimeMinutesPart: int
    m_deltaToCarInFrontMSPart: int
    m_deltaToCarInFrontMinutesPart: int
    m_deltaToRaceLeaderMSPart: int
    m_deltaToRaceLeaderMinutesPart: int
    m_lapDistance: float
    m_totalDistance: float
    m_safetyCarDelta: float
    m_carPosition: int
    m_currentLapNum: int
    m_pitStatus: int
    m_numPitStops: int
    m_sector: int
    m_currentLapInvalid: int
    m_penalties: int
    m_totalWarnings: int
    m_cornerCuttingWarnings: int
    m_numUnservedDriveThroughPens: int
    m_numUnservedStopGoPens: int
    m_gridPosition: int
    m_driverStatus: int
    m_resultStatus: int
    m_pitLaneTimerActive: int
    m_pitLaneTimeInLaneInMS: int
    m_pitStopTimerInMS: int
    m_pitStopShouldServePen: int
    m_speedTrapFastestSpeed: float
    m_speedTrapFastestLap: int

LapData_LAYOUT = Layout(LapData, [
    ('m_lastLapTimeInMS', 'I', 1, False),
    ('m_currentLapTimeInMS', 'I', 1, False),
    ('m_sector1TimeMSPart', 'H', 1, False),
    ('m_sector1TimeMinutesPart', 'B', 1, False),
    ('m_sector2TimeMSPart', 'H', 1, False),
    ('m_sector2TimeMinutesPart', 'B', 1, False),
    ('m_deltaToCarInFrontMSPart', 'H', 1, False),
    ('m_deltaToCarInFrontMinutesPart', 'B', 1, False),
    ('m_deltaToRaceLeaderMSPart', 'H', 1, False),
    ('m_deltaToRaceLeaderMinutesPart', 'B', 1, False),
    ('m_lapDistance', 'f', 1, False),
    ('m_totalDistance', 'f', 1, False),
    ('m_safetyCarDelta', 'f', 1, False),
    ('m_carPosition', 'B', 1, False),
    ('m_currentLapNum', 'B', 1, False),
    ('m_pitStatus', 'B', 1, False),
    ('m_numPitStops', 'B', 1, False),
    ('m_sector', 'B', 1, False),
    ('m_currentLapInvalid', 'B', 1, False),
    ('m_penalties', 'B', 1, False),
    ('m_totalWarnings', 'B', 1, False),
    ('m_cornerCuttingWarnings', 'B', 1, False),
    ('m_numUnservedDriveThroughPens', 'B', 1, False),
    ('m_numUnservedStopGoPens', 'B', 1, False),
    ('m_gridPosition', 'B', 1, False),
    ('m_driverStatus', 'B', 1, False),
    ('m_resultStatus', 'B', 1, False),
    ('m_pitLaneTimerActive', 'B', 1, False),
    ('m_pitLaneTimeInLaneInMS', 'H', 1, False),
    ('m_pitStopTimerInMS', 'H', 1, False),
    ('m_pitStopShouldServePen', 'B', 1, False),
    ('m_speedTrapFastestSpeed', 'f', 1, False),
    ('m_speedTrapFastestLap', 'B', 1, False),
])

@dataclass(frozen=True, slots=True)
class PacketLapData:
    m_lapData: tuple[LapData, ...]
    m_timeTrialPBCarIdx: int
    m_timeTrialRivalCarIdx: int

PacketLapData_LAYOUT = Layout(PacketLapData, [
    ('m_lapData', LapData_LAYOUT, 24, True),
    ('m_timeTrialPBCarIdx', 'B', 1, False),
    ('m_timeTrialRivalCarIdx', 'B', 1, False),
])

@dataclass(frozen=True, slots=True)
class LiveryColour:
    red: int
    green: int
    blue: int

LiveryColour_LAYOUT = Layout(LiveryColour, [
    ('red', 'B', 1, False),
    ('green', 'B', 1, False),
    ('blue', 'B', 1, False),
])

@dataclass(frozen=True, slots=True)
class ParticipantData:
    m_aiControlled: int
    m_driverId: int
    m_networkId: int
    m_teamId: int
    m_myTeam: int
    m_raceNumber: int
    m_nationality: int
    m_name: str
    m_yourTelemetry: int
    m_showOnlineNames: int
    m_techLevel: int
    m_platform: int
    m_numColours: int
    m_liveryColours: tuple[LiveryColour, ...]

ParticipantData_LAYOUT = Layout(ParticipantData, [
    ('m_aiControlled', 'B', 1, False),
    ('m_driverId', 'H', 1, False),
    ('m_networkId', 'H', 1, False),
    ('m_teamId', 'H', 1, False),
    ('m_myTeam', 'B', 1, False),
    ('m_raceNumber', 'B', 1, False),
    ('m_nationality', 'B', 1, False),
    ('m_name', '32s', 1, False),
    ('m_yourTelemetry', 'B', 1, False),
    ('m_showOnlineNames', 'B', 1, False),
    ('m_techLevel', 'H', 1, False),
    ('m_platform', 'B', 1, False),
    ('m_numColours', 'B', 1, False),
    ('m_liveryColours', LiveryColour_LAYOUT, 4, True),
])

@dataclass(frozen=True, slots=True)
class PacketParticipantsData:
    m_numActiveCars: int
    m_participants: tuple[ParticipantData, ...]

PacketParticipantsData_LAYOUT = Layout(PacketParticipantsData, [
    ('m_numActiveCars', 'B', 1, False),
    ('m_participants', ParticipantData_LAYOUT, 24, True),
])

@dataclass(frozen=True, slots=True)
class CarTelemetryData:
    m_speed: int
    m_throttle: float
    m_steer: float
    m_brake: float
    m_clutch: int
    m_gear: int
    m_engineRPM: int
    m_drs: int
    m_revLightsPercent: int
    m_revLightsBitValue: int
    m_brakesTemperature: tuple[int, ...]
    m_tyresSurfaceTemperature: tuple[int, ...]
    m_tyresInnerTemperature: tuple[int, ...]
    m_engineTemperature: int
    m_tyresPressure: tuple[float, ...]
    m_surfaceType: tuple[int, ...]

CarTelemetryData_LAYOUT = Layout(CarTelemetryData, [
    ('m_speed', 'H', 1, False),
    ('m_throttle', 'f', 1, False),
    ('m_steer', 'f', 1, False),
    ('m_brake', 'f', 1, False),
    ('m_clutch', 'B', 1, False),
    ('m_gear', 'b', 1, False),
    ('m_engineRPM', 'H', 1, False),
    ('m_drs', 'B', 1, False),
    ('m_revLightsPercent', 'B', 1, False),
    ('m_revLightsBitValue', 'H', 1, False),
    ('m_brakesTemperature', 'H', 4, True),
    ('m_tyresSurfaceTemperature', 'B', 4, True),
    ('m_tyresInnerTemperature', 'B', 4, True),
    ('m_engineTemperature', 'B', 1, False),
    ('m_tyresPressure', 'f', 4, True),
    ('m_surfaceType', 'B', 4, True),
])

@dataclass(frozen=True, slots=True)
class PacketCarTelemetryData:
    m_carTelemetryData: tuple[CarTelemetryData, ...]
    m_mfdPanelIndex: int
    m_mfdPanelIndexSecondaryPlayer: int
    m_suggestedGear: int

PacketCarTelemetryData_LAYOUT = Layout(PacketCarTelemetryData, [
    ('m_carTelemetryData', CarTelemetryData_LAYOUT, 24, True),
    ('m_mfdPanelIndex', 'B', 1, False),
    ('m_mfdPanelIndexSecondaryPlayer', 'B', 1, False),
    ('m_suggestedGear', 'b', 1, False),
])

@dataclass(frozen=True, slots=True)
class CarStatusData:
    m_tractionControl: int
    m_antiLockBrakes: int
    m_fuelMix: int
    m_frontBrakeBias: int
    m_pitLimiterStatus: int
    m_fuelInTank: float
    m_fuelCapacity: float
    m_fuelRemainingLaps: float
    m_maxRPM: int
    m_idleRPM: int
    m_maxGears: int
    m_drsAllowed: int
    m_drsActivationDistance: int
    m_actualTyreCompound: int
    m_visualTyreCompound: int
    m_tyresAgeLaps: int
    m_vehicleFIAFlags: int
    m_enginePowerICE: float
    m_enginePowerMGUK: float
    m_ersStoreEnergy: float
    m_ersDeployMode: int
    m_ersHarvestedThisLapMGUK: float
    m_ersHarvestedThisLapMGUH: float
    m_ersHarvestLimitPerLap: float
    m_ersDeployedThisLap: float
    m_networkPaused: int

CarStatusData_LAYOUT = Layout(CarStatusData, [
    ('m_tractionControl', 'B', 1, False),
    ('m_antiLockBrakes', 'B', 1, False),
    ('m_fuelMix', 'B', 1, False),
    ('m_frontBrakeBias', 'B', 1, False),
    ('m_pitLimiterStatus', 'B', 1, False),
    ('m_fuelInTank', 'f', 1, False),
    ('m_fuelCapacity', 'f', 1, False),
    ('m_fuelRemainingLaps', 'f', 1, False),
    ('m_maxRPM', 'H', 1, False),
    ('m_idleRPM', 'H', 1, False),
    ('m_maxGears', 'B', 1, False),
    ('m_drsAllowed', 'B', 1, False),
    ('m_drsActivationDistance', 'H', 1, False),
    ('m_actualTyreCompound', 'B', 1, False),
    ('m_visualTyreCompound', 'B', 1, False),
    ('m_tyresAgeLaps', 'B', 1, False),
    ('m_vehicleFIAFlags', 'b', 1, False),
    ('m_enginePowerICE', 'f', 1, False),
    ('m_enginePowerMGUK', 'f', 1, False),
    ('m_ersStoreEnergy', 'f', 1, False),
    ('m_ersDeployMode', 'B', 1, False),
    ('m_ersHarvestedThisLapMGUK', 'f', 1, False),
    ('m_ersHarvestedThisLapMGUH', 'f', 1, False),
    ('m_ersHarvestLimitPerLap', 'f', 1, False),
    ('m_ersDeployedThisLap', 'f', 1, False),
    ('m_networkPaused', 'B', 1, False),
])

@dataclass(frozen=True, slots=True)
class PacketCarStatusData:
    m_carStatusData: tuple[CarStatusData, ...]

PacketCarStatusData_LAYOUT = Layout(PacketCarStatusData, [
    ('m_carStatusData', CarStatusData_LAYOUT, 24, True),
])

@dataclass(frozen=True, slots=True)
class CarDamageData:
    m_tyresWear: tuple[float, ...]
    m_tyresDamage: tuple[int, ...]
    m_brakesDamage: tuple[int, ...]
    m_tyreBlisters: tuple[int, ...]
    m_frontLeftWingDamage: int
    m_frontRightWingDamage: int
    m_rearWingDamage: int
    m_floorDamage: int
    m_diffuserDamage: int
    m_sidepodDamage: int
    m_drsFault: int
    m_ersFault: int
    m_gearBoxDamage: int
    m_engineDamage: int
    m_engineMGUHWear: int
    m_engineESWear: int
    m_engineCEWear: int
    m_engineICEWear: int
    m_engineMGUKWear: int
    m_engineTCWear: int
    m_engineBlown: int
    m_engineSeized: int

CarDamageData_LAYOUT = Layout(CarDamageData, [
    ('m_tyresWear', 'f', 4, True),
    ('m_tyresDamage', 'B', 4, True),
    ('m_brakesDamage', 'B', 4, True),
    ('m_tyreBlisters', 'B', 4, True),
    ('m_frontLeftWingDamage', 'B', 1, False),
    ('m_frontRightWingDamage', 'B', 1, False),
    ('m_rearWingDamage', 'B', 1, False),
    ('m_floorDamage', 'B', 1, False),
    ('m_diffuserDamage', 'B', 1, False),
    ('m_sidepodDamage', 'B', 1, False),
    ('m_drsFault', 'B', 1, False),
    ('m_ersFault', 'B', 1, False),
    ('m_gearBoxDamage', 'B', 1, False),
    ('m_engineDamage', 'B', 1, False),
    ('m_engineMGUHWear', 'B', 1, False),
    ('m_engineESWear', 'B', 1, False),
    ('m_engineCEWear', 'B', 1, False),
    ('m_engineICEWear', 'B', 1, False),
    ('m_engineMGUKWear', 'B', 1, False),
    ('m_engineTCWear', 'B', 1, False),
    ('m_engineBlown', 'B', 1, False),
    ('m_engineSeized', 'B', 1, False),
])

@dataclass(frozen=True, slots=True)
class PacketCarDamageData:
    m_carDamageData: tuple[CarDamageData, ...]

PacketCarDamageData_LAYOUT = Layout(PacketCarDamageData, [
    ('m_carDamageData', CarDamageData_LAYOUT, 24, True),
])

@dataclass(frozen=True, slots=True)
class TyreSetData:
    m_actualTyreCompound: int
    m_visualTyreCompound: int
    m_wear: int
    m_available: int
    m_recommendedSession: int
    m_lifeSpan: int
    m_usableLife: int
    m_lapDeltaTime: int
    m_fitted: int

TyreSetData_LAYOUT = Layout(TyreSetData, [
    ('m_actualTyreCompound', 'B', 1, False),
    ('m_visualTyreCompound', 'B', 1, False),
    ('m_wear', 'B', 1, False),
    ('m_available', 'B', 1, False),
    ('m_recommendedSession', 'B', 1, False),
    ('m_lifeSpan', 'B', 1, False),
    ('m_usableLife', 'B', 1, False),
    ('m_lapDeltaTime', 'h', 1, False),
    ('m_fitted', 'B', 1, False),
])

@dataclass(frozen=True, slots=True)
class PacketTyreSetsData:
    m_carIdx: int
    m_tyreSetData: tuple[TyreSetData, ...]
    m_fittedIdx: int

PacketTyreSetsData_LAYOUT = Layout(PacketTyreSetsData, [
    ('m_carIdx', 'B', 1, False),
    ('m_tyreSetData', TyreSetData_LAYOUT, 20, True),
    ('m_fittedIdx', 'B', 1, False),
])

@dataclass(frozen=True, slots=True)
class CarTelemetry2Data:
    m_activeAeroMode: int
    m_activeAeroAvailable: int
    m_activeAeroActivationDistance: int
    m_overtakeAvailable: int
    m_overtakeActive: int
    m_overtakeActivationDistance: int
    m_2026Regulations: int
    m_drivingWrongWay: int

CarTelemetry2Data_LAYOUT = Layout(CarTelemetry2Data, [
    ('m_activeAeroMode', 'B', 1, False),
    ('m_activeAeroAvailable', 'B', 1, False),
    ('m_activeAeroActivationDistance', 'H', 1, False),
    ('m_overtakeAvailable', 'B', 1, False),
    ('m_overtakeActive', 'B', 1, False),
    ('m_overtakeActivationDistance', 'H', 1, False),
    ('m_2026Regulations', 'B', 1, False),
    ('m_drivingWrongWay', 'B', 1, False),
])

@dataclass(frozen=True, slots=True)
class PacketCarTelemetry2Data:
    m_carTelemetry2Data: tuple[CarTelemetry2Data, ...]

PacketCarTelemetry2Data_LAYOUT = Layout(PacketCarTelemetry2Data, [
    ('m_carTelemetry2Data', CarTelemetry2Data_LAYOUT, 24, True),
])
