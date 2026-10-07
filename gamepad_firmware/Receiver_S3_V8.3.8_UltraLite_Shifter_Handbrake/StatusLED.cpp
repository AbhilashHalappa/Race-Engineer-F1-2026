/******************************************************************************
 * GamePad Pro V8
 * StatusLED.cpp
 ******************************************************************************/

#include "StatusLED.h"

#include <Adafruit_NeoPixel.h>

#include "Pins.h"
#include "Config.h"

namespace
{
    Adafruit_NeoPixel led(1, STATUS_LED_PIN, NEO_GRB + NEO_KHZ800);

    SystemStatus currentStatus = SystemStatus::BOOTING;
    SystemStatus shownStatus = SystemStatus::BOOTING;

    bool statusDirty = true;
    bool hasShownStatus = false;
    uint32_t lastRefresh = 0;
}

//=============================================================================

void StatusLED::begin()
{
#if ENABLE_STATUS_LED
    led.begin();
    led.setBrightness(40);
    led.clear();
    led.show();

    setBooting();
#endif
}

//=============================================================================

void StatusLED::update()
{
#if ENABLE_STATUS_LED
    if (!statusDirty)
    {
        return;
    }

    const uint32_t now = millis();

    if (hasShownStatus &&
        (now - lastRefresh) < STATUS_LED_REFRESH_MS)
    {
        return;
    }

    uint32_t color = 0;

    switch (currentStatus)
    {
        case SystemStatus::BOOTING:
            color = led.Color(0, 0, 255);
            break;

        case SystemStatus::READY:
            color = led.Color(0, 255, 255);
            break;

        case SystemStatus::CONNECTED:
            color = led.Color(0, 255, 0);
            break;

        case SystemStatus::WAITING_WHEEL:
            color = led.Color(255, 255, 0);
            break;

        case SystemStatus::WAITING_PEDALS:
            color = led.Color(255, 120, 0);
            break;

        case SystemStatus::WAITING_MOTOR_TEMP:
            color = led.Color(180, 0, 255);
            break;

        case SystemStatus::SIMHUB_LOST:
            color = led.Color(180, 0, 255);
            break;

        case SystemStatus::ERROR:
            color = led.Color(255, 0, 0);
            break;
    }

    led.setPixelColor(0, color);
    led.show();

    shownStatus = currentStatus;
    statusDirty = false;
    hasShownStatus = true;
    lastRefresh = now;
#endif
}

//=============================================================================

void StatusLED::setStatus(SystemStatus status)
{
    if (currentStatus == status)
    {
        return;
    }

    currentStatus = status;
    statusDirty = !hasShownStatus || shownStatus != currentStatus;
}

//=============================================================================

SystemStatus StatusLED::getStatus()
{
    return currentStatus;
}

//=============================================================================

void StatusLED::setBooting()
{
    setStatus(SystemStatus::BOOTING);
}

void StatusLED::setReady()
{
    setStatus(SystemStatus::READY);
}

void StatusLED::setConnected()
{
    setStatus(SystemStatus::CONNECTED);
}

void StatusLED::setWaitingWheel()
{
    setStatus(SystemStatus::WAITING_WHEEL);
}

void StatusLED::setWaitingPedals()
{
    setStatus(SystemStatus::WAITING_PEDALS);
}

void StatusLED::setWaitingMotorTemp()
{
    setStatus(SystemStatus::WAITING_MOTOR_TEMP);
}

void StatusLED::setSimHubLost()
{
    setStatus(SystemStatus::SIMHUB_LOST);
}

void StatusLED::setError()
{
    setStatus(SystemStatus::ERROR);
}
