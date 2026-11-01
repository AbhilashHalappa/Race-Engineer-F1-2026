#pragma once
#include <Arduino.h>
#include <stdint.h>
#include <string.h>

constexpr uint8_t PEDAL_SENSOR_MAGIC0 = 'L';
constexpr uint8_t PEDAL_SENSOR_MAGIC1 = 'C';
constexpr uint8_t PEDAL_SENSOR_STATUS_MAGIC1 = 'S';
constexpr uint8_t PEDAL_SENSOR_PROTOCOL_VERSION = 2;

enum class PedalSensorFrameKind : uint8_t { COMMAND = 1, STATUS = 2 };
enum class PedalSensorCommand : uint8_t {
    GET_STATUS=1,
    SET_CONFIG=2,
    TARE_THROTTLE=3,
    TARE_BRAKE=4,
    TARE_BOTH=5,
    CALIBRATE_THROTTLE=6,
    CALIBRATE_BRAKE=7,
    RESET_DEFAULTS=8,
    SET_THROTTLE_CONFIG=9,
    SET_BRAKE_CONFIG=10,
    SET_CLUTCH_CONFIG=11,
    TARE_CLUTCH=12,
    CALIBRATE_CLUTCH=13
};

enum class PedalSensorMode : uint8_t { ANALOG_INPUT=1, HX711=2 };
enum class PedalSensorResult : uint8_t { OK=0, BAD_FRAME=1, BAD_CONFIG=2, HX711_TIMEOUT=3, NO_LOAD=4, BAD_CALIBRATION_FORCE=5, UNSUPPORTED=6 };

struct __attribute__((packed)) PedalSensorFrame {
    uint8_t magic0, magic1, version;
    PedalSensorFrameKind kind;
    PedalSensorCommand command;
    uint16_t sequence;
    uint8_t throttleMode, brakeMode, clutchMode, flags;
    uint8_t throttleFilterDivisor, brakeFilterDivisor, clutchFilterDivisor;
    float throttleCapacityKg, brakeCapacityKg, clutchCapacityKg;
    float throttleMaxForceKg, brakeMaxForceKg, clutchMaxForceKg;
    float throttleCountsPerKg, brakeCountsPerKg, clutchCountsPerKg;
    float calibrationForceKg;
    PedalSensorResult result;
    int32_t throttleRawDelta, brakeRawDelta, clutchRawDelta;
    uint16_t throttleOutput, brakeOutput, clutchOutput;
    uint8_t crc;
};

inline uint8_t pedalSensorCrc8(const uint8_t* data, size_t length) {
    uint8_t crc=0;
    for(size_t i=0;i<length;++i){
        crc^=data[i];
        for(uint8_t b=0;b<8;++b)
            crc=(crc&0x80u)?static_cast<uint8_t>((crc<<1u)^0x07u):static_cast<uint8_t>(crc<<1u);
    }
    return crc;
}
inline void pedalSensorInitFrame(PedalSensorFrame& f, PedalSensorFrameKind kind, PedalSensorCommand command, uint16_t sequence) {
    memset(&f,0,sizeof(f));
    f.magic0=PEDAL_SENSOR_MAGIC0;
    f.magic1=(kind==PedalSensorFrameKind::STATUS)?PEDAL_SENSOR_STATUS_MAGIC1:PEDAL_SENSOR_MAGIC1;
    f.version=PEDAL_SENSOR_PROTOCOL_VERSION;
    f.kind=kind; f.command=command; f.sequence=sequence;
}
inline void pedalSensorSealFrame(PedalSensorFrame& f) { f.crc=pedalSensorCrc8(reinterpret_cast<const uint8_t*>(&f),sizeof(f)-1); }
inline bool pedalSensorValidateFrame(const PedalSensorFrame& f) {
    const uint8_t m=(f.kind==PedalSensorFrameKind::STATUS)?PEDAL_SENSOR_STATUS_MAGIC1:PEDAL_SENSOR_MAGIC1;
    return f.magic0==PEDAL_SENSOR_MAGIC0 && f.magic1==m && f.version==PEDAL_SENSOR_PROTOCOL_VERSION &&
           pedalSensorCrc8(reinterpret_cast<const uint8_t*>(&f),sizeof(f)-1)==f.crc;
}
static_assert(sizeof(PedalSensorFrame)==74,"Pedal sensor V2 frame size changed");
