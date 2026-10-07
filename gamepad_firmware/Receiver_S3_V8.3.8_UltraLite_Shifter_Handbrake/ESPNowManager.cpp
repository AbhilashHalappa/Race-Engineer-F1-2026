/******************************************************************************
 * GamePad Pro V8
 * ESPNowManager.cpp
 ******************************************************************************/

#include "ESPNowManager.h"

#include <esp_wifi.h>

#include "Config.h"
#include "Secrets.h"
#include "Gamepad.h"

//=============================================================================
// Local Variables
//=============================================================================

namespace
{

//-----------------------------------------------------------------------------
// Latest Received Data
//-----------------------------------------------------------------------------

WheelPayload wheelData = {};
PedalPayload pedalData = {};
ShifterPayload shifterData = {};

MotorTempPayload motorTempData = {};
uint32_t motorTempLastMs = 0;
uint32_t motorTempPacketsReceived = 0;

//-----------------------------------------------------------------------------
// Network State
//-----------------------------------------------------------------------------

ReceiverNetworkState network;

//-----------------------------------------------------------------------------
// Statistics
//-----------------------------------------------------------------------------

uint32_t wheelPacketsReceived = 0;
uint32_t pedalPacketsReceived = 0;
uint32_t shifterPacketsReceived = 0;

uint32_t dashboardPacketsSent = 0;

uint32_t duplicatePackets = 0;
uint32_t invalidPackets = 0;
uint32_t sendFailures = 0;

//-----------------------------------------------------------------------------
// Sequence Counter and non-blocking priority TX queue
//-----------------------------------------------------------------------------

uint16_t txSequence = 0;

WheelDashboardPayload queuedDashboard = {};
uint16_t queuedSequence = 0;

bool wheelTxPending = false;

volatile bool txBusy = false;

//-----------------------------------------------------------------------------
// Send at most one ESP-NOW packet at a time
//-----------------------------------------------------------------------------
//
// Priority is always:
//   1. Steering-wheel dashboard packet (small unicast LegacyPacket)
//   2. LCD dashboard packet (best-effort broadcast Packet)
//
// There is intentionally no retry queue. If the Wi-Fi driver cannot accept a
// frame immediately, that stale frame is dropped and the next fresh telemetry
// snapshot is used. This prevents any output device from building latency.

void processTxQueue()
{
    if (txBusy || !wheelTxPending)
    {
        return;
    }

    if (!network.wheel.connected)
    {
        wheelTxPending = false;
        return;
    }

    WheelDashboardPacket packet;
    initWheelDashboardPacket(packet, queuedSequence);

    packet.dashboard.speed      = queuedDashboard.speed;
    packet.dashboard.gear       = queuedDashboard.gear;
    packet.dashboard.position   = queuedDashboard.position;
    packet.dashboard.rpmPercent = queuedDashboard.rpmPercent;
    packet.dashboard.shiftLight = queuedDashboard.shiftLight;
    packet.dashboard.flagStatus = queuedDashboard.flagStatus;
    packet.dashboard.ersMode    = queuedDashboard.ersMode;
    packet.dashboard.statusBits = queuedDashboard.statusBits;

    // Motor temperature remains independent of PC telemetry and is still
    // supplied by the existing ESP32-C3 sensor path.
    if (motorTempData.valid != 0 &&
        (millis() - motorTempLastMs) <= MOTOR_TEMP_TIMEOUT_MS)
    {
        packet.dashboard.motorTempCx100 = motorTempData.tempCx100;
    }
    else
    {
        packet.dashboard.motorTempCx100 = MOTOR_TEMP_INVALID_CX100;
    }

    txBusy = true;
    const esp_err_t result = esp_now_send(
        WHEEL_MAC,
        reinterpret_cast<const uint8_t*>(&packet),
        sizeof(packet));

    wheelTxPending = false;
    if (result != ESP_OK)
    {
        txBusy = false;
        ++sendFailures;
    }
}

//=============================================================================
// Add ESP-NOW Peer
//=============================================================================

bool addPeer(const uint8_t *mac)
{
    esp_now_peer_info_t peer = {};

    memcpy(peer.peer_addr, mac, 6);

    peer.channel = ESPNOW_CHANNEL;
    peer.encrypt = false;

    esp_err_t result = esp_now_add_peer(&peer);

#if DEBUG_ESPNOW
    if (result == ESP_OK)
    {
        Serial.printf(
            "[ESP-NOW] Peer Added : %02X:%02X:%02X:%02X:%02X:%02X\n",
            mac[0], mac[1], mac[2],
            mac[3], mac[4], mac[5]);
    }
    else
    {
        Serial.printf(
            "[ESP-NOW] Failed To Add Peer (%d)\n",
            result);
    }
#endif

    return (result == ESP_OK);
}

//=============================================================================
// Validate Sender
//=============================================================================

bool validateSender(const Packet& packet,
                    const esp_now_recv_info_t* info)
{
    switch (packet.header.type)
    {
        //-------------------------------------------------------------
        // Wheel
        //-------------------------------------------------------------

        case PacketType::WHEEL:

            return (memcmp(
                        info->src_addr,
                        WHEEL_MAC,
                        6) == 0);

        //-------------------------------------------------------------
        // Pedals
        //-------------------------------------------------------------

        case PacketType::PEDALS:

            return (memcmp(
                        info->src_addr,
                        PEDALS_MAC,
                        6) == 0);

        case PacketType::MOTOR_TEMP:

            return (memcmp(
                        info->src_addr,
                        MOTOR_TEMP_MAC,
                        6) == 0);

        case PacketType::SHIFTER:

            return (memcmp(
                        info->src_addr,
                        SHIFTER_MAC,
                        6) == 0);

        //-------------------------------------------------------------
        // Unknown
        //-------------------------------------------------------------

        default:

            return false;
    }
}

//=============================================================================
// Check Duplicate Packet
//=============================================================================

bool isDuplicate(const Packet& packet)
{
    switch (packet.header.type)
    {
        case PacketType::WHEEL:

            return packet.header.sequence ==
                   network.wheel.lastSequence;

        case PacketType::PEDALS:

            return packet.header.sequence ==
                   network.pedals.lastSequence;

        case PacketType::MOTOR_TEMP:

            return packet.header.sequence ==
                   network.motorTemp.lastSequence;

        case PacketType::SHIFTER:

            return packet.header.sequence ==
                   network.shifter.lastSequence;

        default:

            return false;
    }
}

//=============================================================================
// Update Peer State
//=============================================================================

void updatePeer(PeerInfo& peer,
                uint16_t sequence)
{
    peer.connected = true;

    peer.lastPacketTime = millis();

    peer.lastSequence = sequence;
}



//=============================================================================
// ESP-NOW Receive Callback
//=============================================================================

void onReceive(const esp_now_recv_info_t *info,
               const uint8_t *data,
               int len)
{
    if (info == nullptr || data == nullptr)
    {
        invalidPackets++;
        return;
    }

    //---------------------------------------------------------------------
    // Accept both packet generations
    //---------------------------------------------------------------------
    // Existing wheel/pedal firmware sends LegacyPacket (19 bytes).
    // The expanded LCD protocol uses Packet (77 bytes).

    if (len != static_cast<int>(sizeof(LegacyPacket)) &&
        len != static_cast<int>(sizeof(Packet)))
    {
        invalidPackets++;
        return;
    }

    // Zero-fill the expanded packet, then copy the received bytes.
    // The header and wheel/pedal payload offsets are identical in both
    // formats, so legacy packets can be processed safely.
    Packet packet = {};
    memcpy(&packet, data, static_cast<size_t>(len));

    //---------------------------------------------------------------------
    // Validate Protocol
    //---------------------------------------------------------------------

    if (!validatePacket(packet))
    {
        invalidPackets++;
        return;
    }

    //---------------------------------------------------------------------
    // Validate Sender MAC
    //---------------------------------------------------------------------

    if (!validateSender(packet, info))
    {
        invalidPackets++;

#if DEBUG_ESPNOW
        Serial.println("[ESP-NOW] Unknown Sender");
#endif
        return;
    }

    //---------------------------------------------------------------------
    // Ignore Duplicate Packets
    //---------------------------------------------------------------------

    if (isDuplicate(packet))
    {
        duplicatePackets++;
        return;
    }

    //---------------------------------------------------------------------
    // Process Packet
    //---------------------------------------------------------------------

    switch (packet.header.type)
    {
        case PacketType::WHEEL:
        {
            wheelData = packet.wheel;

            Gamepad::setWheelData(wheelData);

            updatePeer(network.wheel, packet.header.sequence);

            wheelPacketsReceived++;
            break;
        }

        case PacketType::PEDALS:
        {
            // The installed pedal loom has the two ADC channels physically
            // reversed relative to the legacy PedalPayload names. Normalize the
            // pair once at Receiver ingress so every downstream consumer sees
            // the same semantic axes: HID Z=Throttle, HID RZ=Brake, Wheel
            // Companion live values, and the saved response curves.
#if SWAP_PEDAL_AXES
            pedalData.throttle = packet.pedals.brake;
            pedalData.brake    = packet.pedals.throttle;
            pedalData.clutch   = packet.pedals.clutch;
#else
            pedalData = packet.pedals;
#endif

            Gamepad::setPedalData(pedalData);

            updatePeer(network.pedals, packet.header.sequence);

            pedalPacketsReceived++;
            break;
        }

        case PacketType::SHIFTER:
        {
            shifterData = packet.shifter;
            shifterData.buttonState &= 0x07u;

            Gamepad::setShifterData(shifterData);

            updatePeer(network.shifter, packet.header.sequence);

            shifterPacketsReceived++;
            break;
        }

        case PacketType::MOTOR_TEMP:
        {
            motorTempData = packet.motorTemp;
            motorTempLastMs = millis();

            updatePeer(network.motorTemp, packet.header.sequence);

            motorTempPacketsReceived++;
            break;
        }

        default:
            break;
    }
}

//=============================================================================
// ESP-NOW Send Callback
//=============================================================================

static void onSent(
    const wifi_tx_info_t *,
    esp_now_send_status_t status)
{
    // Keep the Wi-Fi callback short. Serial output here can block the high
    // priority Wi-Fi task and also competes with the USB HID/CDC interface.
    if (status == ESP_NOW_SEND_SUCCESS)
    {
        dashboardPacketsSent++;
    }
    else
    {
        sendFailures++;
    }

    txBusy = false;
}

} // namespace

