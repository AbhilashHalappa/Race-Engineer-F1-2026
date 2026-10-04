"""Remaining EA F1 25 2026 Season Pack packet layouts (IDs 0,5,8,9,11,13,14,15)."""
from dataclasses import dataclass
from .binary import Layout

@dataclass(frozen=True, slots=True)
class CarMotionData:
    m_worldPositionX: float; m_worldPositionY: float; m_worldPositionZ: float
    m_worldVelocityX: float; m_worldVelocityY: float; m_worldVelocityZ: float
    m_worldForwardDirX: int; m_worldForwardDirY: int; m_worldForwardDirZ: int
    m_worldRightDirX: int; m_worldRightDirY: int; m_worldRightDirZ: int
    m_gForceLateral: int; m_gForceLongitudinal: int; m_gForceVertical: int
    m_yaw: float; m_pitch: float; m_roll: float
CarMotionData_LAYOUT=Layout(CarMotionData,[
 ('m_worldPositionX','f',1,False),('m_worldPositionY','f',1,False),('m_worldPositionZ','f',1,False),
 ('m_worldVelocityX','f',1,False),('m_worldVelocityY','f',1,False),('m_worldVelocityZ','f',1,False),
 ('m_worldForwardDirX','h',1,False),('m_worldForwardDirY','h',1,False),('m_worldForwardDirZ','h',1,False),
 ('m_worldRightDirX','h',1,False),('m_worldRightDirY','h',1,False),('m_worldRightDirZ','h',1,False),
 ('m_gForceLateral','h',1,False),('m_gForceLongitudinal','h',1,False),('m_gForceVertical','h',1,False),
 ('m_yaw','f',1,False),('m_pitch','f',1,False),('m_roll','f',1,False)])
@dataclass(frozen=True, slots=True)
class PacketMotionData: m_carMotionData: tuple[CarMotionData,...]
PacketMotionData_LAYOUT=Layout(PacketMotionData,[('m_carMotionData',CarMotionData_LAYOUT,24,True)])

@dataclass(frozen=True, slots=True)
class CarSetupData:
    m_frontWing:int; m_rearWing:int; m_onThrottle:int; m_offThrottle:int
    m_frontCamber:float; m_rearCamber:float; m_frontToe:float; m_rearToe:float
    m_frontSuspension:int; m_rearSuspension:int; m_frontAntiRollBar:int; m_rearAntiRollBar:int
    m_frontSuspensionHeight:int; m_rearSuspensionHeight:int; m_brakePressure:int; m_brakeBias:int; m_engineBraking:int
    m_rearLeftTyrePressure:float; m_rearRightTyrePressure:float; m_frontLeftTyrePressure:float; m_frontRightTyrePressure:float
    m_ballast:int; m_fuelLoad:float
CarSetupData_LAYOUT=Layout(CarSetupData,[
 ('m_frontWing','B',1,False),('m_rearWing','B',1,False),('m_onThrottle','B',1,False),('m_offThrottle','B',1,False),
 ('m_frontCamber','f',1,False),('m_rearCamber','f',1,False),('m_frontToe','f',1,False),('m_rearToe','f',1,False),
 ('m_frontSuspension','B',1,False),('m_rearSuspension','B',1,False),('m_frontAntiRollBar','B',1,False),('m_rearAntiRollBar','B',1,False),
 ('m_frontSuspensionHeight','B',1,False),('m_rearSuspensionHeight','B',1,False),('m_brakePressure','B',1,False),('m_brakeBias','B',1,False),('m_engineBraking','B',1,False),
 ('m_rearLeftTyrePressure','f',1,False),('m_rearRightTyrePressure','f',1,False),('m_frontLeftTyrePressure','f',1,False),('m_frontRightTyrePressure','f',1,False),
 ('m_ballast','B',1,False),('m_fuelLoad','f',1,False)])
@dataclass(frozen=True, slots=True)
class PacketCarSetupData: m_carSetupData:tuple[CarSetupData,...]; m_nextFrontWingValue:float
PacketCarSetupData_LAYOUT=Layout(PacketCarSetupData,[('m_carSetupData',CarSetupData_LAYOUT,24,True),('m_nextFrontWingValue','f',1,False)])

@dataclass(frozen=True, slots=True)
class FinalClassificationData:
    m_position:int; m_numLaps:int; m_gridPosition:int; m_points:int; m_numPitStops:int; m_resultStatus:int; m_resultReason:int
    m_bestLapTimeInMS:int; m_totalRaceTime:float; m_penaltiesTime:int; m_numPenalties:int; m_numTyreStints:int
    m_tyreStintsActual:tuple[int,...]; m_tyreStintsVisual:tuple[int,...]; m_tyreStintsEndLaps:tuple[int,...]
