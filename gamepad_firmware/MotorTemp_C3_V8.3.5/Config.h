/******************************************************************************
 * GamePad Pro V8
 * Config.h — MotorTemp ESP32-C3 (10K NTC)
 ******************************************************************************/

#pragma once

#include <Arduino.h>

#define ENABLE_SERIAL_DEBUG    1
#define DEBUG_ESPNOW           0

constexpr uint32_t SERIAL_BAUDRATE = 115200;
constexpr uint8_t ESPNOW_CHANNEL = 1;

constexpr uint32_t TEMP_SAMPLE_INTERVAL_MS = 200;
constexpr uint32_t TEMP_TX_INTERVAL_MS     = 500;

//=============================================================================
// 10K NTC thermistor (2-wire) + series divider resistor
//=============================================================================
//
// Wiring:
//   3V3 ---- R_SERIES (10k) ----+---- NTC_ADC_PIN
//                               |
//                              NTC 10k
//                               |
//                              GND
//

constexpr uint16_t ADC_MAX_VALUE     = 4095;
constexpr float    NTC_VCC           = 3.3f;
constexpr float    NTC_R_SERIES      = 10000.0f; // matching divider resistor
constexpr float    NTC_R25           = 10000.0f; // 10K at 25 °C
constexpr float    NTC_BETA          = 3950.0f;  // common B-value; tune if needed
constexpr float    NTC_T0_KELVIN     = 298.15f;  // 25 °C

// EMA on ADC (0..1). Higher = snappier.
constexpr float NTC_ADC_FILTER_ALPHA = 0.25f;
