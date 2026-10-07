#pragma once

#include <Arduino.h>
#include <stdint.h>

namespace PedalCalibration
{
    struct AxisSettings
    {
        uint8_t bottomDeadzonePercent;
        uint8_t topDeadzonePercent;
        uint8_t outputPercent[6]; // fixed input points: 0,20,40,60,80,100%
    };

    struct Settings
    {
        AxisSettings throttle;
        AxisSettings brake;
        AxisSettings clutch;
        AxisSettings handbrake;
        uint8_t clutchEnabled;
        uint8_t handbrakeEnabled;
    };

    void begin();
    void consumeSerialByte(uint8_t value);

    uint16_t applyThrottle(uint16_t raw);
    uint16_t applyBrake(uint16_t raw);
    uint16_t applyClutch(uint16_t raw);
    uint16_t applyHandbrake(uint16_t raw);
    bool clutchEnabled();
    bool handbrakeEnabled();

    const Settings& getSettings();
}
