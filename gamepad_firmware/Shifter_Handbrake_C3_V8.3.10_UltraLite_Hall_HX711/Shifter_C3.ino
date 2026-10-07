/******************************************************************************
 * Wheel Companion Ultra Lite - ESP32-C3 Wireless Sequential Shifter + Handbrake
 *
 * Shifter:
 *   GPIO4 -> Shift Up switch -> GND
 *   GPIO5 -> Shift Down switch -> GND
 *   GPIO6 -> AUX switch -> GND
 *
 * Handbrake - select ONE mode in Config.h:
 *   HALL  : GPIO0 -> analog Hall sensor (0..3.3 V)
 *   HX711 : GPIO1 -> DAT, GPIO2 -> CLK; 40 kg load cell -> HX711 input
 *
 * Receiver exposes buttons 30/31/32 and handbrake on HID Y.
 ******************************************************************************/
#include "Config.h"
#include "Version.h"
#include "Inputs.h"
#include "ESPNowManager.h"

void setup()
{
#if ENABLE_SERIAL_DEBUG
    Serial.begin(SERIAL_BAUDRATE);
    delay(500);
    Serial.println();
    Serial.println("==========================================");
    Serial.println(FW_NAME);
    Serial.print("Version: ");
    Serial.println(FW_STRING);
#if HANDBRAKE_SENSOR_MODE == HANDBRAKE_SENSOR_HX711
    Serial.println("Handbrake sensor: HX711 / LOAD CELL");
#else
    Serial.println("Handbrake sensor: ANALOG HALL");
#endif
    Serial.println("==========================================");
#endif

    if (!Inputs::begin())
    {
#if ENABLE_SERIAL_DEBUG
        Serial.println("[ERROR] Inputs init failed");
#endif
        while (true) delay(1000);
    }

    if (!ESPNow::begin())
    {
#if ENABLE_SERIAL_DEBUG
        Serial.println("[ERROR] ESP-NOW init failed");
#endif
        while (true) delay(1000);
    }

#if ENABLE_SERIAL_DEBUG
    Serial.println("Shifter + handbrake ready");
#endif
}

void loop()
{
    Inputs::update();
    ESPNow::update();
    delay(1);
}
