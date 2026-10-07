/******************************************************************************
 * GamePad Pro V8
 * StatusLED.h
 ******************************************************************************/

#pragma once

#include <Arduino.h>

enum class SystemStatus : uint8_t
{
    BOOTING = 0,
    READY,
    CONNECTED,
    WAITING_WHEEL,
    WAITING_PEDALS,
    WAITING_MOTOR_TEMP,
    SIMHUB_LOST,
    ERROR
};

namespace StatusLED
{
    void begin();

    void update();

    void setStatus(SystemStatus status);

    SystemStatus getStatus();

    // Convenience functions
    void setBooting();
    void setReady();
    void setConnected();
    void setWaitingWheel();
    void setWaitingPedals();
    void setWaitingMotorTemp();
    void setSimHubLost();
    void setError();
}