//=============================================================================
// Initialize ESP-NOW
//=============================================================================

bool ESPNow::begin()
{
    //---------------------------------------------------------------------
    // WiFi Station Mode
    //---------------------------------------------------------------------

    WiFi.mode(WIFI_STA);

    WiFi.disconnect();

    // The devices are all close to the receiver. Limiting the radio to
    // 11 dBm reduces current and heat while retaining comfortable range.
    // Failure is non-fatal so the firmware remains compatible across cores.
    const esp_err_t txPowerResult =
        esp_wifi_set_max_tx_power(ESPNOW_TX_POWER_QDBM);

#if DEBUG_ESPNOW
    if (txPowerResult != ESP_OK)
    {
        Serial.printf(
            "[ESP-NOW] TX power setting failed (%d)\n",
            txPowerResult
        );
    }
#endif

    //---------------------------------------------------------------------
    // Set WiFi Channel
    //---------------------------------------------------------------------

    if (esp_wifi_set_channel(
            ESPNOW_CHANNEL,
            WIFI_SECOND_CHAN_NONE) != ESP_OK)
    {
#if DEBUG_ESPNOW
        Serial.println("[ESP-NOW] Failed to set WiFi channel");
#endif
        return false;
    }

    //---------------------------------------------------------------------
    // Initialize ESP-NOW
    //---------------------------------------------------------------------

    if (esp_now_init() != ESP_OK)
    {
#if DEBUG_ESPNOW
        Serial.println("[ESP-NOW] Initialization Failed");
#endif
        return false;
    }

    //---------------------------------------------------------------------
    // Register Callbacks
    //---------------------------------------------------------------------

    esp_now_register_recv_cb(onReceive);

    esp_now_register_send_cb(onSent);

    //---------------------------------------------------------------------
    // Register Wheel
    //---------------------------------------------------------------------

    if (!addPeer(WHEEL_MAC))
    {
        return false;
    }

    //---------------------------------------------------------------------
    // Register Pedals
    //---------------------------------------------------------------------

    if (!addPeer(PEDALS_MAC))
    {
        return false;
    }

    // Motor-temp C3 is TX-only toward the receiver; no peer add required for
    // RX. MAC is checked in validateSender via MOTOR_TEMP_MAC.

    //---------------------------------------------------------------------
    // Initialize Network State
    //---------------------------------------------------------------------

    resetPeer(network.wheel);
    network.wheel.device = DeviceID::WHEEL;

    resetPeer(network.pedals);
    network.pedals.device = DeviceID::PEDALS;

    resetPeer(network.motorTemp);
    network.motorTemp.device = DeviceID::MOTOR_TEMP;

    resetPeer(network.shifter);
    network.shifter.device = DeviceID::SHIFTER;

#if DEBUG_ESPNOW

    Serial.println();
    Serial.println("================================");
    Serial.println(" ESP-NOW Initialized");
    Serial.println("================================");

#endif

    return true;
}

