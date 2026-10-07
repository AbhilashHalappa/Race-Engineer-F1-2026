/******************************************************************************
 * GamePad Pro V8
 * ESPNowManager.h
 *
 * ESP-NOW Manager
 * (Wheel ESP32-WROOM)
 ******************************************************************************/

#pragma once

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>

#include "Protocol.h"
#include "GameNetwork.h"

namespace ESPNow
{
    //-------------------------------------------------------------------------
    // Initialize ESP-NOW
    //-------------------------------------------------------------------------

    bool begin();

    //-------------------------------------------------------------------------
    // Update ESP-NOW
    //
    //  • Checks receiver timeout
    //  • Sends wheel packet periodically
    //-------------------------------------------------------------------------

    void update();

    //-------------------------------------------------------------------------
    // Send Wheel Packet
    //-------------------------------------------------------------------------

    bool sendWheel(const WheelPayload& wheel);

    //-------------------------------------------------------------------------
    // Dashboard Data
    //-------------------------------------------------------------------------

    const WheelDashboardExtendedPayload& getDashboardData();

    //-------------------------------------------------------------------------
    // Connection State
    //-------------------------------------------------------------------------

    bool receiverConnected();

    const PeerInfo& getReceiverState();

    //-------------------------------------------------------------------------
    // Statistics
    //-------------------------------------------------------------------------

    uint32_t wheelPackets();

    uint32_t dashboardPackets();

    void printStatistics();

} // namespace ESPNow