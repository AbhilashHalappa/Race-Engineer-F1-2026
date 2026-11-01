#pragma once
#include <Arduino.h>
#include "HandbrakeSensorProtocol.h"

namespace HandbrakeSensorBridge {
    void begin();
    void consumeSerialByte(uint8_t value);
    void update();
    void onHandbrakeFrame(const HandbrakeSensorFrame& frame);
}
