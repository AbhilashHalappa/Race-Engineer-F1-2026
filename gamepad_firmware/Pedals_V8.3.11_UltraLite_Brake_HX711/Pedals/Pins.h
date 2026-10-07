/******************************************************************************
 * GamePad Pro V8
 * Pins.h
 *
 * Hardware Pin Definitions
 ******************************************************************************/

#pragma once

//=============================================================================
// ESP32 PEDALS (Transmitter 2)
//=============================================================================

#define THROTTLE_ADC_PIN            34
#define BRAKE_ADC_PIN               35
#define CLUTCH_ADC_PIN              32  // Future foot-clutch input (ADC1)
// Future brake load-cell HX711. Ignored in analog brake mode.
#define BRAKE_HX711_DATA_PIN        25
#define BRAKE_HX711_CLOCK_PIN       26
