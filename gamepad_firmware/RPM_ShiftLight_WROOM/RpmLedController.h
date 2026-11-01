#pragma once
#include <Arduino.h>

namespace RpmLedController
{
    void begin();
    void update(uint8_t rpmPercent, bool shiftLight, bool telemetryFresh);
}
