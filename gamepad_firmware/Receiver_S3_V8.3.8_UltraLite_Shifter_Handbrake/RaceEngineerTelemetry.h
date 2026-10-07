/*****************************************************************************/
/* GamePad Pro V8.3.3 - Race Engineer compact telemetry receiver             */
/*                                                                           */
/* The proven 15-byte PC -> Receiver telemetry protocol remains unchanged.    */
/* A tiny independent control frame lets Wheel Companion opt in to extended   */
/* Receiver -> PC live values without changing legacy Race Engineer traffic.  */
/*****************************************************************************/
#pragma once

#include <Arduino.h>
#include "Protocol.h"

namespace RaceEngineerTelemetry
{
    void begin();
    void update();
    const WheelDashboardPayload& getDashboard();
    bool hasData();
    uint32_t packetsReceived();
    uint32_t invalidPackets();

    // Milliseconds since the last valid PC telemetry frame; UINT32_MAX before first RX.
    uint32_t lastPacketAgeMs();

    // Wheel Companion extended-status opt-in. The Receiver defaults to legacy
    // output only. A valid Wheel Companion enable command keeps this true for
    // a short lease; disable or timeout returns immediately to legacy-only.
    bool extendedStatusEnabled();
    uint32_t extendedStatusLeaseRemainingMs();
    // 0=disabled, 1=legacy WL/V1, 2=+clutch, 3=+handbrake.
    uint8_t extendedStatusVersion();
}
