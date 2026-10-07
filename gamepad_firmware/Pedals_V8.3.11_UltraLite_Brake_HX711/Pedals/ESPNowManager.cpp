/******************************************************************************
 * GamePad Pro V8
 * ESPNowManager.cpp — Pedals ESP32
 *
 * Uses LegacyPacket (19 bytes) for receiver compatibility.
 ******************************************************************************/

#include "ESPNowManager.h"

#include <esp_wifi.h>

#include "Config.h"
#include "Secrets.h"
#include "Inputs.h"

namespace
{

PeerInfo receiver;

uint32_t pedalPacketsSent = 0;
uint32_t sendFailures     = 0;
uint16_t txSequence       = 0;

bool addPeer(const uint8_t* mac)
{
    esp_now_peer_info_t peer = {};
    memcpy(peer.peer_addr, mac, 6);
    peer.channel = ESPNOW_CHANNEL;
    peer.encrypt = false;

    const esp_err_t result = esp_now_add_peer(&peer);

#if DEBUG_ESPNOW
    if (result == ESP_OK)
    {
        Serial.printf(
            "[ESP-NOW] Peer Added : %02X:%02X:%02X:%02X:%02X:%02X\n",
            mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    }
    else
    {
        Serial.printf("[ESP-NOW] Failed To Add Peer (%d)\n", result);
    }
#endif

    return result == ESP_OK;
}

} // namespace

void onReceive(const esp_now_recv_info_t* info,
               const uint8_t* data,
               int len)
{
    (void)info;
    (void)data;
    (void)len;
}

static void onSent(const wifi_tx_info_t*, esp_now_send_status_t status)
{
    if (status == ESP_NOW_SEND_SUCCESS)
    {
        pedalPacketsSent++;
        return;
    }

    sendFailures++;

#if DEBUG_ESPNOW
    Serial.printf("[ESP-NOW] Pedal Send Failed (%d)\n", status);
#endif
}

bool ESPNow::begin()
{
    WiFi.mode(WIFI_STA);
    WiFi.disconnect(true, true);
    WiFi.setSleep(false);
    delay(100);

    if (esp_wifi_set_channel(ESPNOW_CHANNEL, WIFI_SECOND_CHAN_NONE) != ESP_OK)
    {
#if DEBUG_ESPNOW
        Serial.println("[ESP-NOW] Failed to set WiFi channel");
#endif
        return false;
    }

    if (esp_now_init() != ESP_OK)
    {
#if DEBUG_ESPNOW
        Serial.println("[ESP-NOW] Initialization Failed");
#endif
        return false;
    }

    esp_now_register_recv_cb(onReceive);
    esp_now_register_send_cb(onSent);

    if (!addPeer(RECEIVER_MAC))
    {
        return false;
    }

    resetPeer(receiver);
    receiver.device = DeviceID::RECEIVER;

#if DEBUG_ESPNOW
    Serial.println("ESP-NOW Initialized");
#endif

    return true;
}

void ESPNow::update()
{
    static uint32_t lastTransmit = 0;

    if ((millis() - lastTransmit) >= PEDAL_TX_INTERVAL_MS)
    {
        lastTransmit = millis();
        sendPedals(Inputs::getPedalData());
    }
}

bool ESPNow::sendPedals(const PedalPayload& pedals)
{
    LegacyPacket packet;
    initLegacyPacket(
        packet,
        PacketType::PEDALS,
        DeviceID::PEDALS,
        txSequence++);

    packet.pedals = pedals;

    const esp_err_t result = esp_now_send(
        RECEIVER_MAC,
        reinterpret_cast<uint8_t*>(&packet),
        sizeof(packet));

    if (result != ESP_OK)
    {
        sendFailures++;
#if DEBUG_ESPNOW
        Serial.printf("[ESP-NOW] Pedal Send Failed (%d)\n", result);
#endif
        return false;
    }

#if DEBUG_ESPNOW
    static uint32_t lastPrint = 0;
    if ((millis() - lastPrint) >= 1000)
    {
        lastPrint = millis();
        Serial.printf(
            "[ESP-NOW] Pedals TX  Throttle:%u  Brake:%u  Clutch:%u\n",
            pedals.throttle,
            pedals.brake,
            pedals.clutch);
    }
#endif

    return true;
}

bool ESPNow::receiverConnected()
{
    return receiver.connected;
}

const PeerInfo& ESPNow::getReceiverState()
{
    return receiver;
}

uint32_t ESPNow::pedalPackets()
{
    return pedalPacketsSent;
}

void ESPNow::printStatistics()
{
#if DEBUG_ESPNOW
    Serial.println();
    Serial.println("=================================================");
    Serial.println("           ESP-NOW STATISTICS");
    Serial.println("=================================================");
    Serial.printf("Receiver Connected   : %s\n", receiver.connected ? "YES" : "NO");
    Serial.printf("Pedal Packets TX     : %lu\n", pedalPacketsSent);
    Serial.printf("Send Failures        : %lu\n", sendFailures);
    Serial.printf("Last Sequence        : %u\n", txSequence);
    Serial.println("=================================================");
#endif
}
