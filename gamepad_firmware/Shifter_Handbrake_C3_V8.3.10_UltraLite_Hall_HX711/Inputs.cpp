#include "Inputs.h"
#include "Pins.h"
#include "Config.h"

namespace
{
struct DebouncedButton
{
    uint8_t pin;
    bool rawPressed;
    bool stablePressed;
    uint32_t changedAt;
};

DebouncedButton buttons[3] =
{
    {SHIFT_UP_PIN, false, false, 0},
    {SHIFT_DOWN_PIN, false, false, 0},
    {SHIFTER_AUX_PIN, false, false, 0}
};

ShifterPayload shifter = {};

// HX711 state. The Receiver still receives the same normalized 0..4095 value
// regardless of whether Hall or load cell mode is selected.
int32_t hx711TareOffset = 0;
int32_t hx711FilteredDelta = 0;
bool hx711HasFilteredValue = false;
uint16_t hx711LastOutput = 0;

void updateButton(DebouncedButton& button, uint32_t now)
{
    const bool pressed = (digitalRead(button.pin) == LOW);
    if (pressed != button.rawPressed)
    {
        button.rawPressed = pressed;
        button.changedAt = now;
    }
    if (button.stablePressed != button.rawPressed &&
        (now - button.changedAt) >= DEBOUNCE_MS)
    {
        button.stablePressed = button.rawPressed;
    }
}

uint16_t readHallHandbrake()
{
    uint32_t total = 0;
    for (uint8_t i = 0; i < HALL_HANDBRAKE_SAMPLES; ++i)
    {
        total += static_cast<uint16_t>(analogRead(HALL_HANDBRAKE_PIN));
    }

    uint16_t value = static_cast<uint16_t>(total / HALL_HANDBRAKE_SAMPLES);
    if (value > 4095u) value = 4095u;
    if (HALL_HANDBRAKE_INVERT) value = static_cast<uint16_t>(4095u - value);
    return value;
}

bool hx711ReadRaw(int32_t& value)
{
    // DOUT is LOW only when a fresh conversion is ready. Never block the
    // shifter loop waiting for a conversion; simply keep the previous value.
    if (digitalRead(HX711_DATA_PIN) != LOW) return false;

    uint32_t data = 0;
    noInterrupts();
    for (uint8_t i = 0; i < 24; ++i)
    {
        digitalWrite(HX711_CLOCK_PIN, HIGH);
        delayMicroseconds(1);
        data = (data << 1) | (digitalRead(HX711_DATA_PIN) ? 1u : 0u);
        digitalWrite(HX711_CLOCK_PIN, LOW);
        delayMicroseconds(1);
    }

    // 25th pulse selects Channel A, gain 128 for the next conversion.
    digitalWrite(HX711_CLOCK_PIN, HIGH);
    delayMicroseconds(1);
    digitalWrite(HX711_CLOCK_PIN, LOW);
    interrupts();

    // Sign-extend the 24-bit two's-complement result.
    if (data & 0x00800000UL) data |= 0xFF000000UL;
    value = static_cast<int32_t>(data);
    return true;
}

bool hx711ReadRawWithTimeout(int32_t& value, uint32_t timeoutMs)
{
    const uint32_t start = millis();
    while ((millis() - start) < timeoutMs)
    {
        if (hx711ReadRaw(value)) return true;
        delay(1);
    }
    return false;
}

bool tareHX711()
{
    int64_t total = 0;
    uint8_t collected = 0;

#if ENABLE_SERIAL_DEBUG
    Serial.println("HX711: release handbrake; taring...");
#endif

    while (collected < HX711_TARE_SAMPLES)
    {
        int32_t raw = 0;
        if (!hx711ReadRawWithTimeout(raw, HX711_READY_TIMEOUT_MS))
        {
#if ENABLE_SERIAL_DEBUG
            Serial.println("[ERROR] HX711 tare timeout - check DAT/CLK/VCC/GND");
#endif
            return false;
        }
        total += raw;
        ++collected;
    }

    hx711TareOffset = static_cast<int32_t>(total / HX711_TARE_SAMPLES);
    hx711FilteredDelta = 0;
    hx711HasFilteredValue = false;
    hx711LastOutput = 0;

#if ENABLE_SERIAL_DEBUG
    Serial.print("HX711 tare offset: ");
    Serial.println(hx711TareOffset);
#endif
    return true;
}

uint16_t readHX711Handbrake()
{
    int32_t raw = 0;
    if (!hx711ReadRaw(raw)) return hx711LastOutput;

    int32_t delta = raw - hx711TareOffset;
    if (HX711_HANDBRAKE_INVERT) delta = -delta;
    if (delta < 0) delta = 0;

    if (!hx711HasFilteredValue)
    {
        hx711FilteredDelta = delta;
        hx711HasFilteredValue = true;
    }
    else if (HX711_FILTER_DIVISOR <= 1)
    {
        hx711FilteredDelta = delta;
    }
    else
    {
        hx711FilteredDelta += (delta - hx711FilteredDelta) / HX711_FILTER_DIVISOR;
    }

    float targetForceKg = HX711_MAX_FORCE_KG;
    if (targetForceKg < 0.1f) targetForceKg = 0.1f;
    if (targetForceKg > HX711_LOAD_CELL_CAPACITY_KG)
        targetForceKg = HX711_LOAD_CELL_CAPACITY_KG;
    const float countsPerKg = (HX711_COUNTS_PER_KG > 1.0f) ? HX711_COUNTS_PER_KG : 1.0f;
    const int32_t fullScale = static_cast<int32_t>(countsPerKg * targetForceKg);

    int64_t mapped = (static_cast<int64_t>(hx711FilteredDelta) * 4095LL) / (fullScale > 0 ? fullScale : 1);
    if (mapped < 0) mapped = 0;
    if (mapped > 4095) mapped = 4095;
    hx711LastOutput = static_cast<uint16_t>(mapped);
    return hx711LastOutput;
}

uint16_t readHandbrake()
{
#if HANDBRAKE_SENSOR_MODE == HANDBRAKE_SENSOR_HX711
    return readHX711Handbrake();
#else
    return readHallHandbrake();
#endif
}
}

bool Inputs::begin()
{
#if HANDBRAKE_SENSOR_MODE == HANDBRAKE_SENSOR_HX711
    pinMode(HX711_DATA_PIN, INPUT);
    pinMode(HX711_CLOCK_PIN, OUTPUT);
    digitalWrite(HX711_CLOCK_PIN, LOW);
#else
    analogReadResolution(12);
    pinMode(HALL_HANDBRAKE_PIN, INPUT);
#endif

    for (auto& button : buttons)
    {
        pinMode(button.pin, INPUT_PULLUP);
        button.rawPressed = (digitalRead(button.pin) == LOW);
        button.stablePressed = button.rawPressed;
        button.changedAt = millis();
    }

#if HANDBRAKE_SENSOR_MODE == HANDBRAKE_SENSOR_HX711
    if (!tareHX711()) return false;
#endif

    update();
    return true;
}

void Inputs::update()
{
    const uint32_t now = millis();
    for (auto& button : buttons) updateButton(button, now);

    uint8_t state = 0;
    if (buttons[0].stablePressed) state |= (1u << 0);
    if (buttons[1].stablePressed) state |= (1u << 1);
    if (buttons[2].stablePressed) state |= (1u << 2);
    shifter.buttonState = state;
    shifter.handbrake = readHandbrake();
}

const ShifterPayload& Inputs::getShifterData()
{
    return shifter;
}
