/******************************************************************************
 * Wheel Companion Ultra Lite
 * Pedal Input Manager - analog brake or HX711 load-cell brake
 ******************************************************************************/

#include "Inputs.h"
#include "Pins.h"
#include "Config.h"

namespace
{
PedalPayload pedals = {};
float throttleFiltered = 0.0f;
float brakeFiltered    = 0.0f;
float clutchFiltered   = 0.0f;

// HX711 brake state. Regardless of sensor type the transmitted brake value is
// normalized to the existing 0..4095 PedalPayload.brake field, so Receiver and
// HID mappings do not change.
int32_t brakeHx711TareOffset = 0;
int32_t brakeHx711FilteredDelta = 0;
bool brakeHx711HasFilteredValue = false;
uint16_t brakeHx711LastOutput = 0;

bool hx711ReadRaw(int32_t& value)
{
    if (digitalRead(BRAKE_HX711_DATA_PIN) != LOW) return false;
    uint32_t data = 0;
    noInterrupts();
    for (uint8_t i = 0; i < 24; ++i)
    {
        digitalWrite(BRAKE_HX711_CLOCK_PIN, HIGH);
        delayMicroseconds(1);
        data = (data << 1) | (digitalRead(BRAKE_HX711_DATA_PIN) ? 1u : 0u);
        digitalWrite(BRAKE_HX711_CLOCK_PIN, LOW);
        delayMicroseconds(1);
    }
    // 25th pulse: Channel A, gain 128 for next conversion.
    digitalWrite(BRAKE_HX711_CLOCK_PIN, HIGH);
    delayMicroseconds(1);
    digitalWrite(BRAKE_HX711_CLOCK_PIN, LOW);
    interrupts();

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

bool tareBrakeHX711()
{
    int64_t total = 0;
    uint8_t collected = 0;
#if ENABLE_SERIAL_DEBUG
    Serial.println("Brake HX711: release brake; taring...");
#endif
    while (collected < BRAKE_HX711_TARE_SAMPLES)
    {
        int32_t raw = 0;
        if (!hx711ReadRawWithTimeout(raw, BRAKE_HX711_READY_TIMEOUT_MS))
        {
#if ENABLE_SERIAL_DEBUG
            Serial.println("[ERROR] Brake HX711 tare timeout - check DAT/CLK/VCC/GND");
#endif
            return false;
        }
        total += raw;
        ++collected;
    }
    brakeHx711TareOffset = static_cast<int32_t>(total / BRAKE_HX711_TARE_SAMPLES);
    brakeHx711FilteredDelta = 0;
    brakeHx711HasFilteredValue = false;
    brakeHx711LastOutput = 0;
#if ENABLE_SERIAL_DEBUG
    Serial.print("Brake HX711 tare offset: ");
    Serial.println(brakeHx711TareOffset);
#endif
    return true;
}

uint16_t readLoadCellBrake()
{
    int32_t raw = 0;
    if (!hx711ReadRaw(raw)) return brakeHx711LastOutput;

    int32_t delta = raw - brakeHx711TareOffset;
    if (BRAKE_HX711_INVERT) delta = -delta;
    if (delta < 0) delta = 0;

    if (!brakeHx711HasFilteredValue)
    {
        brakeHx711FilteredDelta = delta;
        brakeHx711HasFilteredValue = true;
    }
    else if (BRAKE_HX711_FILTER_DIVISOR <= 1)
    {
        brakeHx711FilteredDelta = delta;
    }
    else
    {
        brakeHx711FilteredDelta += (delta - brakeHx711FilteredDelta) / BRAKE_HX711_FILTER_DIVISOR;
    }

    float targetForceKg = BRAKE_MAX_FORCE_KG;
    if (targetForceKg < 0.1f) targetForceKg = 0.1f;
    if (targetForceKg > BRAKE_LOAD_CELL_CAPACITY_KG) targetForceKg = BRAKE_LOAD_CELL_CAPACITY_KG;
    const float countsPerKg = BRAKE_HX711_COUNTS_PER_KG > 1.0f ? BRAKE_HX711_COUNTS_PER_KG : 1.0f;
    const int32_t fullScale = static_cast<int32_t>(countsPerKg * targetForceKg);
    int64_t mapped = (static_cast<int64_t>(brakeHx711FilteredDelta) * 4095LL) / (fullScale > 0 ? fullScale : 1);
    if (mapped < 0) mapped = 0;
    if (mapped > 4095) mapped = 4095;
    brakeHx711LastOutput = static_cast<uint16_t>(mapped);
    return brakeHx711LastOutput;
}

uint16_t readAnalogBrake()
{
    constexpr float alpha = PEDAL_ADC_FILTER_ALPHA;
    brakeFiltered = (alpha * analogRead(BRAKE_ADC_PIN)) + ((1.0f - alpha) * brakeFiltered);
    if (brakeFiltered < 0.0f) brakeFiltered = 0.0f;
    if (brakeFiltered > ADC_MAX_VALUE) brakeFiltered = ADC_MAX_VALUE;
    return static_cast<uint16_t>(brakeFiltered);
}
}

bool Inputs::begin()
{
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);
    pinMode(THROTTLE_ADC_PIN, INPUT);
#if BRAKE_SENSOR_MODE == BRAKE_SENSOR_HX711
    pinMode(BRAKE_HX711_DATA_PIN, INPUT);
    pinMode(BRAKE_HX711_CLOCK_PIN, OUTPUT);
    digitalWrite(BRAKE_HX711_CLOCK_PIN, LOW);
#else
    pinMode(BRAKE_ADC_PIN, INPUT);
#endif
#if ENABLE_CLUTCH_PEDAL
    pinMode(CLUTCH_ADC_PIN, INPUT);
#endif

    throttleFiltered = analogRead(THROTTLE_ADC_PIN);
#if BRAKE_SENSOR_MODE == BRAKE_SENSOR_HX711
    brakeFiltered = 0.0f;
    if (!tareBrakeHX711()) return false;
#else
    brakeFiltered = analogRead(BRAKE_ADC_PIN);
#endif
#if ENABLE_CLUTCH_PEDAL
    clutchFiltered = analogRead(CLUTCH_ADC_PIN);
#else
    clutchFiltered = 0.0f;
#endif

    pedals.throttle = static_cast<uint16_t>(throttleFiltered);
#if BRAKE_SENSOR_MODE == BRAKE_SENSOR_HX711
    pedals.brake = readLoadCellBrake();
#else
    pedals.brake = static_cast<uint16_t>(brakeFiltered);
#endif
    pedals.clutch = static_cast<uint16_t>(clutchFiltered);
    return true;
}

void Inputs::update()
{
    constexpr float alpha = PEDAL_ADC_FILTER_ALPHA;
    throttleFiltered = (alpha * analogRead(THROTTLE_ADC_PIN)) + ((1.0f - alpha) * throttleFiltered);

#if BRAKE_SENSOR_MODE == BRAKE_SENSOR_HX711
    const uint16_t brakeValue = readLoadCellBrake();
#else
    const uint16_t brakeValue = readAnalogBrake();
#endif

#if ENABLE_CLUTCH_PEDAL
    clutchFiltered = (alpha * analogRead(CLUTCH_ADC_PIN)) + ((1.0f - alpha) * clutchFiltered);
#else
    clutchFiltered = 0.0f;
#endif

    pedals.throttle = static_cast<uint16_t>(throttleFiltered);
    pedals.brake = brakeValue;
    pedals.clutch = static_cast<uint16_t>(clutchFiltered);
}

const PedalPayload& Inputs::getPedalData()
{
    return pedals;
}
