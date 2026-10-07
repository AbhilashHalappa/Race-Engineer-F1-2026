/******************************************************************************
 * ESP32-C3 Super Mini - Sequential Shifter + Handbrake
 *
 * Shifter switches: GPIO -> switch -> GND (internal pull-ups enabled).
 *
 * Hall mode:
 *   GPIO0 = analog Hall output (0..3.3 V only)
 *
 * HX711/load-cell mode:
 *   GPIO1 = HX711 DAT/DOUT
 *   GPIO2 = HX711 CLK/SCK
 ******************************************************************************/
#pragma once

#define HALL_HANDBRAKE_PIN 0
#define HX711_DATA_PIN      1
#define HX711_CLOCK_PIN     2
#define SHIFT_UP_PIN        4
#define SHIFT_DOWN_PIN      5
#define SHIFTER_AUX_PIN     6
