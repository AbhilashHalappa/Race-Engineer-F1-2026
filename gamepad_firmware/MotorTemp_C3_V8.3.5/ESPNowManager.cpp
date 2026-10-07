/******************************************************************************
 * GamePad Pro V8
 * ESPNowManager.cpp — MotorTemp ESP32-C3 → receiver
 ******************************************************************************/

#include "ESPNowManager.h"

#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

#include "Config.h"
#include "Secrets.h"
#include "Protocol.h"
#include "GameNetwork.h"
#include "TempSensor.h"

namespace
{
    PeerInfo receiver;
    uint16_t txSequence = 0;
    uint32_t lastTxMs = 0;
    uint32_t sendOk = 0;
    uint32_t sendFail = 0;

    bool addPeer(const uint8_t* mac)
    {
        esp_now_peer_info_t peer = {};
        memcpy(peer.peer_addr, mac, 6);
        peer.channel = ESPNOW_CHANNEL;
        peer.encrypt = false;
        peer.ifidx = WIFI_IF_STA;
        return esp_now_add_peer(&peer) == ESP_OK;
    }

    void onSent(const wifi_tx_info_t*, esp_now_send_status_t status)
    {
        if (status == ESP_NOW_SEND_SUCCESS)
        {
            sendOk++;
        }
        else
        {
            sendFail++;
        }
    }
}

bool ESPNow::begin()
{
    WiFi.mode(WIFI_STA);

// Keep Wi-Fi radio enabled for ESP-NOW
WiFi.disconnect(false, true);

WiFi.setSleep(false);
delay(200);

    if (esp_wifi_set_channel(ESPNOW_CHANNEL, WIFI_SECOND_CHAN_NONE) != ESP_OK)
    {
        return false;
    }

    if (esp_now_init() != ESP_OK)
    {
        return false;
    }

    esp_now_register_send_cb(onSent);

    if (!addPeer(RECEIVER_MAC))
    {
        return false;
    }

    resetPeer(receiver);
    receiver.device = DeviceID::RECEIVER;

#if ENABLE_SERIAL_DEBUG
    Serial.printf(
        "[ESP-NOW] STA MAC %s → receiver\n",
        WiFi.macAddress().c_str());
#endif

    return true;
}

void ESPNow::update()
{
    const uint32_t now = millis();
    if ((now - lastTxMs) < TEMP_TX_INTERVAL_MS)
    {
        return;
    }
    lastTxMs = now;

    LegacyPacket packet;
    initLegacyPacket(
        packet,
        PacketType::MOTOR_TEMP,
        DeviceID::MOTOR_TEMP,
        txSequence++);

    packet.motorTemp = TempSensor::getPayload();

    const esp_err_t result = esp_now_send(
        RECEIVER_MAC,
        reinterpret_cast<const uint8_t*>(&packet),
        sizeof(packet));

#if DEBUG_ESPNOW
    if (result != ESP_OK)
    {
        Serial.printf("[ESP-NOW] send failed %d\n", result);
    }
#else
    (void)result;
#endif
}
