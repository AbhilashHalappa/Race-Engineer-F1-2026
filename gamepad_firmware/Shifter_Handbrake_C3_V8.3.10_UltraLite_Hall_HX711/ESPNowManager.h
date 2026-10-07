#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include "Protocol.h"

namespace ESPNow
{
    bool begin();
    void update();
    bool sendShifter(const ShifterPayload& shifter);
    uint32_t packetsSent();
    uint32_t sendFailures();
}
