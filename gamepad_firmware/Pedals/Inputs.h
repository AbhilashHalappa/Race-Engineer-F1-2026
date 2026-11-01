#pragma once
#include <Arduino.h>
#include "Protocol.h"
#include "PedalSensorProtocol.h"

namespace Inputs {
    bool begin();
    void update();
    const PedalPayload& getPedalData();

    // Called from the main loop, never from the ESP-NOW callback.
    bool processSensorCommand(const PedalSensorFrame& command, PedalSensorFrame& response);
    void getSensorStatus(PedalSensorFrame& response, PedalSensorResult result = PedalSensorResult::OK);
}
