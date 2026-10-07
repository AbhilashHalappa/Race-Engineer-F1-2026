/******************************************************************************
 * GamePad Pro V8
 * Pins.h
 *
 * Hardware Pin Definitions
 ******************************************************************************/

#pragma once

//=============================================================================
// ESP32 WHEEL (Transmitter 1)
//=============================================================================
constexpr uint8_t BUTTON_COUNT = 32;

extern const uint8_t BUTTON_PINS[BUTTON_COUNT];
//--------------------------------------------------
// Encoder Matrix
//--------------------------------------------------

#define ENC_ROW1_PIN                15
#define ENC_ROW2_PIN                5
#define ENC_ROW3_PIN                13

#define ENC_COL1_PIN                19
#define ENC_COL2_PIN                21
#define ENC_COL3_PIN                22
#define ENC_COL4_PIN                23


//--------------------------------------------------
// Button Matrix
//--------------------------------------------------

#define BTN_ROW1_PIN                4
#define BTN_ROW2_PIN                26
#define BTN_ROW3_PIN                27

#define BTN_COL1_PIN                14
#define BTN_COL2_PIN                18
#define BTN_COL3_PIN                32
#define BTN_COL4_PIN                33




//--------------------------------------------------
// Analog Inputs
//--------------------------------------------------

#define CLUTCH_LEFT_ADC_PIN         34
#define CLUTCH_RIGHT_ADC_PIN        35

#define POT1_ADC_PIN                36
#define POT2_ADC_PIN                39


//--------------------------------------------------
// Dashboard Display
//--------------------------------------------------

#define MAX7219_DIN_PIN             25
#define MAX7219_CLK_PIN             16

// CS / LOAD
#define MAX7219_CS_PIN              17


//--------------------------------------------------
// RPM LED Bar
//--------------------------------------------------

// Uses UART0 TX

#define RPM_LED_PIN                 1


