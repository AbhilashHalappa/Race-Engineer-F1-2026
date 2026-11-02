#include "RpmLedController.h"
#include <Adafruit_NeoPixel.h>
#include "Config.h"
#include "Pins.h"

namespace
{
Adafruit_NeoPixel strip(LED_COUNT, LED_DATA_PIN, NEO_GRB + NEO_KHZ800);

uint32_t lastShiftFlashMs = 0;
bool shiftFlashOn = false;

uint8_t brightnessLevel = LED_BRIGHTNESS;
bool ledsEnabled = true;

// TEMPORARY GPIO TEST: treat the three EC11 connections as independent
// active-LOW push buttons. This isolates GPIO/button detection from quadrature.
struct TestButton
{
    uint8_t pin;
    bool rawState;
    bool stableState;
    uint32_t lastChangeMs;
};

TestButton brightnessDownButton = {BRIGHTNESS_ENCODER_A_PIN, HIGH, HIGH, 0};
TestButton brightnessUpButton   = {BRIGHTNESS_ENCODER_B_PIN, HIGH, HIGH, 0};
TestButton masterButton         = {LED_MASTER_TOGGLE_PIN, HIGH, HIGH, 0};

uint8_t lastRenderedRpm = 255;
bool lastRenderedShift = false;
bool lastRenderedFresh = false;
bool lastRenderedShiftFlash = false;
uint8_t lastRenderedBrightness = 0;
bool lastRenderedEnabled = false;

constexpr uint32_t BUTTON_DEBOUNCE_MS = 25;
constexpr uint8_t BRIGHTNESS_STEP = 10;
constexpr uint8_t MIN_BRIGHTNESS = 5;
constexpr uint8_t MAX_BRIGHTNESS = 255;

// Returns true once for each debounced press (not on release).
bool pressedEvent(TestButton &button, uint32_t now)
{
    const bool reading = digitalRead(button.pin);
    if (reading != button.rawState)
    {
        button.rawState = reading;
        button.lastChangeMs = now;
        Serial.printf("[RPM TEST] GPIO%u raw=%s\\n",
                      button.pin, reading == LOW ? "LOW" : "HIGH");
    }

    if ((now - button.lastChangeMs) >= BUTTON_DEBOUNCE_MS &&
        reading != button.stableState)
    {
        button.stableState = reading;
        if (button.stableState == LOW)
        {
            Serial.printf("[RPM TEST] GPIO%u PRESSED\\n", button.pin);
            return true;
        }
    }
    return false;
}

bool readLocalControls()
{
    bool changed = false;
    const uint32_t now = millis();

    if (pressedEvent(brightnessDownButton, now))
    {
        brightnessLevel = brightnessLevel > (MIN_BRIGHTNESS + BRIGHTNESS_STEP - 1)
            ? brightnessLevel - BRIGHTNESS_STEP : MIN_BRIGHTNESS;
        Serial.printf("[RPM TEST] Brightness DOWN: %u/255\\n", brightnessLevel);
        changed = true;
    }

    if (pressedEvent(brightnessUpButton, now))
    {
        const uint16_t next = static_cast<uint16_t>(brightnessLevel) + BRIGHTNESS_STEP;
        brightnessLevel = next > MAX_BRIGHTNESS ? MAX_BRIGHTNESS : static_cast<uint8_t>(next);
        Serial.printf("[RPM TEST] Brightness UP: %u/255\\n", brightnessLevel);
        changed = true;
    }

    if (pressedEvent(masterButton, now))
    {
        ledsEnabled = !ledsEnabled;
        Serial.printf("[RPM TEST] LEDs %s\\n", ledsEnabled ? "ON" : "OFF");
        changed = true;
    }

    return changed;
}

uint32_t colourForPosition(uint8_t positionPercent)
{
    if (positionPercent <= 50) return strip.Color(0, 180, 0);       // Green
    if (positionPercent <= 70) return strip.Color(255, 190, 0);     // Yellow
    if (positionPercent <= 85) return strip.Color(255, 75, 0);      // Orange
    return strip.Color(255, 0, 0);                                  // Red
}

void render(uint8_t rpm, bool shift, bool fresh)
{
    // Keep the original brighter disconnected-white mode, scaled by test brightness.
    uint16_t outputBrightness = brightnessLevel;
    if (!fresh) {
        outputBrightness = (static_cast<uint16_t>(brightnessLevel) *
                            DISCONNECTED_LED_BRIGHTNESS) / LED_BRIGHTNESS;
        if (outputBrightness > 255) outputBrightness = 255;
    }
    strip.setBrightness(static_cast<uint8_t>(outputBrightness));
    strip.clear();

    // Master OFF overrides RPM, shift flash, and disconnected white mode.
    if (!ledsEnabled)
    {
        strip.show();
        return;
    }

    // If the S3 receiver is absent or telemetry times out, show solid white.
    if (!fresh)
    {
        for (uint8_t i = 0; i < LED_COUNT; ++i)
            strip.setPixelColor(i, strip.Color(255, 255, 255));
    }
    else if (shift)
    {
        if (shiftFlashOn) {
            for (uint8_t i = 0; i < LED_COUNT; ++i)
                strip.setPixelColor(i, strip.Color(255, 255, 255));
        }
    }
    else
    {
        const uint8_t litPerSide = static_cast<uint8_t>((static_cast<uint16_t>(rpm) * 30u + 99u) / 100u);
        for (uint8_t i = 0; i < litPerSide; ++i)
        {
            const uint8_t positionPercent = static_cast<uint8_t>((static_cast<uint16_t>(i + 1) * 100u) / 30u);
            const uint32_t colour = colourForPosition(positionPercent);
            strip.setPixelColor(i, colour);
            strip.setPixelColor(LED_COUNT - 1 - i, colour);
        }
    }

    strip.show();
}
}

