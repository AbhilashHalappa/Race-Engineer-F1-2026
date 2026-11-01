#pragma once
#include <Arduino.h>
#include <stdint.h>
#include <string.h>

constexpr uint8_t HANDBRAKE_SENSOR_MAGIC0 = 'H';
constexpr uint8_t HANDBRAKE_SENSOR_MAGIC1 = 'B';
constexpr uint8_t HANDBRAKE_SENSOR_STATUS_MAGIC1 = 'S';
constexpr uint8_t HANDBRAKE_SENSOR_PROTOCOL_VERSION = 1;

enum class HandbrakeSensorFrameKind : uint8_t { COMMAND = 1, STATUS = 2 };
enum class HandbrakeSensorCommand : uint8_t { GET_STATUS = 1, SET_CONFIG = 2, TARE = 3, CALIBRATE = 4, RESET_DEFAULTS = 5 };
enum class HandbrakeSensorMode : uint8_t { HALL = 1, HX711 = 2 };
enum class HandbrakeSensorResult : uint8_t { OK = 0, BAD_FRAME = 1, BAD_CONFIG = 2, HX711_TIMEOUT = 3, NO_LOAD = 4, BAD_CALIBRATION_FORCE = 5, UNSUPPORTED = 6, PERSISTENCE_ERROR = 7 };

struct __attribute__((packed)) HandbrakeSensorFrame {
    uint8_t magic0, magic1, version;
    HandbrakeSensorFrameKind kind;
    HandbrakeSensorCommand command;
    uint16_t sequence;
    HandbrakeSensorMode mode;
    uint8_t filterDivisor;
    uint8_t flags;
    float capacityKg;
    float maxForceKg;
    float countsPerKg;
    float calibrationForceKg;
    HandbrakeSensorResult result;
    int32_t rawDelta;
    uint16_t output;
    uint8_t crc;
};

inline uint8_t handbrakeSensorCrc8(const uint8_t* data, size_t length) {
    uint8_t crc = 0;
    for (size_t i = 0; i < length; ++i) {
        crc ^= data[i];
        for (uint8_t b = 0; b < 8; ++b)
            crc = (crc & 0x80u) ? static_cast<uint8_t>((crc << 1u) ^ 0x07u) : static_cast<uint8_t>(crc << 1u);
    }
    return crc;
}

inline void handbrakeSensorInitFrame(HandbrakeSensorFrame& frame, HandbrakeSensorFrameKind kind, HandbrakeSensorCommand command, uint16_t sequence) {
    memset(&frame, 0, sizeof(frame));
    frame.magic0 = HANDBRAKE_SENSOR_MAGIC0;
    frame.magic1 = kind == HandbrakeSensorFrameKind::STATUS ? HANDBRAKE_SENSOR_STATUS_MAGIC1 : HANDBRAKE_SENSOR_MAGIC1;
    frame.version = HANDBRAKE_SENSOR_PROTOCOL_VERSION;
    frame.kind = kind;
    frame.command = command;
    frame.sequence = sequence;
}

inline void handbrakeSensorSealFrame(HandbrakeSensorFrame& frame) {
    frame.crc = handbrakeSensorCrc8(reinterpret_cast<const uint8_t*>(&frame), sizeof(frame) - 1);
}

inline bool handbrakeSensorValidateFrame(const HandbrakeSensorFrame& frame) {
    const uint8_t expectedMagic1 = frame.kind == HandbrakeSensorFrameKind::STATUS ? HANDBRAKE_SENSOR_STATUS_MAGIC1 : HANDBRAKE_SENSOR_MAGIC1;
    return frame.magic0 == HANDBRAKE_SENSOR_MAGIC0 && frame.magic1 == expectedMagic1 && frame.version == HANDBRAKE_SENSOR_PROTOCOL_VERSION &&
           handbrakeSensorCrc8(reinterpret_cast<const uint8_t*>(&frame), sizeof(frame) - 1) == frame.crc;
}

static_assert(sizeof(HandbrakeSensorFrame) == 34, "Handbrake sensor frame size mismatch");
