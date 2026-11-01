/******************************************************************************
 * GamePad Pro V8
 * Config.h — Wheel
 ******************************************************************************/

#pragma once

#include <Arduino.h>

#define ENABLE_SIMHUB          1
#define ENABLE_DASHBOARD       1
#define ENABLE_RPM_BAR         1
#define ENABLE_STATUS_LED      0
#define ENABLE_SERIAL_DEBUG    0
#define ENABLE_CRC             0
#define ENABLE_OTA             1

// All four former analog inputs are now permanent digital push buttons.
// GPIO 34/35/36/39 are input-only and have no internal pull-up resistors.
// Fit an external pull-up (for example 10 kΩ to 3.3 V) and wire each
// normally-open button between its GPIO and GND.
constexpr uint8_t ANALOG_INPUT_BUTTON_DEBOUNCE_SAMPLES = 3;

constexpr uint8_t POT1_BUTTON_BIT          = 24;
constexpr uint8_t POT2_BUTTON_BIT          = 25;
constexpr uint8_t CLUTCH_LEFT_BUTTON_BIT   = 26;
constexpr uint8_t CLUTCH_RIGHT_BUTTON_BIT  = 27;

#define DEBUG_ESPNOW           0
constexpr uint32_t SERIAL_BAUDRATE = 115200;
constexpr uint8_t ESPNOW_CHANNEL = 1;
constexpr uint32_t OTA_WINDOW_MS = 60000;
constexpr uint16_t OTA_HTTP_PORT = 80;
#define OTA_AP_SSID     "GamePadPro-Wheel-OTA"
#define OTA_AP_PASSWORD "GPPedalsOTA8264"
constexpr uint8_t DISPLAY_BRIGHTNESS = 4;
constexpr uint8_t WHEEL_LED_COUNT      = 14;
constexpr uint8_t RPM_BAR_LED_COUNT    = 8;
constexpr uint8_t RPM_LED_BRIGHTNESS   = 20;
constexpr uint32_t SHIFT_FLASH_PERIOD_MS = 100;
constexpr uint8_t LED_RPM_FIRST   = 0;
constexpr uint8_t LED_DRS         = 8;
constexpr uint8_t LED_MOTOR_TEMP  = 9;
constexpr uint8_t LED_PIT         = LED_MOTOR_TEMP;
constexpr uint8_t LED_ERS_MODE    = 10;
constexpr uint8_t LED_FLAG        = 11;
constexpr uint8_t LED_LOW_FUEL    = 12;
constexpr uint8_t LED_LOW_ERS     = 13;
constexpr uint8_t RPM_GREEN_END  = 50;
constexpr uint8_t RPM_YELLOW_END = 75;
constexpr uint8_t SPEED_DIGITS    = 4;
constexpr uint8_t GEAR_DIGITS     = 2;
constexpr uint8_t POSITION_DIGITS = 2;
constexpr uint32_t WHEEL_TIMEOUT_MS      = 500;
constexpr uint32_t PEDAL_TIMEOUT_MS      = 500;
constexpr uint32_t DASHBOARD_TIMEOUT_MS  = 500;
constexpr uint32_t SIMHUB_TIMEOUT_MS     = 1000;
constexpr uint32_t WHEEL_TX_INTERVAL_MS      = 5;
constexpr uint32_t PEDAL_TX_INTERVAL_MS      = 10;
constexpr uint32_t DASHBOARD_TX_INTERVAL_MS  = 20;
constexpr uint16_t MAX_SPEED    = 9999;
constexpr uint8_t  MAX_POSITION = 99;
constexpr uint8_t  MAX_GEAR     = 11;
constexpr bool TELEMETRY_LOST_DIM = true;
