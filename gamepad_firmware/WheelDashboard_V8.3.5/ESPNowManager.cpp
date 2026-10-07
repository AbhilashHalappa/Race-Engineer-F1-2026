/******************************************************************************
 * GamePad Pro V8
 * ESPNowManager.cpp — Wheel ESP32
 *
 * Wheel input still uses LegacyPacket (19 bytes). Receiver -> wheel dashboard
 * telemetry uses WheelDashboardPacket (21 bytes) so raw motor temperature can
 * be forwarded without changing the C3/wheel-input packet format.
 ******************************************************************************/

#include "ESPNowManager.h"

#include <esp_wifi.h>

#include "Config.h"
#include "Secrets.h"
#include "Dashboard.h"
#include "Inputs.h"

namespace
{

WheelDashboardExtendedPayload dashboardData = {};
PeerInfo receiver;

uint32_t wheelPacketsSent   = 0;
uint32_t dashboardPacketsRX = 0;
uint32_t duplicatePackets   = 0;
uint32_t invalidPackets     = 0;
uint32_t sendFailures       = 0;

uint16_t txSequence = 0;

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

bool validateSender(const esp_now_recv_info_t* info)
{
    return memcmp(info->src_addr, RECEIVER_MAC, 6) == 0;
}

bool isDuplicate(const WheelDashboardPacket& packet)
{
    return packet.header.sequence == receiver.lastSequence;
}

void updateReceiver(uint16_t sequence)
{
    receiver.connected = true;
    receiver.lastPacketTime = millis();
    receiver.lastSequence = sequence;
}

void onReceive(const esp_now_recv_info_t* info,
               const uint8_t* data,
               int len)
{
    if (len != static_cast<int>(sizeof(WheelDashboardPacket)))
    {
        invalidPackets++;
        return;
    }

    WheelDashboardPacket packet = {};
    memcpy(&packet, data, sizeof(packet));

    if (!validatePacketHeader(packet.header))
    {
        invalidPackets++;
        return;
    }

    if (!validateSender(info))
    {
        invalidPackets++;
#if DEBUG_ESPNOW
        Serial.println("[ESP-NOW] Unknown Sender");
#endif
        return;
    }

    if (packet.header.type != PacketType::DASHBOARD)
    {
        invalidPackets++;
        return;
    }

    if (isDuplicate(packet))
    {
        duplicatePackets++;
        return;
    }

    dashboardData = packet.dashboard;
    Dashboard::setData(dashboardData);
    updateReceiver(packet.header.sequence);
    dashboardPacketsRX++;
}

void onSent(const wifi_tx_info_t* txInfo, esp_now_send_status_t status)
{
    (void)txInfo;

    if (status == ESP_NOW_SEND_SUCCESS)
    {
        wheelPacketsSent++;
        return;
    }

    sendFailures++;

#if DEBUG_ESPNOW
    Serial.printf("[ESP-NOW] Send Failed (%d)\n", status);
#endif
}

} // namespace

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
    if (receiver.connected)
    {
        if ((millis() - receiver.lastPacketTime) > DASHBOARD_TIMEOUT_MS)
        {
            receiver.connected = false;
            // Receiver link is gone: never leave stale speed/RPM/DRS/ERS
            // indications frozen on the wheel. Clear telemetry immediately.
            dashboardData = {};
            dashboardData.motorTempCx100 = MOTOR_TEMP_INVALID_CX100;
            Dashboard::setData(dashboardData);
#if DEBUG_ESPNOW
            Serial.println("[ESP-NOW] Receiver Timeout");
#endif
        }
    }

    static uint32_t lastTransmit = 0;

    if ((millis() - lastTransmit) >= WHEEL_TX_INTERVAL_MS)
    {
        lastTransmit = millis();
        sendWheel(Inputs::getWheelData());
    }
}

bool ESPNow::sendWheel(const WheelPayload& wheel)
{
    LegacyPacket packet;
    initLegacyPacket(
        packet,
        PacketType::WHEEL,
        DeviceID::WHEEL,
        txSequence++);

    packet.wheel = wheel;

    const esp_err_t result = esp_now_send(
        RECEIVER_MAC,
        reinterpret_cast<uint8_t*>(&packet),
        sizeof(packet));

    if (result != ESP_OK)
    {
        sendFailures++;
#if DEBUG_ESPNOW
        Serial.printf("[ESP-NOW] Wheel Send Failed (%d)\n", result);
#endif
        return false;
    }

#if DEBUG_ESPNOW
    static uint32_t lastPrint = 0;
    if ((millis() - lastPrint) >= 1000)
    {
        lastPrint = millis();
        Serial.printf(
            "[ESP-NOW] Wheel TX  Buttons:%08lX  L:%u  R:%u\n",
            static_cast<unsigned long>(wheel.buttonState),
            wheel.clutchLeft,
            wheel.clutchRight);
    }
#endif

    return true;
}

const WheelDashboardExtendedPayload& ESPNow::getDashboardData()
{
    return dashboardData;
}

bool ESPNow::receiverConnected()
{
    return receiver.connected;
}

const PeerInfo& ESPNow::getReceiverState()
{
    return receiver;
}

uint32_t ESPNow::wheelPackets()
{
    return wheelPacketsSent;
}

uint32_t ESPNow::dashboardPackets()
{
    return dashboardPacketsRX;
}

void ESPNow::printStatistics()
{
#if DEBUG_ESPNOW
    Serial.println();
    Serial.println("=================================================");
    Serial.println("           ESP-NOW STATISTICS");
    Serial.println("=================================================");
    Serial.printf("Receiver Connected   : %s\n", receiver.connected ? "YES" : "NO");
    Serial.printf("Wheel Packets TX     : %lu\n", wheelPacketsSent);
    Serial.printf("Dashboard Packets RX : %lu\n", dashboardPacketsRX);
    Serial.printf("Duplicate Packets    : %lu\n", duplicatePackets);
    Serial.printf("Invalid Packets      : %lu\n", invalidPackets);
    Serial.printf("Send Failures        : %lu\n", sendFailures);
    Serial.printf("Last Sequence        : %u\n", receiver.lastSequence);
    Serial.println("=================================================");
#endif
}
