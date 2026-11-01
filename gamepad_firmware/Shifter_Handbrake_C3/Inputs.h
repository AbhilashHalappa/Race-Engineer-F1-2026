#pragma once
#include <Arduino.h>
#include "Protocol.h"
#include "HandbrakeSensorProtocol.h"

namespace Inputs
{
    bool begin();
    void update();
    bool handleCommand(const HandbrakeSensorFrame& command, HandbrakeSensorFrame& response);
    const ShifterPayload& getShifterData();
}
