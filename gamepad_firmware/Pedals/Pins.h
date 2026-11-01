/******************************************************************************
 * Wheel Companion Ultra Lite - Pedal Input Pin Definitions
 ******************************************************************************/
#pragma once

// Analog pedal inputs
#define THROTTLE_ADC_PIN            34
#define BRAKE_ADC_PIN               32
#define CLUTCH_ADC_PIN              35

// Brake HX711
#define BRAKE_HX711_DATA_PIN       33
#define BRAKE_HX711_CLOCK_PIN      26

// Throttle HX711
#define THROTTLE_HX711_DATA_PIN    27
#define THROTTLE_HX711_CLOCK_PIN   14

// Clutch HX711
// GPIO18/19 are free on the pedal ESP32 in this firmware and are not ADC-only
// or flash pins. GPIO18 = HX711 DOUT, GPIO19 = HX711 SCK.
#define CLUTCH_HX711_DATA_PIN      18
#define CLUTCH_HX711_CLOCK_PIN     19
