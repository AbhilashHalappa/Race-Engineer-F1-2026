/******************************************************************************
 * GamePad Pro V8.3.6 Ultra Lite
 * Receiver_S3.ino
 *
 * Main Firmware
 ******************************************************************************/

#include "Pins.h"
#include "Config.h"
#include "Protocol.h"
#include "Version.h"
#include "Secrets.h"
#include "Colors.h"

#include "ESPNowManager.h"
#include "RaceEngineerTelemetry.h"
#include "LinkHealth.h"
#include "Gamepad.h"
#include "StatusLED.h"
#include "PedalCalibration.h"


//=============================================================================
// Setup
//=============================================================================

void setup()
{
    // One USB-C cable is used as a composite USB device:
    //   1) USB CDC compact Race Engineer telemetry
    //   2) USB HID gamepad
    //
    // Register HID before USB.begin(). Gamepad::begin() performs both.
    Serial.begin(SERIAL_BAUDRATE);

    StatusLED::begin();
    Gamepad::begin();

    // Give Windows time to enumerate the CDC + HID composite device.
    delay(1000);

#if ENABLE_SERIAL_DEBUG
    Serial.println();
    Serial.println("======================================");
    Serial.println(FW_NAME);
    Serial.print("Firmware : ");
    Serial.println(FW_STRING);
    Serial.print("Protocol : ");
    Serial.println(PROTOCOL_STRING);
    Serial.println("Board    : ESP32-S3 Zero / One USB");
    Serial.println("======================================");
#endif

#if ENABLE_RACE_ENGINEER
    RaceEngineerTelemetry::begin();
    LinkHealth::begin();
#endif
    PedalCalibration::begin();

    if (!ESPNow::begin())
    {
#if ENABLE_SERIAL_DEBUG
        Serial.println("ESP-NOW FAILED");
#endif
        StatusLED::setError();

        while (true)
        {
            StatusLED::update();
            delay(10);
        }
    }

    StatusLED::setReady();

#if ENABLE_SERIAL_DEBUG
    Serial.println("Receiver Ready");
#endif
}

//=============================================================================
// Main Loop
//=============================================================================

void loop()
{
    //----------------------------------------------------------
    // Highest priority: publish the latest wheel/pedal state to USB HID
    //----------------------------------------------------------
    // ESP-NOW receive callbacks update the snapshots asynchronously. Running
    // HID first ensures LCD telemetry work can never delay control input.

    Gamepad::update();

    //----------------------------------------------------------
    // Receive compact Race Engineer telemetry
    //----------------------------------------------------------

#if ENABLE_RACE_ENGINEER
    RaceEngineerTelemetry::update();

    static uint32_t lastDashTx = 0;
    if ((millis() - lastDashTx) >= DASHBOARD_TX_INTERVAL_MS)
    {
        lastDashTx = millis();
        // Keep forwarding at 50 Hz even if the PC telemetry stream stops.
        // A stale PC link therefore becomes a safe zeroed dashboard while the
        // independent MotorTemp C3 reading continues to reach the wheel.
        if (RaceEngineerTelemetry::hasData())
        {
            ESPNow::sendDashboard(RaceEngineerTelemetry::getDashboard());
        }
        else
        {
            const WheelDashboardPayload safeDashboard = {};
            ESPNow::sendDashboard(safeDashboard);
        }
    }
#endif

    //----------------------------------------------------------
    // Process ESP-NOW
    //----------------------------------------------------------

    ESPNow::update();

#if ENABLE_RACE_ENGINEER
    // 2 Hz full-duplex USB CDC status back to the PC. This reports wheel,
    // pedals and MotorTemp peer health without touching the HID path.
    LinkHealth::update();
#endif

    //----------------------------------------------------------
    // Update Connection Status LED
    //----------------------------------------------------------

    if (ESPNow::wheelConnected() && ESPNow::pedalsConnected() && ESPNow::motorTempConnected())
    {
        StatusLED::setConnected();        // Green: wheel + pedals + temp all healthy
    }
    else if (!ESPNow::wheelConnected() && ESPNow::pedalsConnected())
    {
        StatusLED::setWaitingWheel();     // Yellow
    }
    else if (ESPNow::wheelConnected() && !ESPNow::pedalsConnected())
    {
        StatusLED::setWaitingPedals();    // Orange
    }
    else if (ESPNow::wheelConnected() && ESPNow::pedalsConnected() && !ESPNow::motorTempConnected())
    {
        StatusLED::setWaitingMotorTemp(); // Purple: controls OK, temp peer missing
    }
    else
    {
        StatusLED::setReady();            // Cyan: wheel + pedals both missing
    }

    //----------------------------------------------------------
    // Update RGB Status LED
    //----------------------------------------------------------

    StatusLED::update();

    // Yield to the USB and Wi-Fi system tasks. A 1 ms yield keeps the
    // 200 Hz wheel input responsive while allowing the CPU to idle.
    delay(1);
}