/******************************************************************************
 * GamePad Pro V8
 * Gamepad.h
 ******************************************************************************/

#pragma once

#include <Arduino.h>
#include "USB.h"
#include "USBHIDGamepad.h"

#include "Protocol.h"

namespace Gamepad
{
    void begin();

    void update();

    void setWheelData(const WheelPayload& data);

    void setPedalData(const PedalPayload& data);

    void setShifterData(const ShifterPayload& data);
}