FinalClassificationData_LAYOUT=Layout(FinalClassificationData,[
 ('m_position','B',1,False),('m_numLaps','B',1,False),('m_gridPosition','B',1,False),('m_points','B',1,False),('m_numPitStops','B',1,False),('m_resultStatus','B',1,False),('m_resultReason','B',1,False),
 ('m_bestLapTimeInMS','I',1,False),('m_totalRaceTime','d',1,False),('m_penaltiesTime','B',1,False),('m_numPenalties','B',1,False),('m_numTyreStints','B',1,False),
 ('m_tyreStintsActual','B',8,True),('m_tyreStintsVisual','B',8,True),('m_tyreStintsEndLaps','B',8,True)])
@dataclass(frozen=True, slots=True)
class PacketFinalClassificationData: m_numCars:int; m_classificationData:tuple[FinalClassificationData,...]
PacketFinalClassificationData_LAYOUT=Layout(PacketFinalClassificationData,[('m_numCars','B',1,False),('m_classificationData',FinalClassificationData_LAYOUT,24,True)])

@dataclass(frozen=True, slots=True)
class LobbyInfoData:
    m_aiControlled:int; m_teamId:int; m_nationality:int; m_platform:int; m_name:str; m_carNumber:int; m_yourTelemetry:int; m_showOnlineNames:int; m_techLevel:int; m_readyStatus:int
LobbyInfoData_LAYOUT=Layout(LobbyInfoData,[('m_aiControlled','B',1,False),('m_teamId','H',1,False),('m_nationality','B',1,False),('m_platform','B',1,False),('m_name','32s',1,False),('m_carNumber','B',1,False),('m_yourTelemetry','B',1,False),('m_showOnlineNames','B',1,False),('m_techLevel','H',1,False),('m_readyStatus','B',1,False)])
@dataclass(frozen=True, slots=True)
class PacketLobbyInfoData: m_numPlayers:int; m_lobbyPlayers:tuple[LobbyInfoData,...]
PacketLobbyInfoData_LAYOUT=Layout(PacketLobbyInfoData,[('m_numPlayers','B',1,False),('m_lobbyPlayers',LobbyInfoData_LAYOUT,24,True)])

@dataclass(frozen=True, slots=True)
class LapHistoryData:
    m_lapTimeInMS:int; m_sector1TimeMSPart:int; m_sector1TimeMinutesPart:int; m_sector2TimeMSPart:int; m_sector2TimeMinutesPart:int; m_sector3TimeMSPart:int; m_sector3TimeMinutesPart:int; m_lapValidBitFlags:int
LapHistoryData_LAYOUT=Layout(LapHistoryData,[('m_lapTimeInMS','I',1,False),('m_sector1TimeMSPart','H',1,False),('m_sector1TimeMinutesPart','B',1,False),('m_sector2TimeMSPart','H',1,False),('m_sector2TimeMinutesPart','B',1,False),('m_sector3TimeMSPart','H',1,False),('m_sector3TimeMinutesPart','B',1,False),('m_lapValidBitFlags','B',1,False)])
@dataclass(frozen=True, slots=True)
class TyreStintHistoryData: m_endLap:int; m_tyreActualCompound:int; m_tyreVisualCompound:int
TyreStintHistoryData_LAYOUT=Layout(TyreStintHistoryData,[('m_endLap','B',1,False),('m_tyreActualCompound','B',1,False),('m_tyreVisualCompound','B',1,False)])
@dataclass(frozen=True, slots=True)
class PacketSessionHistoryData:
    m_carIdx:int; m_numLaps:int; m_numTyreStints:int; m_bestLapTimeLapNum:int; m_bestSector1LapNum:int; m_bestSector2LapNum:int; m_bestSector3LapNum:int
    m_lapHistoryData:tuple[LapHistoryData,...]; m_tyreStintsHistoryData:tuple[TyreStintHistoryData,...]
PacketSessionHistoryData_LAYOUT=Layout(PacketSessionHistoryData,[('m_carIdx','B',1,False),('m_numLaps','B',1,False),('m_numTyreStints','B',1,False),('m_bestLapTimeLapNum','B',1,False),('m_bestSector1LapNum','B',1,False),('m_bestSector2LapNum','B',1,False),('m_bestSector3LapNum','B',1,False),('m_lapHistoryData',LapHistoryData_LAYOUT,100,True),('m_tyreStintsHistoryData',TyreStintHistoryData_LAYOUT,8,True)])

