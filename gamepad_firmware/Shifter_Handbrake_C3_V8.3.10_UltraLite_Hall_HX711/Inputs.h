#pragma once
#include <Arduino.h>
#include "Protocol.h"

namespace Inputs
{
    bool begin();
    void update();
    const ShifterPayload& getShifterData();
}
