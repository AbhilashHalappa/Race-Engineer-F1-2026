#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

#include "Config.h"
#include "Pins.h"
#include "RpmLedProtocol.h"
#include "RpmLedReceiver.h"
#include "RpmLedController.h"
#include "Version.h"
#if ENABLE_OTA
#include "OTAManager.h"
#endif

void setup()
{
    Serial.begin(115200);
    Serial.println();
    Serial.println(FW_NAME);
    Serial.printf("Version: %s\\n", FW_STRING);
    delay(100);
    RpmLedController::begin();

    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    const esp_err_t channelResult = esp_wifi_set_channel(ESPNOW_CHANNEL, WIFI_SECOND_CHAN_NONE);
    if (channelResult != ESP_OK) {
        Serial.printf("[RPM LED] Channel setup failed: %d\n", channelResult);
    }

    if (esp_now_init() != ESP_OK) {
        Serial.println("[RPM LED] ESP-NOW init failed");
        while (true) delay(1000);
    }

    esp_now_register_recv_cb(RpmLedReceiver::onReceive);

#if ENABLE_OTA
    // Start OTA after ESP-NOW, matching the working Pedals implementation.
    OTA::begin();
#endif
    Serial.println("[RPM LED] WROOM controller ready");
    Serial.print("[RPM LED] STA MAC: ");
    Serial.println(WiFi.macAddress());
}

void loop()
{
    RpmLedReceiver::update();
#if ENABLE_OTA
    OTA::update();
#endif
    RpmLedController::update(
        RpmLedReceiver::rpmPercent(),
        RpmLedReceiver::shiftLight(),
        RpmLedReceiver::hasFreshData());
    delay(1);
}
