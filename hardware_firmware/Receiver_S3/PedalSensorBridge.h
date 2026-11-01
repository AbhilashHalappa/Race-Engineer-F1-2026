#pragma once
#include <Arduino.h>
#include "PedalSensorProtocol.h"

namespace PedalSensorBridge {
    void begin();
    void consumeSerialByte(uint8_t value);
    void update();
    void onPedalFrame(const PedalSensorFrame& frame);
}
