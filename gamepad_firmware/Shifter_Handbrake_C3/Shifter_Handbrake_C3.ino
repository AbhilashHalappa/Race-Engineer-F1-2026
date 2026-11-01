/******************************************************************************
 * Wheel Companion Ultra Lite - ESP32-C3 Wireless Sequential Shifter + Handbrake
 *
 * Shifter: GPIO4=UP, GPIO5=DOWN, GPIO6=AUX (switches to GND).
 * Handbrake: Hall GPIO0 OR HX711 DAT GPIO1 / CLK GPIO2.
 * OTA uses a temporary SoftAP on ESP-NOW channel 1; no GPIO25 dependency.
 ******************************************************************************/
#include "Config.h"
#include "Version.h"
#include "Inputs.h"
#include "ESPNowManager.h"
#if ENABLE_OTA
#include "OTAManager.h"
#endif

void setup()
{
#if ENABLE_SERIAL_DEBUG
    Serial.begin(SERIAL_BAUDRATE);
    delay(500);
    Serial.println();
    Serial.println("==========================================");
    Serial.println(FW_NAME);
    Serial.print("Version: "); Serial.println(FW_STRING);
    Serial.println("==========================================");
#endif

    if (!Inputs::begin()) {
#if ENABLE_SERIAL_DEBUG
        Serial.println("[ERROR] Inputs init failed");
#endif
        while (true) delay(1000);
    }
    if (!ESPNow::begin()) {
#if ENABLE_SERIAL_DEBUG
        Serial.println("[ERROR] ESP-NOW init failed");
#endif
        while (true) delay(1000);
    }

#if ENABLE_SERIAL_DEBUG
    Serial.println("Shifter + handbrake ready");
#endif

#if ENABLE_OTA
    // Start OTA only after ESP-NOW. AP+STA shares ESPNOW_CHANNEL.
    if (!OTA::begin()) {
#if ENABLE_SERIAL_DEBUG
        Serial.println("[WARNING] Handbrake OTA could not start");
#endif
    }
#endif
}

void loop()
{
    Inputs::update();
    ESPNow::update();
#if ENABLE_OTA
    OTA::update();
#endif
    delay(1);
}
