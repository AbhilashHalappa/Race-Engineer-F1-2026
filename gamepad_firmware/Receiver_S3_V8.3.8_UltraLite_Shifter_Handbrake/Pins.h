/******************************************************************************
 * GamePad Pro V8
 * Pins.h
 *
 * Hardware Pin Definitions
 ******************************************************************************/

#pragma once

//=============================================================================
// ESP32-S3 RECEIVER
//=============================================================================

// Steering encoder / centre button removed — steering is a standalone device.
// GPIO 6 / 7 / 8 are free (reserved for a future sequential-shifter peer or debug).

// Built-in RGB LED
#define STATUS_LED_PIN              21

// Native USB-C is used as one composite USB device:
//   - USB HID gamepad
//   - USB CDC serial port for SimHub
// No external UART pins are required.