//=============================================================================
// Update
//=============================================================================

void ESPNow::update()
{
    uint32_t now = millis();

    //---------------------------------------------------------------------
    // Wheel Timeout
    //---------------------------------------------------------------------

    if (network.wheel.connected)
    {
        if ((now - network.wheel.lastPacketTime) > WHEEL_TIMEOUT_MS)
        {
            network.wheel.connected = false;

#if DEBUG_ESPNOW
            Serial.println("[ESP-NOW] Wheel Timeout");
#endif
        }
    }

    //---------------------------------------------------------------------
    // Pedals Timeout
    //---------------------------------------------------------------------

    if (network.pedals.connected)
    {
        if ((now - network.pedals.lastPacketTime) > PEDAL_TIMEOUT_MS)
        {
            network.pedals.connected = false;

#if DEBUG_ESPNOW
            Serial.println("[ESP-NOW] Pedals Timeout");
#endif
        }
    }

    //---------------------------------------------------------------------
    // Motor-temperature peer timeout
    //---------------------------------------------------------------------

    if (network.motorTemp.connected)
    {
        if ((now - network.motorTemp.lastPacketTime) > MOTOR_TEMP_TIMEOUT_MS)
        {
            network.motorTemp.connected = false;
            motorTempData.valid = 0;

#if DEBUG_ESPNOW
            Serial.println("[ESP-NOW] MotorTemp Timeout");
#endif
        }
    }

    //---------------------------------------------------------------------
    // Sequential-shifter timeout. Explicitly release all HID buttons so a
    // lost radio packet can never leave Shift Up / Down logically held.
    //---------------------------------------------------------------------

    if (network.shifter.connected)
    {
        if ((now - network.shifter.lastPacketTime) > SHIFTER_TIMEOUT_MS)
        {
            network.shifter.connected = false;
            shifterData = {};
            Gamepad::setShifterData(shifterData);

#if DEBUG_ESPNOW
            Serial.println("[ESP-NOW] Shifter Timeout");
#endif
        }
    }

    processTxQueue();
}

