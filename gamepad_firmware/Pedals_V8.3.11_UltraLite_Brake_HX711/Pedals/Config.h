/******************************************************************************
 * GamePad Pro V8
 * Config.h — Pedals
 ******************************************************************************/

#pragma once

#include <Arduino.h>

//=============================================================================
// Feature Enable
//=============================================================================

#define ENABLE_SERIAL_DEBUG    0
#define ENABLE_CRC             0
#define ENABLE_OTA             0

// Future / optional hardware hooks
#define ENABLE_PEDAL_CALIB     0
#define ENABLE_CLUTCH_PEDAL    0  // Set to 1 after wiring foot clutch to CLUTCH_ADC_PIN

//=============================================================================
// Brake sensor selection
//=============================================================================

#define BRAKE_SENSOR_ANALOG 1
#define BRAKE_SENSOR_HX711  2

// Current/default hardware: existing analog position sensor on BRAKE_ADC_PIN.
// Change ONLY this line when upgrading the brake to a load cell + HX711.
#define BRAKE_SENSOR_MODE BRAKE_SENSOR_ANALOG
// #define BRAKE_SENSOR_MODE BRAKE_SENSOR_HX711

#if (BRAKE_SENSOR_MODE != BRAKE_SENSOR_ANALOG) && \
    (BRAKE_SENSOR_MODE != BRAKE_SENSOR_HX711)
#error "BRAKE_SENSOR_MODE must be BRAKE_SENSOR_ANALOG or BRAKE_SENSOR_HX711"
#endif

// HX711 brake load-cell settings. No external HX711 library is required.
// Release the brake while the pedal ESP32 boots so startup tare is correct.
constexpr uint8_t BRAKE_HX711_TARE_SAMPLES = 20;
constexpr uint32_t BRAKE_HX711_READY_TIMEOUT_MS = 1000;
constexpr float BRAKE_LOAD_CELL_CAPACITY_KG = 40.0f;
constexpr float BRAKE_MAX_FORCE_KG = 40.0f;
constexpr float BRAKE_HX711_COUNTS_PER_KG = 25000.0f;
constexpr bool BRAKE_HX711_INVERT = false;
constexpr uint8_t BRAKE_HX711_FILTER_DIVISOR = 4;

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
// Communication Timeouts
//=============================================================================

constexpr uint32_t PEDAL_TIMEOUT_MS = 500;

//=============================================================================
// Update Rates
//=============================================================================

constexpr uint32_t PEDAL_TX_INTERVAL_MS = 10;    // 100Hz

//=============================================================================
// ADC
//=============================================================================

constexpr uint16_t ADC_MAX_VALUE = 4095;

// EMA filter coefficient for throttle/brake/clutch (0..1). Higher = snappier.
constexpr float PEDAL_ADC_FILTER_ALPHA = 0.30f;