void RpmLedController::begin()
{
    pinMode(BRIGHTNESS_ENCODER_A_PIN, INPUT_PULLUP);
    pinMode(BRIGHTNESS_ENCODER_B_PIN, INPUT_PULLUP);
    pinMode(LED_MASTER_TOGGLE_PIN, INPUT_PULLUP);

    const uint32_t now = millis();
    brightnessDownButton.rawState = brightnessDownButton.stableState =
        digitalRead(BRIGHTNESS_ENCODER_A_PIN);
    brightnessUpButton.rawState = brightnessUpButton.stableState =
        digitalRead(BRIGHTNESS_ENCODER_B_PIN);
    masterButton.rawState = masterButton.stableState =
        digitalRead(LED_MASTER_TOGGLE_PIN);
    brightnessDownButton.lastChangeMs = now;
    brightnessUpButton.lastChangeMs = now;
    masterButton.lastChangeMs = now;

    Serial.printf("[RPM TEST] BUTTON DIAGNOSTIC V1.1.1\\n");
    Serial.printf("[RPM TEST] GPIO%u=Brightness DOWN, GPIO%u=Brightness UP, GPIO%u=Master ON/OFF\\n",
                  BRIGHTNESS_ENCODER_A_PIN, BRIGHTNESS_ENCODER_B_PIN, LED_MASTER_TOGGLE_PIN);
    Serial.printf("[RPM TEST] Initial levels: GPIO%u=%u GPIO%u=%u GPIO%u=%u\\n",
                  BRIGHTNESS_ENCODER_A_PIN, brightnessDownButton.stableState,
                  BRIGHTNESS_ENCODER_B_PIN, brightnessUpButton.stableState,
                  LED_MASTER_TOGGLE_PIN, masterButton.stableState);
    Serial.println("[RPM TEST] Hold each GPIO to GND for at least 1 second.");

    strip.begin();
    strip.setBrightness(LED_BRIGHTNESS);
    strip.clear();
    strip.show();
}

void RpmLedController::update(uint8_t rpmPercent, bool shiftLight, bool telemetryFresh)
{
    const bool controlsChanged = readLocalControls();
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

    if (controlsChanged || rpmPercent != lastRenderedRpm ||
        shiftLight != lastRenderedShift || telemetryFresh != lastRenderedFresh ||
        shiftFlashOn != lastRenderedShiftFlash || brightnessLevel != lastRenderedBrightness ||
        ledsEnabled != lastRenderedEnabled)
    {
        render(rpmPercent, shiftLight, telemetryFresh);
        lastRenderedRpm = rpmPercent;
        lastRenderedShift = shiftLight;
        lastRenderedFresh = telemetryFresh;
        lastRenderedShiftFlash = shiftFlashOn;
        lastRenderedBrightness = brightnessLevel;
        lastRenderedEnabled = ledsEnabled;
    }
}
