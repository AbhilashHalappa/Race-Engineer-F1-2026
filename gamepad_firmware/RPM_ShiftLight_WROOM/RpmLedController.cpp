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

// EC11 quadrature decoder. A full detent is four valid transitions.
uint8_t encoderPreviousState = 0;
int8_t encoderTransitionCount = 0;

bool switchRawState = HIGH;
bool switchStableState = HIGH;
uint32_t switchLastChangeMs = 0;

uint8_t lastRenderedRpm = 255;
bool lastRenderedShift = false;
bool lastRenderedFresh = false;
bool lastRenderedShiftFlash = false;
uint8_t lastRenderedBrightness = 0;
bool lastRenderedEnabled = false;

constexpr uint32_t SWITCH_DEBOUNCE_MS = 35;
constexpr uint8_t BRIGHTNESS_STEP = 10;
constexpr uint8_t MIN_BRIGHTNESS = 5;
constexpr uint8_t MAX_BRIGHTNESS = 255;

// Index: previous AB state (2 bits), followed by current AB state (2 bits).
// Values are +1/-1 for valid quadrature steps, 0 for invalid/no movement.
constexpr int8_t ENCODER_TRANSITIONS[16] = {
     0, -1,  1,  0,
     1,  0,  0, -1,
    -1,  0,  0,  1,
     0,  1, -1,  0
};

uint8_t readEncoderState()
{
    return static_cast<uint8_t>(
        (digitalRead(BRIGHTNESS_ENCODER_A_PIN) << 1) |
         digitalRead(BRIGHTNESS_ENCODER_B_PIN));
}

bool readLocalControls()
{
    bool changed = false;
    const uint8_t currentState = readEncoderState();

    if (currentState != encoderPreviousState)
    {
        const uint8_t index = static_cast<uint8_t>(
            (encoderPreviousState << 2) | currentState);
        encoderTransitionCount += ENCODER_TRANSITIONS[index];
        encoderPreviousState = currentState;

        if (encoderTransitionCount >= 4)
        {
            const uint16_t next = static_cast<uint16_t>(brightnessLevel) + BRIGHTNESS_STEP;
            brightnessLevel = next > MAX_BRIGHTNESS
                ? MAX_BRIGHTNESS : static_cast<uint8_t>(next);
            encoderTransitionCount = 0;
            changed = true;
        }
        else if (encoderTransitionCount <= -4)
        {
            brightnessLevel = brightnessLevel > (MIN_BRIGHTNESS + BRIGHTNESS_STEP - 1)
                ? brightnessLevel - BRIGHTNESS_STEP : MIN_BRIGHTNESS;
            encoderTransitionCount = 0;
            changed = true;
        }
    }

    const uint32_t now = millis();
    const bool switchReading = digitalRead(LED_MASTER_TOGGLE_PIN);

    if (switchReading != switchRawState)
    {
        switchRawState = switchReading;
        switchLastChangeMs = now;
    }

    if ((now - switchLastChangeMs) >= SWITCH_DEBOUNCE_MS &&
        switchReading != switchStableState)
    {
        switchStableState = switchReading;
        if (switchStableState == LOW)
        {
            ledsEnabled = !ledsEnabled;
            changed = true;
        }
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
    // Preserve the brighter disconnected-white mode, scaled by user brightness.
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

    encoderPreviousState = readEncoderState();
    encoderTransitionCount = 0;

    switchRawState = switchStableState = digitalRead(LED_MASTER_TOGGLE_PIN);
    switchLastChangeMs = millis();

    Serial.printf("[RPM CTRL] EC11 ready: A=GPIO%u B=GPIO%u SW=GPIO%u\n",
                  BRIGHTNESS_ENCODER_A_PIN,
                  BRIGHTNESS_ENCODER_B_PIN,
                  LED_MASTER_TOGGLE_PIN);

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
