/******************************************************************************
 * GamePad Pro V8
 * Dashboard.h
 *
 * Wheel Dashboard Manager
 ******************************************************************************/

#pragma once

#include <Arduino.h>

#include "Protocol.h"

namespace Dashboard
{
    //-------------------------------------------------------------------------
    // Initialize Dashboard
    //-------------------------------------------------------------------------

    bool begin();

    //-------------------------------------------------------------------------
    // Update Dashboard
    // Refreshes display and RPM LEDs
    //-------------------------------------------------------------------------

    void update();

    //-------------------------------------------------------------------------
    // Set Latest Dashboard Data
    // Called by ESPNowManager when a dashboard packet is received
    //-------------------------------------------------------------------------

    void setData(const WheelDashboardExtendedPayload& data);

    //-------------------------------------------------------------------------
    // Get Latest Dashboard Data
    //-------------------------------------------------------------------------

    const WheelDashboardExtendedPayload& getData();

} // namespace Dashboard