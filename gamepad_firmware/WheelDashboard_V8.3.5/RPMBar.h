/******************************************************************************
 * GamePad Pro V8
 * RPMBar.h
 ******************************************************************************/

#pragma once

#include <Arduino.h>

#include "Protocol.h"

namespace RPMBar
{
    bool begin();

    void update();

    void setDashboardData(const WheelDashboardExtendedPayload& data);
}