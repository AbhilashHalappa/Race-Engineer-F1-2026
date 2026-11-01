#include "ESPNowManager.h"
#include <esp_wifi.h>
#include "Config.h"
#include "Secrets.h"
#include "Inputs.h"
#include "HandbrakeSensorProtocol.h"

namespace
{
uint16_t txSequence = 0;
uint32_t txPackets = 0;
uint32_t txFailures = 0;
portMUX_TYPE commandMux = portMUX_INITIALIZER_UNLOCKED;
HandbrakeSensorFrame queuedCommand{};
volatile bool commandPending = false;

static void onReceive(const esp_now_recv_info_t* info, const uint8_t* data, int len)
{
    if (!info || !data || len != static_cast<int>(sizeof(HandbrakeSensorFrame)) || memcmp(info->src_addr, RECEIVER_MAC, 6) != 0) return;
    HandbrakeSensorFrame frame{};
    memcpy(&frame, data, sizeof(frame));
    if (!handbrakeSensorValidateFrame(frame) || frame.kind != HandbrakeSensorFrameKind::COMMAND) return;
    portENTER_CRITICAL(&commandMux);
    queuedCommand = frame;
    commandPending = true;
    portEXIT_CRITICAL(&commandMux);
}

bool addReceiverPeer()
{
    esp_now_peer_info_t peer = {};
    memcpy(peer.peer_addr, RECEIVER_MAC, 6);
    peer.channel = ESPNOW_CHANNEL;
    peer.encrypt = false;
    return esp_now_add_peer(&peer) == ESP_OK;
}

static void onSent(const wifi_tx_info_t*, esp_now_send_status_t status)
{
    if (status == ESP_NOW_SEND_SUCCESS)
        ++txPackets;
    else
        ++txFailures;
}
}

bool ESPNow::begin()
{
    // Keep the radio ON in station mode for ESP-NOW.
    // IMPORTANT: WiFi.disconnect(true, true) powers Wi-Fi off and causes
    // a 00:00:00:00:00:00 MAC / esp_now_init() failure on ESP32-C3.
    WiFi.mode(WIFI_STA);
    delay(100);
    WiFi.disconnect(false, true);   // forget old AP credentials, keep radio on
    WiFi.setSleep(false);
    delay(100);

#if ENABLE_SERIAL_DEBUG
    Serial.print("Shifter C3 STA MAC: ");
    Serial.println(WiFi.macAddress());
#endif

    if (esp_wifi_set_channel(ESPNOW_CHANNEL, WIFI_SECOND_CHAN_NONE) != ESP_OK)
        return false;

    if (esp_now_init() != ESP_OK)
        return false;

    esp_now_register_send_cb(onSent);
    esp_now_register_recv_cb(onReceive);
    return addReceiverPeer();
}

void ESPNow::update()
{
    static uint32_t lastTx = 0;
    const uint32_t now = millis();

    HandbrakeSensorFrame command{};
    bool haveCommand = false;
    portENTER_CRITICAL(&commandMux);
    if (commandPending) { command = queuedCommand; commandPending = false; haveCommand = true; }
    portEXIT_CRITICAL(&commandMux);
    if (haveCommand) {
        HandbrakeSensorFrame response{};
        Inputs::handleCommand(command, response);
        esp_now_send(RECEIVER_MAC, reinterpret_cast<const uint8_t*>(&response), sizeof(response));
    }

    if ((now - lastTx) >= SHIFTER_TX_INTERVAL_MS)
    {
        lastTx = now;
        sendShifter(Inputs::getShifterData());
    }
}

bool ESPNow::sendShifter(const ShifterPayload& shifter)
{
    LegacyPacket packet;
    initLegacyPacket(packet, PacketType::SHIFTER, DeviceID::SHIFTER, txSequence++);
    packet.shifter = shifter;

    const esp_err_t result = esp_now_send(
        RECEIVER_MAC,
        reinterpret_cast<const uint8_t*>(&packet),
        sizeof(packet));

    if (result != ESP_OK)
    {
        ++txFailures;
        return false;
    }
    return true;
}

uint32_t ESPNow::packetsSent() { return txPackets; }
uint32_t ESPNow::sendFailures() { return txFailures; }
