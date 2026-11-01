
#pragma once

#include <Arduino.h>

//=============================================================================
// FEATURES
//=============================================================================

#define ENABLE_SERIAL_DEBUG 0
#define ENABLE_CRC          0
#define ENABLE_OTA          1
#define ENABLE_PEDAL_CALIB  0
#define ENABLE_CLUTCH_PEDAL 1

//=============================================================================
// SENSOR MODES
//=============================================================================

#define BRAKE_SENSOR_ANALOG 1
#define BRAKE_SENSOR_HX711  2
#define THROTTLE_SENSOR_ANALOG 1
#define THROTTLE_SENSOR_HX711  2
#define CLUTCH_SENSOR_ANALOG 1
#define CLUTCH_SENSOR_HX711  2

// Default sensor modes. All three pedals now have the same runtime capability.
#define BRAKE_SENSOR_MODE BRAKE_SENSOR_HX711
#define THROTTLE_SENSOR_MODE THROTTLE_SENSOR_ANALOG
#define CLUTCH_SENSOR_MODE CLUTCH_SENSOR_ANALOG

#if (BRAKE_SENSOR_MODE != BRAKE_SENSOR_ANALOG) && (BRAKE_SENSOR_MODE != BRAKE_SENSOR_HX711)
#error "Invalid BRAKE_SENSOR_MODE"
#endif
#if (THROTTLE_SENSOR_MODE != THROTTLE_SENSOR_ANALOG) && (THROTTLE_SENSOR_MODE != THROTTLE_SENSOR_HX711)
#error "Invalid THROTTLE_SENSOR_MODE"
#endif
#if (CLUTCH_SENSOR_MODE != CLUTCH_SENSOR_ANALOG) && (CLUTCH_SENSOR_MODE != CLUTCH_SENSOR_HX711)
#error "Invalid CLUTCH_SENSOR_MODE"
#endif

//=============================================================================
// BRAKE HX711
//=============================================================================
constexpr uint8_t BRAKE_HX711_TARE_SAMPLES = 20;
constexpr uint32_t BRAKE_HX711_READY_TIMEOUT_MS = 1000;
constexpr float BRAKE_LOAD_CELL_CAPACITY_KG = 200.0f;
constexpr float BRAKE_MAX_FORCE_KG = 40.0f;
constexpr float BRAKE_HX711_COUNTS_PER_KG = 25000.0f;
constexpr bool BRAKE_HX711_INVERT = false;
constexpr uint8_t BRAKE_HX711_FILTER_DIVISOR = 1;

//=============================================================================
// THROTTLE HX711
//=============================================================================
constexpr uint8_t THROTTLE_HX711_TARE_SAMPLES = 20;
constexpr uint32_t THROTTLE_HX711_READY_TIMEOUT_MS = 1000;
constexpr float THROTTLE_LOAD_CELL_CAPACITY_KG = 200.0f;
constexpr float THROTTLE_MAX_FORCE_KG = 10.0f;
constexpr float THROTTLE_HX711_COUNTS_PER_KG = 25000.0f;
constexpr bool THROTTLE_HX711_INVERT = false;
constexpr uint8_t THROTTLE_HX711_FILTER_DIVISOR = 1;

//=============================================================================
// CLUTCH HX711
//=============================================================================
constexpr uint8_t CLUTCH_HX711_TARE_SAMPLES = 20;
constexpr uint32_t CLUTCH_HX711_READY_TIMEOUT_MS = 1000;
constexpr float CLUTCH_LOAD_CELL_CAPACITY_KG = 200.0f;
constexpr float CLUTCH_MAX_FORCE_KG = 10.0f;
constexpr float CLUTCH_HX711_COUNTS_PER_KG = 25000.0f;
constexpr bool CLUTCH_HX711_INVERT = false;
constexpr uint8_t CLUTCH_HX711_FILTER_DIVISOR = 1;

//=============================================================================
// DEBUG / ESP-NOW
//=============================================================================
#define DEBUG_ESPNOW 0
constexpr uint32_t SERIAL_BAUDRATE = 115200;
constexpr uint8_t ESPNOW_CHANNEL = 1;
constexpr uint32_t PEDAL_TIMEOUT_MS = 500;
constexpr uint32_t PEDAL_TX_INTERVAL_MS = 10;

//=============================================================================
// ADC
//=============================================================================
constexpr uint16_t ADC_MAX_VALUE = 4095;
constexpr float PEDAL_ADC_FILTER_ALPHA = 0.30f;

//=============================================================================
// OTA
//=============================================================================
#if ENABLE_OTA
constexpr uint32_t OTA_WINDOW_MS = 60000;
constexpr char OTA_AP_SSID[] = "GamePadPro-Pedals-OTA";
constexpr char OTA_AP_PASSWORD[] = "GPPedalsOTA8264";
constexpr uint16_t OTA_HTTP_PORT = 80;
#endif
