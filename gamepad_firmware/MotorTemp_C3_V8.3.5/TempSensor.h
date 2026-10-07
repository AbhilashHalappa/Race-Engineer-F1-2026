/******************************************************************************
 * GamePad Pro V8
 * TempSensor.h
 ******************************************************************************/

#pragma once

#include "Protocol.h"

namespace TempSensor
{
    bool begin();
    void update();
    MotorTempPayload getPayload();
}
