/*** Wheel Companion Ultra Lite - Wireless Sequential Shifter + Handbrake ESP32-C3 ***/
#pragma once
#include <Arduino.h>

#define ENABLE_SERIAL_DEBUG 1
#define DEBUG_ESPNOW        0
#define ENABLE_OTA          1

constexpr uint32_t SERIAL_BAUDRATE = 115200;
constexpr uint8_t ESPNOW_CHANNEL = 1;
constexpr uint32_t SHIFTER_TX_INTERVAL_MS = 5;
constexpr uint32_t DEBOUNCE_MS = 6;

// Runtime-selectable handbrake sensor types.
#define HANDBRAKE_SENSOR_HALL   1
#define HANDBRAKE_SENSOR_HX711  2
#define HANDBRAKE_SENSOR_MODE HANDBRAKE_SENSOR_HALL
#if (HANDBRAKE_SENSOR_MODE != HANDBRAKE_SENSOR_HALL) && \
    (HANDBRAKE_SENSOR_MODE != HANDBRAKE_SENSOR_HX711)
#error "Invalid HANDBRAKE_SENSOR_MODE"
#endif

constexpr uint8_t HALL_HANDBRAKE_SAMPLES = 4;
constexpr bool HALL_HANDBRAKE_INVERT = false;
constexpr uint8_t HX711_TARE_SAMPLES = 20;
constexpr uint32_t HX711_READY_TIMEOUT_MS = 1000;
constexpr float HX711_LOAD_CELL_CAPACITY_KG = 40.0f;
constexpr float HX711_MAX_FORCE_KG = 40.0f;
constexpr float HX711_COUNTS_PER_KG = 25000.0f;
constexpr bool HX711_HANDBRAKE_INVERT = false;
constexpr uint8_t HX711_FILTER_DIVISOR = 4;

// OTA mirrors the proven pedal updater but uses an independent AP identity.
#if ENABLE_OTA
constexpr uint32_t OTA_WINDOW_MS = 60000;
constexpr char OTA_AP_SSID[] = "GamePadPro-Handbrake-OTA";
constexpr char OTA_AP_PASSWORD[] = "GPPedalsOTA8264";
constexpr uint16_t OTA_HTTP_PORT = 80;
#endif
