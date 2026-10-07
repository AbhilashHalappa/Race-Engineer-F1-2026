/******************************************************************************
 * GamePad Pro V8
 * ESPNowManager.h
 *
 * ESP-NOW Manager
 * (Pedals ESP32-WROOM)
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
    //  • Sends pedal packet periodically
    //-------------------------------------------------------------------------

    void update();

    //-------------------------------------------------------------------------
    // Send Pedal Packet
    //-------------------------------------------------------------------------

    bool sendPedals(const PedalPayload& pedals);

    //-------------------------------------------------------------------------
    // Connection State
    //-------------------------------------------------------------------------

    bool receiverConnected();

    const PeerInfo& getReceiverState();

    //-------------------------------------------------------------------------
    // Statistics
    //-------------------------------------------------------------------------

    uint32_t pedalPackets();

    void printStatistics();

} // namespace ESPNow