#pragma once
#include <Arduino.h>
#include "PedalSensorProtocol.h"

namespace PedalSensorBridge {
    void begin();
    void consumeSerialByte(uint8_t value);
    void update();
    // Called from the ESP-NOW receive callback; only queues the frame.
    void onPedalFrame(const PedalSensorFrame& frame);
}