//=============================================================================
// Send Dashboard Packet
//=============================================================================

bool ESPNow::sendDashboard(const WheelDashboardPayload& dashboard)
{
    // Keep only the newest 9-byte snapshot. The receiver performs no F1/SimHub
    // decoding and has no LCD broadcast path.
    queuedDashboard = dashboard;
    queuedSequence = txSequence++;

    if (network.wheel.connected)
    {
        wheelTxPending = true;
    }

    processTxQueue();
    return true;
}

//=============================================================================
// Get Latest Wheel Data
//=============================================================================

const WheelPayload& ESPNow::getWheelData()
{
    return wheelData;
}

//=============================================================================
// Get Latest Pedal Data
//=============================================================================

const PedalPayload& ESPNow::getPedalData()
{
    return pedalData;
}

//=============================================================================
// Get Latest Motor Temperature Data
//=============================================================================

const MotorTempPayload& ESPNow::getMotorTempData()
{
    return motorTempData;
}

//=============================================================================
// Get Latest Shifter Data
//=============================================================================

const ShifterPayload& ESPNow::getShifterData()
{
    return shifterData;
}

//=============================================================================
// Connection Status
//=============================================================================

bool ESPNow::wheelConnected()
{
    return network.wheel.connected;
}

//-----------------------------------------------------------------------------

