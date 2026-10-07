/******************************************************************************
 * GamePad Pro V8
 * ESPNowManager.h
 *
 * ESP-NOW Communication Manager
 ******************************************************************************/

#pragma once

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>

#include "Protocol.h"
#include "GameNetwork.h"

namespace ESPNow
{
    //=========================================================================
    // Initialization
    //=========================================================================

    // Initialize WiFi + ESP-NOW + Register Peers
    bool begin();

    // Process communication, timeouts and dashboard updates
    void update();

    //=========================================================================
    // Dashboard
    //=========================================================================

    // Send latest dashboard telemetry to Wheel ESP32
    bool sendDashboard(const WheelDashboardPayload &dashboard);

    //=========================================================================
    // Latest Received Data
    //=========================================================================

    const WheelPayload& getWheelData();

    const PedalPayload& getPedalData();

    const MotorTempPayload& getMotorTempData();

    const ShifterPayload& getShifterData();

    //=========================================================================
    // Connection Status
    //=========================================================================

    bool wheelConnected();

    bool pedalsConnected();

    bool motorTempConnected();

    bool shifterConnected();

    bool allConnected();

    //=========================================================================
    // Network State
    //=========================================================================

    const ReceiverNetworkState& getNetworkState();

    //=========================================================================
    // Statistics
    //=========================================================================

    uint32_t wheelPackets();

    uint32_t pedalPackets();

    uint32_t motorTempPackets();

    uint32_t shifterPackets();

    uint32_t dashboardPackets();

    //=========================================================================
    // Debug
    //=========================================================================

    void printStatistics();
}