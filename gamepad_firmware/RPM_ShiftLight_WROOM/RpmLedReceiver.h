#pragma once
#include <Arduino.h>
#include <esp_now.h>
#include "RpmLedProtocol.h"

namespace RpmLedReceiver
{
    void onReceive(const esp_now_recv_info_t* info, const uint8_t* data, int len);
    void update();
    uint8_t rpmPercent();
    bool shiftLight();
    bool hasFreshData();
}
