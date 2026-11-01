#pragma once
#include <Arduino.h>
#include <stdint.h>

constexpr uint16_t RPM_LED_MAGIC = 0x524C;
constexpr uint8_t RPM_LED_VERSION = 1;

struct __attribute__((packed)) RpmLedFrame
{
    uint16_t magic;
    uint8_t version;
    uint16_t sequence;
    uint8_t rpmPercent;
    uint8_t shiftLight;
    uint8_t checksum;
};

inline uint8_t rpmLedChecksum(const RpmLedFrame& frame)
{
    const uint8_t* bytes = reinterpret_cast<const uint8_t*>(&frame);
    uint8_t value = 0xA7;
    for (size_t i = 0; i < sizeof(RpmLedFrame) - 1; ++i) value ^= bytes[i];
    return value;
}

inline bool rpmLedValidate(const RpmLedFrame& frame)
{
    return frame.magic == RPM_LED_MAGIC &&
           frame.version == RPM_LED_VERSION &&
           frame.rpmPercent <= 100 &&
           frame.checksum == rpmLedChecksum(frame);
}
