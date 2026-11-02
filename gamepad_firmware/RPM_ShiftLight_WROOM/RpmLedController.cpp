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

uint8_t encoderPreviousState = 0;
int8_t encoderTransitionCount = 0;
uint8_t lastDebugEncoderState = 0xFF;
bool lastButtonReading = HIGH;
bool lastDebugButtonReading = HIGH;
bool stableButtonState = HIGH;
uint32_t lastButtonChangeMs = 0;

uint8_t lastRenderedRpm = 255;
bool lastRenderedShift = false;
bool lastRenderedFresh = false;
bool lastRenderedShiftFlash = false;
uint8_t lastRenderedBrightness = 0;
bool lastRenderedEnabled = false;

constexpr uint32_t BUTTON_DEBOUNCE_MS = 35;
constexpr uint8_t BRIGHTNESS_STEP = 10;
constexpr uint8_t MIN_BRIGHTNESS = 5;
constexpr uint8_t MAX_BRIGHTNESS = 255;

// Quadrature transition decoder. A complete detent produces +4 or -4.
int8_t encoderStep(uint8_t previous, uint8_t current)
{
    static const int8_t table[16] = {
         0, -1,  1,  0,
         1,  0,  0, -1,
        -1,  0,  0,  1,
         0,  1, -1,  0
    };
    return table[(previous << 2) | current];
}

bool readLocalControls()
{
    bool changed = false;

    const uint8_t encoderState =
        (digitalRead(BRIGHTNESS_ENCODER_A_PIN) ? 0x02 : 0x00) |
        (digitalRead(BRIGHTNESS_ENCODER_B_PIN) ? 0x01 : 0x00);

    // Report every raw encoder transition so wiring and GPIO input levels can
    // be verified independently of the brightness decoder.
    if (encoderState != lastDebugEncoderState) {
        Serial.printf("[RPM CTRL] Encoder A=%u B=%u state=%u\\n",
                      (encoderState & 0x02) ? 1U : 0U,
                      (encoderState & 0x01) ? 1U : 0U,
                      encoderState);
        lastDebugEncoderState = encoderState;
    }

    encoderTransitionCount += encoderStep(encoderPreviousState, encoderState);
    encoderPreviousState = encoderState;

    if (encoderTransitionCount >= 4)
    {
        encoderTransitionCount = 0;
        const uint16_t next = static_cast<uint16_t>(brightnessLevel) + BRIGHTNESS_STEP;
        const uint8_t value = next > MAX_BRIGHTNESS ? MAX_BRIGHTNESS : static_cast<uint8_t>(next);
        if (value != brightnessLevel) {
            brightnessLevel = value;
            changed = true;
        }
    }
    else if (encoderTransitionCount <= -4)
    {
        encoderTransitionCount = 0;
        const uint8_t value = brightnessLevel > (MIN_BRIGHTNESS + BRIGHTNESS_STEP - 1)
            ? brightnessLevel - BRIGHTNESS_STEP : MIN_BRIGHTNESS;
        if (value != brightnessLevel) {
            brightnessLevel = value;
            changed = true;
        }
    }

    // The EC11 push switch is active LOW and is independent of ESP-NOW.
    const bool buttonReading = digitalRead(LED_MASTER_TOGGLE_PIN);
    if (buttonReading != lastDebugButtonReading) {
        Serial.printf("[RPM CTRL] Master button GPIO%d=%s\\n",
                      LED_MASTER_TOGGLE_PIN,
                      buttonReading == LOW ? "LOW/PRESSED" : "HIGH/RELEASED");
        lastDebugButtonReading = buttonReading;
    }
    if (buttonReading != lastButtonReading)
    {
        lastButtonReading = buttonReading;
        lastButtonChangeMs = millis();
    }

    if ((millis() - lastButtonChangeMs) >= BUTTON_DEBOUNCE_MS &&
        buttonReading != stableButtonState)
    {
        stableButtonState = buttonReading;
        if (stableButtonState == LOW) {
            ledsEnabled = !ledsEnabled;
            Serial.printf("[RPM CTRL] LEDs %s\\n", ledsEnabled ? "ON" : "OFF");
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
    // Preserve the original brighter disconnected-white mode while applying
    // the encoder's brightness adjustment to both operating modes.
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

    encoderPreviousState =
        (digitalRead(BRIGHTNESS_ENCODER_A_PIN) ? 0x02 : 0x00) |
        (digitalRead(BRIGHTNESS_ENCODER_B_PIN) ? 0x01 : 0x00);

    lastButtonReading = digitalRead(LED_MASTER_TOGGLE_PIN);
    stableButtonState = lastButtonReading;
    lastDebugButtonReading = lastButtonReading;
    lastDebugEncoderState = encoderPreviousState;
    Serial.printf("[RPM CTRL] Inputs ready: A=GPIO%d B=GPIO%d SW=GPIO%d\\n",
                  BRIGHTNESS_ENCODER_A_PIN,
                  BRIGHTNESS_ENCODER_B_PIN,
                  LED_MASTER_TOGGLE_PIN);
    Serial.printf("[RPM CTRL] Initial levels: A=%u B=%u SW=%u\\n",
                  digitalRead(BRIGHTNESS_ENCODER_A_PIN),
                  digitalRead(BRIGHTNESS_ENCODER_B_PIN),
                  digitalRead(LED_MASTER_TOGGLE_PIN));
    lastButtonChangeMs = millis();

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
