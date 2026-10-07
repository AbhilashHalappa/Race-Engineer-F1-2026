/******************************************************************************
 * GamePad Pro V8
 * TempSensor.cpp — 10K NTC thermistor (2-wire) via ADC divider
 ******************************************************************************/

#include "TempSensor.h"

#include <math.h>

#include "Config.h"
#include "Pins.h"

namespace
{
    MotorTempPayload payload = {};
    uint32_t lastSampleMs = 0;
    float adcFiltered = 0.0f;

    bool adcToCelsius(float adc, float& outC)
    {
        // Reject open / short extremes
        if (adc < 20.0f || adc > (ADC_MAX_VALUE - 20.0f))
        {
            return false;
        }

        const float v = (adc / static_cast<float>(ADC_MAX_VALUE)) * NTC_VCC;
        if (v <= 0.01f || v >= (NTC_VCC - 0.01f))
        {
            return false;
        }

        // VCC -- R_SERIES -- node -- NTC -- GND
        const float rNtc = NTC_R_SERIES * (v / (NTC_VCC - v));
        if (rNtc < 100.0f || rNtc > 500000.0f)
        {
            return false;
        }

        // Beta equation: 1/T = 1/T0 + (1/B) * ln(R/R25)
        const float invT =
            (1.0f / NTC_T0_KELVIN) +
            (logf(rNtc / NTC_R25) / NTC_BETA);
        const float kelvin = 1.0f / invT;
        outC = kelvin - 273.15f;
        return (outC > -40.0f && outC < 150.0f);
    }
}

bool TempSensor::begin()
{
    pinMode(NTC_ADC_PIN, INPUT);
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);

    adcFiltered = static_cast<float>(analogRead(NTC_ADC_PIN));
    payload = {};
    lastSampleMs = 0;

    float c = 0.0f;
    if (!adcToCelsius(adcFiltered, c))
    {
#if ENABLE_SERIAL_DEBUG
        Serial.println("[TEMP] NTC first read out of range — check wiring");
#endif
        payload.valid = 0;
        return true; // still boot; TX will send invalid until sensor OK
    }

    payload.tempCx100 = static_cast<int16_t>(c * 100.0f);
    payload.valid = 1;

#if ENABLE_SERIAL_DEBUG
    Serial.println("[TEMP] 10K NTC ready");
    Serial.printf("[TEMP] %.2f C (ADC %.0f)\n", c, adcFiltered);
#endif

    return true;
}

void TempSensor::update()
{
    const uint32_t now = millis();
    if ((now - lastSampleMs) < TEMP_SAMPLE_INTERVAL_MS)
    {
        return;
    }
    lastSampleMs = now;

    const float raw = static_cast<float>(analogRead(NTC_ADC_PIN));
    adcFiltered =
        (NTC_ADC_FILTER_ALPHA * raw) +
        ((1.0f - NTC_ADC_FILTER_ALPHA) * adcFiltered);

    float c = 0.0f;
    if (!adcToCelsius(adcFiltered, c))
    {
        payload.valid = 0;
#if ENABLE_SERIAL_DEBUG
        Serial.printf("[TEMP] NTC invalid (ADC %.0f)\n", adcFiltered);
#endif
        return;
    }

    payload.tempCx100 = static_cast<int16_t>(c * 100.0f);
    payload.valid = 1;

#if ENABLE_SERIAL_DEBUG
    Serial.printf("[TEMP] %.2f C\n", c);
#endif
}

MotorTempPayload TempSensor::getPayload()
{
    return payload;
}
