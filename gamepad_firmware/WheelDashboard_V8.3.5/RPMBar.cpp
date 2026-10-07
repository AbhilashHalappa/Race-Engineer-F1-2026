/******************************************************************************
 * GamePad Pro V8
 * RPMBar.cpp — 14-LED wheel light bar
 *
 * LED 1-8   RPM
 * LED 9     DRS
 * LED 10    Motor temperature (from ESP32-C3 10K NTC via receiver)
 * LED 11    ERS mode
 * LED 12    Flag
 * LED 13    Low fuel
 * LED 14    Low ERS energy
 ******************************************************************************/

#include "RPMBar.h"

#include <FastLED.h>

#include "Config.h"
#include "Pins.h"

namespace
{

CRGB leds[WHEEL_LED_COUNT];
WheelDashboardExtendedPayload dashboard = {};

const CRGB OFF     = CRGB::Black;
const CRGB GREEN   = CRGB(0, 255, 0);
const CRGB YELLOW  = CRGB(255, 180, 0);
const CRGB ORANGE  = CRGB(255, 80, 0);
const CRGB RED     = CRGB(255, 0, 0);
const CRGB BLUE    = CRGB(0, 0, 255);
const CRGB CYAN    = CRGB(0, 220, 255);
const CRGB PURPLE  = CRGB(180, 0, 255);
const CRGB WHITE   = CRGB(255, 255, 255);

CRGB getFlagColor(uint8_t flag)
{
    switch (flag)
    {
        case 1: return BLUE;
        case 2: return RED;
        case 3: return GREEN;
        case 4: return OFF;
        case 5: return YELLOW;
        case 6: return WHITE;
        case 7: return PURPLE;
        default: return OFF;
    }
}

CRGB getERSColor(uint8_t ersMode)
{
    switch (ersMode)
    {
        case 1: return GREEN;    // Balanced
        case 2: return RED;      // Hotlap
        case 3: return PURPLE;   // Overtake
        default: return OFF;
    }
}

CRGB getRPMColor(uint8_t rpmLedIndex)
{
    const uint8_t pct = static_cast<uint8_t>(
        (static_cast<uint16_t>(rpmLedIndex + 1) * 100u) / RPM_BAR_LED_COUNT);

    if (pct <= RPM_GREEN_END)
        return GREEN;
    if (pct <= RPM_YELLOW_END)
        return YELLOW;
    return RED;
}

bool flashOn()
{
    return ((millis() / SHIFT_FLASH_PERIOD_MS) & 1u) != 0;
}

} // namespace

bool RPMBar::begin()
{
    FastLED.addLeds<WS2812B, RPM_LED_PIN, GRB>(leds, WHEEL_LED_COUNT);
    FastLED.setBrightness(RPM_LED_BRIGHTNESS);
    FastLED.clear(true);
    return true;
}

void RPMBar::setDashboardData(const WheelDashboardExtendedPayload& data)
{
    dashboard = data;
}

void RPMBar::update()
{
    FastLED.clear();

    //-------------------------------------------------------------
    // MOTOR OVER-TEMPERATURE OVERRIDE
    //-------------------------------------------------------------
    // 80..89.99 C: every available wheel LED solid red.
    // >=90 C      : every available wheel LED flashes red.
    //
    // This deliberately overrides RPM/DRS/ERS/flag indications so the driver
    // gets an unmistakable stop-driving warning. Lower temperature bands keep
    // the original single LED 10 behaviour unchanged.

    const int16_t motorTempCx100 = dashboard.motorTempCx100;
    if (motorTempCx100 != MOTOR_TEMP_INVALID_CX100 && motorTempCx100 >= 8000)
    {
        const bool showRed = motorTempCx100 < 9000 || flashOn();
        if (showRed)
        {
            for (uint8_t i = 0; i < WHEEL_LED_COUNT; ++i)
            {
                leds[i] = RED;
            }
        }
        FastLED.show();
        return;
    }

    //-------------------------------------------------------------
    // LED 1-8: RPM / shift flash
    //-------------------------------------------------------------

    if (dashboard.shiftLight)
    {
        if (flashOn())
        {
            for (uint8_t i = 0; i < RPM_BAR_LED_COUNT; i++)
            {
                leds[LED_RPM_FIRST + i] = WHITE;
            }
        }
    }
    else
    {
        const uint8_t lit = static_cast<uint8_t>(map(
            constrain(dashboard.rpmPercent, 0, 100),
            0,
            100,
            0,
            RPM_BAR_LED_COUNT));

        for (uint8_t i = 0; i < lit; i++)
        {
            leds[LED_RPM_FIRST + i] = getRPMColor(i);
        }
    }

    //-------------------------------------------------------------
    // LED 9: DRS (SimHub: 2=available red, 3=active green, 0=off)
    //-------------------------------------------------------------

    {
        const uint8_t drs = WheelStatusBits::getDrs(dashboard.statusBits);

        if (drs == WheelStatusBits::DRS_AVAILABLE)
        {
            leds[LED_DRS] = RED;
        }
        else if (drs == WheelStatusBits::DRS_ACTIVE)
        {
            leds[LED_DRS] = GREEN;
        }
    }

    //-------------------------------------------------------------
    // LED 10: Motor temperature
    // Raw value comes from C3 -> receiver -> wheel.
    // Thresholds are intentionally owned by the wheel firmware.
    //-------------------------------------------------------------

    {
        const int16_t tempCx100 = dashboard.motorTempCx100;

        if (tempCx100 != MOTOR_TEMP_INVALID_CX100)
        {
            if (tempCx100 < 4000)
            {
                leds[LED_MOTOR_TEMP] = BLUE;          // < 40 C
            }
            else if (tempCx100 < 5500)
            {
                leds[LED_MOTOR_TEMP] = GREEN;         // 40 .. <55 C
            }
            else if (tempCx100 < 7000)
            {
                leds[LED_MOTOR_TEMP] = YELLOW;        // 55 .. <70 C
            }
            else if (tempCx100 < 8000)
            {
                leds[LED_MOTOR_TEMP] = ORANGE;        // 70 .. <80 C
            }
            // >=80 C is handled by the all-LED emergency override above.
        }
        // Invalid/stale temperature stays OFF because FastLED.clear() ran above.
    }

    //-------------------------------------------------------------
    // LED 11: ERS mode
    //-------------------------------------------------------------

    leds[LED_ERS_MODE] = getERSColor(dashboard.ersMode);

    //-------------------------------------------------------------
    // LED 12: Flag
    //-------------------------------------------------------------

    leds[LED_FLAG] = getFlagColor(dashboard.flagStatus);

    //-------------------------------------------------------------
    // LED 13: Low fuel (flash orange)
    //-------------------------------------------------------------

    if ((dashboard.statusBits & WheelStatusBits::LOW_FUEL) && flashOn())
    {
        leds[LED_LOW_FUEL] = ORANGE;
    }

    //-------------------------------------------------------------
    // LED 14: Low ERS energy
    //-------------------------------------------------------------

    if (dashboard.statusBits & WheelStatusBits::LOW_ERS)
    {
        leds[LED_LOW_ERS] = PURPLE;
    }

    FastLED.show();
}
