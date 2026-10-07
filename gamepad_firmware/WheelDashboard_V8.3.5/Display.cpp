/******************************************************************************
 * GamePad Pro V8
 * Display.cpp
 ******************************************************************************/

#include "Display.h"

#include <LedController.hpp>

#include "Config.h"
#include "Pins.h"

namespace
{
    LedController<1, 1> display;
    WheelDashboardExtendedPayload dashboard = {};
}

bool Display::begin()
{
    display.init(MAX7219_DIN_PIN, MAX7219_CLK_PIN, MAX7219_CS_PIN);
    display.setIntensity(DISPLAY_BRIGHTNESS);

    return true;
}

void Display::setDashboardData(const WheelDashboardExtendedPayload& data)
{
    dashboard = data;
}

void Display::update()
{
    uint16_t speed = dashboard.speed;

    if (speed > 999)
        speed = 999;

    uint8_t position = dashboard.position;

    if (position > 99)
        position = 99;

    for (uint8_t i = 0; i < 8; i++)
    {
        display.setChar(0, i, ' ', false);
    }

    //---------------------------------------------------------------------
    // Speed: digits 7,6,5
    // Digit 4 blank separator
    //---------------------------------------------------------------------

    display.setDigit(0, 7, (speed / 100) % 10, false);
    display.setDigit(0, 6, (speed / 10) % 10, false);
    display.setDigit(0, 5, speed % 10, false);

    display.setChar(0, 4, ' ', false);

    //---------------------------------------------------------------------
    // Gear: digits 3,2
    //---------------------------------------------------------------------

    if (dashboard.gear == 0)
    {
        display.setDigit(0, 3, 0, false);
        display.setDigit(0, 2, 0, true);
    }
    else if (dashboard.gear == -1)
    {
        display.setChar(0, 3, '-', false);
        display.setDigit(0, 2, 1, true);
    }
    else
    {
        uint8_t gear = dashboard.gear;

        if (gear > 99)
            gear = 99;

        display.setDigit(0, 3, (gear / 10) % 10, false);
        display.setDigit(0, 2, gear % 10, true);
    }

    //---------------------------------------------------------------------
    // Position: digits 1,0
    //---------------------------------------------------------------------

    display.setDigit(0, 1, (position / 10) % 10, false);
    display.setDigit(0, 0, position % 10, false);
}