@dataclass(frozen=True, slots=True)
class PacketMotionExData:
    m_suspensionPosition:tuple[float,...]; m_suspensionVelocity:tuple[float,...]; m_suspensionAcceleration:tuple[float,...]
    m_wheelSpeed:tuple[float,...]; m_wheelSlipRatio:tuple[float,...]; m_wheelSlipAngle:tuple[float,...]; m_wheelLatForce:tuple[float,...]; m_wheelLongForce:tuple[float,...]
    m_heightOfCOGAboveGround:float; m_localVelocityX:float; m_localVelocityY:float; m_localVelocityZ:float
    m_angularVelocityX:float; m_angularVelocityY:float; m_angularVelocityZ:float; m_angularAccelerationX:float; m_angularAccelerationY:float; m_angularAccelerationZ:float
    m_frontWheelsAngle:float; m_wheelVertForce:tuple[float,...]; m_frontAeroHeight:float; m_rearAeroHeight:float; m_frontRollAngle:float; m_rearRollAngle:float; m_chassisYaw:float; m_chassisPitch:float; m_wheelCamber:tuple[float,...]; m_wheelCamberGain:tuple[float,...]
PacketMotionExData_LAYOUT=Layout(PacketMotionExData,[
 ('m_suspensionPosition','f',4,True),('m_suspensionVelocity','f',4,True),('m_suspensionAcceleration','f',4,True),('m_wheelSpeed','f',4,True),('m_wheelSlipRatio','f',4,True),('m_wheelSlipAngle','f',4,True),('m_wheelLatForce','f',4,True),('m_wheelLongForce','f',4,True),
 ('m_heightOfCOGAboveGround','f',1,False),('m_localVelocityX','f',1,False),('m_localVelocityY','f',1,False),('m_localVelocityZ','f',1,False),('m_angularVelocityX','f',1,False),('m_angularVelocityY','f',1,False),('m_angularVelocityZ','f',1,False),('m_angularAccelerationX','f',1,False),('m_angularAccelerationY','f',1,False),('m_angularAccelerationZ','f',1,False),('m_frontWheelsAngle','f',1,False),('m_wheelVertForce','f',4,True),('m_frontAeroHeight','f',1,False),('m_rearAeroHeight','f',1,False),('m_frontRollAngle','f',1,False),('m_rearRollAngle','f',1,False),('m_chassisYaw','f',1,False),('m_chassisPitch','f',1,False),('m_wheelCamber','f',4,True),('m_wheelCamberGain','f',4,True)])

@dataclass(frozen=True, slots=True)
class TimeTrialDataSet:
    m_carIdx:int; m_teamId:int; m_lapTimeInMS:int; m_sector1TimeInMS:int; m_sector2TimeInMS:int; m_sector3TimeInMS:int; m_tractionControl:int; m_gearboxAssist:int; m_antiLockBrakes:int; m_equalCarPerformance:int; m_customSetup:int; m_valid:int
TimeTrialDataSet_LAYOUT=Layout(TimeTrialDataSet,[('m_carIdx','B',1,False),('m_teamId','H',1,False),('m_lapTimeInMS','I',1,False),('m_sector1TimeInMS','I',1,False),('m_sector2TimeInMS','I',1,False),('m_sector3TimeInMS','I',1,False),('m_tractionControl','B',1,False),('m_gearboxAssist','B',1,False),('m_antiLockBrakes','B',1,False),('m_equalCarPerformance','B',1,False),('m_customSetup','B',1,False),('m_valid','B',1,False)])
@dataclass(frozen=True, slots=True)
class PacketTimeTrialData: m_playerSessionBestDataSet:TimeTrialDataSet; m_personalBestDataSet:TimeTrialDataSet; m_rivalDataSet:TimeTrialDataSet
PacketTimeTrialData_LAYOUT=Layout(PacketTimeTrialData,[('m_playerSessionBestDataSet',TimeTrialDataSet_LAYOUT,1,False),('m_personalBestDataSet',TimeTrialDataSet_LAYOUT,1,False),('m_rivalDataSet',TimeTrialDataSet_LAYOUT,1,False)])

@dataclass(frozen=True, slots=True)
class PacketLapPositionsData: m_numLaps:int; m_lapStart:int; m_positionForVehicleIdx:tuple[int,...]
PacketLapPositionsData_LAYOUT=Layout(PacketLapPositionsData,[('m_numLaps','B',1,False),('m_lapStart','B',1,False),('m_positionForVehicleIdx','B',1200,True)])

LAYOUTS={0:PacketMotionData_LAYOUT,5:PacketCarSetupData_LAYOUT,8:PacketFinalClassificationData_LAYOUT,9:PacketLobbyInfoData_LAYOUT,11:PacketSessionHistoryData_LAYOUT,13:PacketMotionExData_LAYOUT,14:PacketTimeTrialData_LAYOUT,15:PacketLapPositionsData_LAYOUT}
PACKET_SIZES={0:1325,5:1233,8:1134,9:1062,11:1460,13:273,14:104,15:1231}