bool ESPNow::pedalsConnected()
{
    return network.pedals.connected;
}

//-----------------------------------------------------------------------------

bool ESPNow::motorTempConnected()
{
    return network.motorTemp.connected;
}

//-----------------------------------------------------------------------------

bool ESPNow::shifterConnected()
{
    return network.shifter.connected;
}

//-----------------------------------------------------------------------------

bool ESPNow::allConnected()
{
    return network.wheel.connected &&
           network.pedals.connected &&
           network.motorTemp.connected;
}

//=============================================================================
// Network State
//=============================================================================

const ReceiverNetworkState& ESPNow::getNetworkState()
{
    return network;
}

//=============================================================================
// Statistics
//=============================================================================

uint32_t ESPNow::wheelPackets()
{
    return wheelPacketsReceived;
}

//-----------------------------------------------------------------------------

uint32_t ESPNow::pedalPackets()
{
    return pedalPacketsReceived;
}

//-----------------------------------------------------------------------------

uint32_t ESPNow::motorTempPackets()
{
    return motorTempPacketsReceived;
}

//-----------------------------------------------------------------------------

uint32_t ESPNow::shifterPackets()
{
    return shifterPacketsReceived;
}

//-----------------------------------------------------------------------------

uint32_t ESPNow::dashboardPackets()
{
    return dashboardPacketsSent;
}

//=============================================================================
// Print Statistics
//=============================================================================

void ESPNow::printStatistics()
{
#if DEBUG_ESPNOW

    Serial.println();
    Serial.println("=================================================");
    Serial.println("            ESP-NOW STATISTICS");
    Serial.println("=================================================");

    Serial.printf("Wheel Connected      : %s\n",
                  network.wheel.connected ? "YES" : "NO");

    Serial.printf("Pedals Connected     : %s\n",
                  network.pedals.connected ? "YES" : "NO");

    Serial.printf("Shifter Connected    : %s\n",
                  network.shifter.connected ? "YES" : "NO");

    Serial.println();

    Serial.printf("Wheel Packets RX     : %lu\n",
                  wheelPacketsReceived);

    Serial.printf("Pedal Packets RX     : %lu\n",
                  pedalPacketsReceived);

    Serial.printf("Shifter Packets RX   : %lu\n",
                  shifterPacketsReceived);

    Serial.printf("Dashboard Packets TX : %lu\n",
                  dashboardPacketsSent);

    Serial.println();

    Serial.printf("Duplicate Packets    : %lu\n",
                  duplicatePackets);

    Serial.printf("Invalid Packets      : %lu\n",
                  invalidPackets);

    Serial.printf("Send Failures        : %lu\n",
                  sendFailures);

    Serial.println();

    Serial.printf("Wheel Sequence       : %u\n",
                  network.wheel.lastSequence);

    Serial.printf("Pedal Sequence       : %u\n",
                  network.pedals.lastSequence);

    Serial.printf("Shifter Sequence     : %u\n",
                  network.shifter.lastSequence);

    Serial.println("=================================================");
    Serial.println();

#endif
}