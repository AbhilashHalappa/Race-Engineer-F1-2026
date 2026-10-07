/******************************************************************************
 * GamePad Pro V8
 * WheelDashboard.ino
 *
 * ESP32 Wheel Transmitter
 ******************************************************************************/

#include "Config.h"
#include "Version.h"

#include "Inputs.h"
#include "Dashboard.h"
#include "ESPNowManager.h"

//=============================================================================
// Setup
//=============================================================================

void setup()
{
#if ENABLE_SERIAL_DEBUG
    Serial.begin(SERIAL_BAUDRATE);

    delay(1000);

    Serial.println();
    Serial.println("========================================");
    Serial.println(FW_NAME);
    Serial.println(FW_STRING);
    Serial.println("Wheel Dashboard");
    Serial.println("========================================");
#endif

    //--------------------------------------------------------------
    // Inputs
    //--------------------------------------------------------------

    Inputs::begin();

    //--------------------------------------------------------------
    // Dashboard Manager
    // Initializes MAX7219 display and RPM LED bar internally
    //--------------------------------------------------------------

    Dashboard::begin();

    //--------------------------------------------------------------
    // ESP-NOW
    //--------------------------------------------------------------

    if (!ESPNow::begin())
    {
#if ENABLE_SERIAL_DEBUG
        Serial.println("ESP-NOW Initialization Failed");
#endif

        while (true)
        {
            delay(250);
        }
    }

#if ENABLE_SERIAL_DEBUG
    Serial.println("Wheel Ready");
#endif
}

//=============================================================================
// Main Loop
//=============================================================================

void loop()
{
    //--------------------------------------------------------------
    // Read Wheel Inputs
    //--------------------------------------------------------------

    Inputs::update();

    //--------------------------------------------------------------
    // ESP-NOW Communication
    //--------------------------------------------------------------

    ESPNow::update();

    //--------------------------------------------------------------
    // Dashboard
    //--------------------------------------------------------------

    Dashboard::update();

#if DEBUG_ESPNOW

    //--------------------------------------------------------------
    // Print Statistics Every 5 Seconds
    //--------------------------------------------------------------

    static uint32_t lastStats = 0;

    if (millis() - lastStats >= 5000)
    {
        lastStats = millis();

        ESPNow::printStatistics();
    }

#endif
}
