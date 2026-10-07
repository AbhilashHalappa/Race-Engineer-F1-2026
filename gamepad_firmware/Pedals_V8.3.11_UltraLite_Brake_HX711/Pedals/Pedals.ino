
/******************************************************************************
 * GamePad Pro V8
 * Pedals.ino
 *
 * ESP32 WROOM - Pedal Module
 ******************************************************************************/

#include "Config.h"
#include "Version.h"

#include "Inputs.h"
#include "ESPNowManager.h"

//=============================================================================
// Setup
//=============================================================================

void setup()
{
    //---------------------------------------------------------------------
    // Serial
    //---------------------------------------------------------------------

#if ENABLE_SERIAL_DEBUG

    Serial.begin(SERIAL_BAUDRATE);

    delay(500);

    Serial.println();
    Serial.println("==========================================");
    Serial.println("      GamePad Pro V8 - Pedals");
    Serial.println("==========================================");
    Serial.printf("Version : %s\n", FW_STRING);
#if BRAKE_SENSOR_MODE == BRAKE_SENSOR_HX711
    Serial.println("Brake sensor: HX711 LOAD CELL");
#else
    Serial.println("Brake sensor: ANALOG POSITION");
#endif

#endif

    //---------------------------------------------------------------------
    // Initialize Inputs
    //---------------------------------------------------------------------

    if (!Inputs::begin())
    {
#if ENABLE_SERIAL_DEBUG
        Serial.println("[ERROR] Inputs Initialization Failed");
#endif

        while (true)
        {
            delay(1000);
        }
    }

    //---------------------------------------------------------------------
    // Initialize ESP-NOW
    //---------------------------------------------------------------------

    if (!ESPNow::begin())
    {
#if ENABLE_SERIAL_DEBUG
        Serial.println("[ERROR] ESP-NOW Initialization Failed");
#endif

        while (true)
        {
            delay(1000);
        }
    }

#if ENABLE_SERIAL_DEBUG

    Serial.println();
    Serial.println("Pedal Module Ready");
    Serial.println();

#endif
}

//=============================================================================
// Loop
//=============================================================================

void loop()
{
    //---------------------------------------------------------------------
    // Read Inputs
    //---------------------------------------------------------------------

    Inputs::update();

    //---------------------------------------------------------------------
    // Handle ESP-NOW
    //---------------------------------------------------------------------

    ESPNow::update();

    //---------------------------------------------------------------------
    // Debug Statistics
    //---------------------------------------------------------------------

#if DEBUG_ESPNOW

    static uint32_t lastStats = 0;

    if ((millis() - lastStats) >= 5000)
    {
        lastStats = millis();

        ESPNow::printStatistics();
    }

#endif

    //---------------------------------------------------------------------
    // Small Yield
    //---------------------------------------------------------------------

    delay(1);
}