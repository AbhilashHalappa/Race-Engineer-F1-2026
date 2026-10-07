/******************************************************************************
 * GamePad Pro V8 — Shared network peer helpers
 ******************************************************************************/

#pragma once

#include <Arduino.h>
#include "Protocol.h"

struct PeerInfo
{
    DeviceID device = DeviceID::RECEIVER;
    bool connected = false;
    uint16_t lastSequence = 0xFFFF;
    uint32_t lastPacketTime = 0;
    int8_t rssi = 0;
};

struct ReceiverNetworkState
{
    PeerInfo wheel{DeviceID::WHEEL};
    PeerInfo pedals{DeviceID::PEDALS};
    PeerInfo motorTemp{DeviceID::MOTOR_TEMP};
};

inline bool isConnected(const PeerInfo& peer, uint32_t timeout)
{
    return peer.connected &&
           (millis() - peer.lastPacketTime) < timeout;
}

inline void resetPeer(PeerInfo& peer)
{
    peer.connected = false;
    peer.lastSequence = 0xFFFF;
    peer.lastPacketTime = 0;
    peer.rssi = 0;
}
