/******************************************************************************
 * Wheel Companion Ultra Lite — Pedals
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
    Serial.println("==========================================");

    Serial.printf("Version  : %s\n", FW_STRING);
    Serial.printf("Protocol : %s\n", PROTOCOL_STRING);

    PedalSensorFrame sensorStatus{};
    Inputs::getSensorStatus(sensorStatus);
    Serial.printf("Throttle sensor: %s\n", sensorStatus.throttleMode == static_cast<uint8_t>(PedalSensorMode::HX711) ? "HX711 LOAD CELL" : "ANALOG");
    Serial.printf("Brake sensor: %s\n", sensorStatus.brakeMode == static_cast<uint8_t>(PedalSensorMode::HX711) ? "HX711 LOAD CELL" : "ANALOG");
    Serial.printf("Clutch sensor: %s\n", sensorStatus.clutchMode == static_cast<uint8_t>(PedalSensorMode::HX711) ? "HX711 LOAD CELL" : "ANALOG");

#endif


    //=====================================================================
    // INPUTS
    //=====================================================================

    if (!Inputs::begin()) {

#if ENABLE_SERIAL_DEBUG

        Serial.println(
            "[ERROR] Inputs Initialization Failed"
        );

#endif

        while (true) {
            delay(1000);
        }
    }


    //=====================================================================
    // ESP-NOW
    //=====================================================================

    if (!ESPNow::begin()) {

#if ENABLE_SERIAL_DEBUG

        Serial.println(
            "[ERROR] ESP-NOW Initialization Failed"
        );

#endif

        while (true) {
            delay(1000);
        }
    }


#if ENABLE_SERIAL_DEBUG

    Serial.println();
    Serial.println("Pedal Module Ready");
    Serial.println();

#endif


    //=====================================================================
    // OTA
    //
    // OTA starts AFTER ESP-NOW.
    //
    // The SoftAP uses ESPNOW_CHANNEL (channel 1), so both functions
    // continue using the same physical Wi-Fi channel.
    //=====================================================================

#if ENABLE_OTA

    OTA::begin();

#endif
}


void loop()
{
    //=====================================================================
    // PEDAL INPUT UPDATE
    //=====================================================================

    Inputs::update();


    //=====================================================================
    // ESP-NOW TRANSMISSION
    //=====================================================================

    ESPNow::update();


    //=====================================================================
    // OTA WEB SERVER
    //=====================================================================

#if ENABLE_OTA

    OTA::update();

#endif


    //=====================================================================
    // DEBUG STATISTICS
    //=====================================================================

#if DEBUG_ESPNOW

    static uint32_t lastStats = 0;

    if ((millis() - lastStats) >= 5000) {

        lastStats = millis();

        ESPNow::printStatistics();
    }

#endif


    delay(1);
}
