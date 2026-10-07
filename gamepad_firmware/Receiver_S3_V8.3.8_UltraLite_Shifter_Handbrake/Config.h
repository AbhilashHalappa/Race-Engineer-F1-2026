/******************************************************************************
 * GamePad Pro V8
 * Config.h
 *
 * Global Configuration
 ******************************************************************************/

#pragma once

#include <Arduino.h>

//=============================================================================
// Feature Enable
//=============================================================================

#define ENABLE_RACE_ENGINEER   1
#define ENABLE_SIMHUB          0
#define ENABLE_DASHBOARD       1
#define ENABLE_RPM_BAR         1
#define ENABLE_STATUS_LED      1
#define ENABLE_SERIAL_DEBUG    0
#define ENABLE_CRC             0
#define ENABLE_OTA             0

//=============================================================================
// Debug
//=============================================================================

#define DEBUG_ESPNOW           0

//=============================================================================
// Serial
//=============================================================================

constexpr uint32_t SERIAL_BAUDRATE = 115200;

//=============================================================================
// ESP-NOW
//=============================================================================

constexpr uint8_t ESPNOW_CHANNEL = 1;

// Maximum Wi-Fi transmit power in 0.25 dBm units.
// 44 maps to 11 dBm: enough for a nearby wheel/pedals/display while
// reducing radio power and heat compared with the default 20 dBm.
constexpr int8_t ESPNOW_TX_POWER_QDBM = 44;

//=============================================================================
// Display
//=============================================================================

constexpr uint8_t DISPLAY_BRIGHTNESS = 4;      // 0-15

//=============================================================================
// RPM LED Bar
//=============================================================================

constexpr uint8_t RPM_LED_COUNT      = 8;
constexpr uint8_t RPM_LED_BRIGHTNESS = 40;

constexpr uint32_t SHIFT_FLASH_PERIOD_MS = 100;

//=============================================================================
// RPM Thresholds (%)
//=============================================================================

constexpr uint8_t RPM_GREEN_END  = 50;
constexpr uint8_t RPM_YELLOW_END = 70;
constexpr uint8_t RPM_ORANGE_END = 85;
constexpr uint8_t RPM_RED_END    = 95;

//=============================================================================
// Dashboard Layout
//=============================================================================

constexpr uint8_t SPEED_DIGITS    = 4;
constexpr uint8_t GEAR_DIGITS     = 2;
constexpr uint8_t POSITION_DIGITS = 2;

//=============================================================================
// Communication Timeouts
//=============================================================================

constexpr uint32_t WHEEL_TIMEOUT_MS      = 500;
constexpr uint32_t PEDAL_TIMEOUT_MS      = 500;
constexpr uint32_t MOTOR_TEMP_TIMEOUT_MS = 3000; // NTC peer TX ~2 Hz
constexpr uint32_t SHIFTER_TIMEOUT_MS    = 500;  // C3 shifter normally TX at 200 Hz
constexpr uint32_t DASHBOARD_TIMEOUT_MS  = 500;
constexpr uint32_t SIMHUB_TIMEOUT_MS     = 1000; // legacy, inactive
constexpr uint32_t RACE_ENGINEER_TIMEOUT_MS = 1000;

//=============================================================================
// Motor temperature bands (°C) → wheel LED 10 levels
//=============================================================================

constexpr int16_t MOTOR_TEMP_WARM_C = 60;  // OK → warm
constexpr int16_t MOTOR_TEMP_HOT_C  = 85;  // warm → hot (flash)

//=============================================================================
// Update Rates
//=============================================================================

constexpr uint32_t WHEEL_TX_INTERVAL_MS      = 5;     // 200Hz
constexpr uint32_t PEDAL_TX_INTERVAL_MS      = 10;    // 100Hz
// Steering-wheel telemetry remains at 50 Hz.
constexpr uint32_t DASHBOARD_TX_INTERVAL_MS  = 20;    // 50 Hz


// Native USB HID: one complete report, only when changed.
constexpr uint32_t HID_REPORT_INTERVAL_MS     = 1;     // Up to 1000Hz
constexpr uint32_t HID_KEEPALIVE_MS           = 100;

//=============================================================================
// ADC
//=============================================================================

constexpr uint16_t ADC_MAX_VALUE = 4095;

//=============================================================================
// Pedal Calibration Thresholds
//=============================================================================

constexpr uint16_t POT_LEFT_THRESHOLD  = 1200;
constexpr uint16_t POT_RIGHT_THRESHOLD = 2800;

//=============================================================================
// Status LED
//=============================================================================

constexpr uint32_t STATUS_LED_REFRESH_MS = 100;

//=============================================================================
// RPM LED Layout
//=============================================================================

constexpr uint8_t RPM_LED_1 = 0;
constexpr uint8_t RPM_LED_2 = 1;
constexpr uint8_t RPM_LED_3 = 2;
constexpr uint8_t RPM_LED_4 = 3;
constexpr uint8_t RPM_LED_5 = 4;
constexpr uint8_t RPM_LED_6 = 5;
constexpr uint8_t RPM_LED_7 = 6;
constexpr uint8_t RPM_LED_8 = 7;

//=============================================================================
// Telemetry Limits
//=============================================================================

constexpr uint16_t MAX_SPEED    = 9999;
constexpr uint8_t  MAX_POSITION = 99;
constexpr uint8_t  MAX_GEAR     = 11;

//=============================================================================
// Misc
//=============================================================================

constexpr bool TELEMETRY_LOST_DIM = true;

//=============================================================================
// Pedal Axis Normalization
//=============================================================================
// The current physical pedal loom is reversed relative to the historical
// PedalPayload field names. Keep the transmitter protocol untouched and
// normalize once inside the Receiver. Set to 0 only if the pedal wiring is
// later corrected at the source.
#define SWAP_PEDAL_AXES 1
