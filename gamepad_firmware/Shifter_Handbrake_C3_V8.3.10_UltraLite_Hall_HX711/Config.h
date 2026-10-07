/******************************************************************************
 * Wheel Companion Ultra Lite - Wireless Sequential Shifter + Handbrake
 * ESP32-C3 Super Mini
 *
 * Select exactly ONE handbrake sensor type below. Both implementations are
 * compiled into this source tree, but only the selected mode is used.
 ******************************************************************************/
#pragma once
#include <Arduino.h>

#define ENABLE_SERIAL_DEBUG 1
#define DEBUG_ESPNOW        0

constexpr uint32_t SERIAL_BAUDRATE = 115200;
constexpr uint8_t ESPNOW_CHANNEL = 1;
constexpr uint32_t SHIFTER_TX_INTERVAL_MS = 5;   // 200 Hz radio update
constexpr uint32_t DEBOUNCE_MS = 6;

// ---------------------------------------------------------------------------
// HANDBRAKE SENSOR SELECTION
// ---------------------------------------------------------------------------
#define HANDBRAKE_SENSOR_HALL   1
#define HANDBRAKE_SENSOR_HX711  2

// Change ONLY this line when changing handbrake hardware:
#define HANDBRAKE_SENSOR_MODE HANDBRAKE_SENSOR_HALL
// #define HANDBRAKE_SENSOR_MODE HANDBRAKE_SENSOR_HX711

#if (HANDBRAKE_SENSOR_MODE != HANDBRAKE_SENSOR_HALL) && \
    (HANDBRAKE_SENSOR_MODE != HANDBRAKE_SENSOR_HX711)
#error "HANDBRAKE_SENSOR_MODE must be HANDBRAKE_SENSOR_HALL or HANDBRAKE_SENSOR_HX711"
#endif

// ---------------------------------------------------------------------------
// ANALOG HALL SENSOR SETTINGS (GPIO0)
// ---------------------------------------------------------------------------
constexpr uint8_t HALL_HANDBRAKE_SAMPLES = 4;
constexpr bool HALL_HANDBRAKE_INVERT = false;

// ---------------------------------------------------------------------------
// HX711 + LOAD CELL SETTINGS (GPIO1 DATA, GPIO2 CLOCK)
// ---------------------------------------------------------------------------
// The HX711 is read directly; no external HX711 Arduino library is required.
// The firmware automatically tares at startup, so release the handbrake while
// the ESP32-C3 boots.
constexpr uint8_t HX711_TARE_SAMPLES = 20;
constexpr uint32_t HX711_READY_TIMEOUT_MS = 1000;

// Load-cell force calibration. Keep these values aligned with the handbrake
// sensor panel in Wheel Companion Ultra Lite. For a 40 kg cell, capacity stays
// 40 kg, while MAX_FORCE can be lower (for example 15 kg = 100% handbrake).
constexpr float HX711_LOAD_CELL_CAPACITY_KG = 40.0f;
constexpr float HX711_MAX_FORCE_KG = 40.0f;

// Calibrate this once with a known weight/force:
//   counts_per_kg = (loaded_raw - tare_raw) / known_force_kg
// 25,000 preserves the previous 1,000,000-count / 40 kg default.
constexpr float HX711_COUNTS_PER_KG = 25000.0f;

// Set true if pulling the handbrake makes the HX711 count move negative after
// tare. Leave false if pulling makes the count increase.
constexpr bool HX711_HANDBRAKE_INVERT = false;

// Simple low-pass filter. 1 = no averaging, 4 = moderate smoothing.
constexpr uint8_t HX711_FILTER_DIVISOR = 4;
