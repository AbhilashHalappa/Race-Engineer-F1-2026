/******************************************************************************
 * GamePad Pro V8
 * MotorTemp_C3.ino — ESP32-C3 + 10K NTC motor temperature → receiver (ESP-NOW)
 ******************************************************************************/

#include "Config.h"
#include "Version.h"

#include "TempSensor.h"
#include "ESPNowManager.h"

void setup()
{
#if ENABLE_SERIAL_DEBUG
    Serial.begin(SERIAL_BAUDRATE);
    delay(500);
    Serial.println();
    Serial.println("==========================================");
    Serial.println("   GamePad Pro V8 - Motor Temp (C3)");
    Serial.println("==========================================");
    Serial.printf("Version : %s\n", FW_STRING);
    Serial.println("Sensor  : 10K NTC (2-wire)");
#endif

    if (!TempSensor::begin())
    {
#if ENABLE_SERIAL_DEBUG
        Serial.println("[ERROR] NTC init failed");
#endif
        while (true)
        {
            delay(1000);
        }
    }

    if (!ESPNow::begin())
    {
#if ENABLE_SERIAL_DEBUG
        Serial.println("[ERROR] ESP-NOW init failed");
#endif
        while (true)
        {
            delay(1000);
        }
    }

#if ENABLE_SERIAL_DEBUG
    Serial.println("Motor temp module ready");
#endif
}

void loop()
{
    TempSensor::update();
    ESPNow::update();
}
