#include "RpmLedController.h"
#include <Adafruit_NeoPixel.h>
#include "Config.h"
#include "Pins.h"

namespace
{
Adafruit_NeoPixel strip(LED_COUNT, LED_DATA_PIN, NEO_GRB + NEO_KHZ800);
uint32_t lastShiftFlashMs = 0;
bool shiftFlashOn = false;
uint8_t lastRenderedRpm = 255;
bool lastRenderedShift = false;
bool lastRenderedFresh = false;
bool lastRenderedShiftFlash = false;

uint32_t colourForPosition(uint8_t positionPercent)
{
    if (positionPercent <= 50) return strip.Color(0, 180, 0);       // Green
    if (positionPercent <= 70) return strip.Color(255, 190, 0);     // Yellow
    if (positionPercent <= 85) return strip.Color(255, 75, 0);      // Orange
    return strip.Color(255, 0, 0);                                  // Red
}

void render(uint8_t rpm, bool shift, bool fresh)
{
    // Keep RPM/shift mode at its normal level, but make disconnected white
    // lighting run at 80% brightness (204/255).
    strip.setBrightness(fresh ? LED_BRIGHTNESS : DISCONNECTED_LED_BRIGHTNESS);
    strip.clear();

    // Fail-safe lighting mode: if the S3 receiver is absent or telemetry times out,
    // illuminate the entire strip white so it remains usable as a normal light.
    if (!fresh)
    {
        for (uint8_t i = 0; i < LED_COUNT; ++i)
            strip.setPixelColor(i, strip.Color(255, 255, 255));
    }
    else if (shift && fresh)
    {
        if (shiftFlashOn) {
            for (uint8_t i = 0; i < LED_COUNT; ++i) strip.setPixelColor(i, strip.Color(255, 255, 255));
        }
    }
    else
    {
        const uint8_t litPerSide = static_cast<uint8_t>((static_cast<uint16_t>(rpm) * 30u + 99u) / 100u);
        for (uint8_t i = 0; i < litPerSide; ++i)
        {
            const uint8_t positionPercent = static_cast<uint8_t>((static_cast<uint16_t>(i + 1) * 100u) / 30u);
            const uint32_t colour = colourForPosition(positionPercent);
            strip.setPixelColor(i, colour);                  // Left: outside -> centre
            strip.setPixelColor(LED_COUNT - 1 - i, colour);  // Right: outside -> centre
        }
    }

    strip.show();
}
}

void RpmLedController::begin()
{
    strip.begin();
    strip.setBrightness(LED_BRIGHTNESS);
    strip.clear();
    strip.show();
}

void RpmLedController::update(uint8_t rpmPercent, bool shiftLight, bool telemetryFresh)
{
    const uint32_t now = millis();
    if (shiftLight && telemetryFresh && (now - lastShiftFlashMs >= SHIFT_FLASH_PERIOD_MS))
    {
        lastShiftFlashMs = now;
        shiftFlashOn = !shiftFlashOn;
    }
    else if (!shiftLight || !telemetryFresh)
    {
        shiftFlashOn = false;
    }

    if (rpmPercent != lastRenderedRpm || shiftLight != lastRenderedShift ||
        telemetryFresh != lastRenderedFresh || shiftFlashOn != lastRenderedShiftFlash)
    {
        render(rpmPercent, shiftLight, telemetryFresh);
        lastRenderedRpm = rpmPercent;
        lastRenderedShift = shiftLight;
        lastRenderedFresh = telemetryFresh;
        lastRenderedShiftFlash = shiftFlashOn;
    }
}
