/******************************************************************************
 * GamePad Pro V8
 * Config.h — Wheel
 ******************************************************************************/

#pragma once

#include <Arduino.h>

//=============================================================================
// Feature Enable
//=============================================================================

#define ENABLE_SIMHUB          1
#define ENABLE_DASHBOARD       1
#define ENABLE_RPM_BAR         1
#define ENABLE_STATUS_LED      0
#define ENABLE_SERIAL_DEBUG    0
#define ENABLE_CRC             0
#define ENABLE_OTA             0

// Set to 1 only when clutch paddles are wired to GPIO 34 / 35.
// With clutches disconnected those pins float and pick up noise from
// pot / button scanning (looks like RX/RY moving when you turn a pot).
#define ENABLE_CLUTCHES        0

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

//=============================================================================
// Display
//=============================================================================

constexpr uint8_t DISPLAY_BRIGHTNESS = 4;      // 0-15

//=============================================================================
// LED bar (14 WS2812: 8 RPM + 6 status)
//=============================================================================
//
// Index map (0-based in firmware / 1-based on the wheel face):
//   0..7  (LED 1..8)   RPM bar
//   8     (LED 9)      DRS
//   9     (LED 10)     Motor temperature (ESP32-C3 10K NTC)
//   10    (LED 11)     ERS mode
//   11    (LED 12)     Flag
//   12    (LED 13)     Low fuel warning
//   13    (LED 14)     Low ERS energy warning
//

constexpr uint8_t WHEEL_LED_COUNT      = 14;
constexpr uint8_t RPM_BAR_LED_COUNT    = 8;
constexpr uint8_t RPM_LED_BRIGHTNESS   = 20;   // ~50% of previous (40); FastLED scale 0-255
constexpr uint32_t SHIFT_FLASH_PERIOD_MS = 100;

constexpr uint8_t LED_RPM_FIRST   = 0;
constexpr uint8_t LED_DRS         = 8;
constexpr uint8_t LED_MOTOR_TEMP  = 9;
constexpr uint8_t LED_PIT         = LED_MOTOR_TEMP; // legacy alias
constexpr uint8_t LED_ERS_MODE    = 10;
constexpr uint8_t LED_FLAG        = 11;
constexpr uint8_t LED_LOW_FUEL    = 12;
constexpr uint8_t LED_LOW_ERS     = 13;

//=============================================================================
// RPM colour bands (% of bar length)
//=============================================================================

constexpr uint8_t RPM_GREEN_END  = 50;
constexpr uint8_t RPM_YELLOW_END = 75;

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
constexpr uint32_t DASHBOARD_TIMEOUT_MS  = 500;
constexpr uint32_t SIMHUB_TIMEOUT_MS     = 1000;

//=============================================================================
// Update Rates
//=============================================================================

constexpr uint32_t WHEEL_TX_INTERVAL_MS      = 5;     // 200Hz
constexpr uint32_t PEDAL_TX_INTERVAL_MS      = 10;    // 100Hz
constexpr uint32_t DASHBOARD_TX_INTERVAL_MS  = 20;    // 50Hz

//=============================================================================
// ADC
//=============================================================================

constexpr uint16_t ADC_MAX_VALUE = 4095;

//=============================================================================
// Rotary pot → 2 buttons each (left / right with centre dead zone)
//=============================================================================
//
// ADC layout per pot (0..4095):
//   [ LOW button ][ dead centre ][ HIGH button ]
//
//   Pot1: low=24, high=25
//   Pot2: low=26, high=27
//
// Mid bits 28/30 are left free for a future sequential shifter (N / R / etc.).
//

constexpr uint16_t POT_LEFT_THRESHOLD  = 1200;  // active when adc <= this
constexpr uint16_t POT_RIGHT_THRESHOLD = 2800;  // active when adc >= this

constexpr uint8_t POT1_BIT_LOW  = 24;
constexpr uint8_t POT1_BIT_HIGH = 25;

constexpr uint8_t POT2_BIT_LOW  = 26;
constexpr uint8_t POT2_BIT_HIGH = 27;

//=============================================================================
// Status LED
//=============================================================================

constexpr uint32_t STATUS_LED_REFRESH_MS = 100;

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
