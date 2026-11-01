#include "RpmLedReceiver.h"
#include "Config.h"

namespace
{
portMUX_TYPE stateMux = portMUX_INITIALIZER_UNLOCKED;
volatile uint8_t currentRpm = 0;
volatile bool currentShiftLight = false;
volatile uint32_t lastReceiveMs = 0;
volatile uint16_t lastSequence = 0;
volatile bool haveSequence = false;
}

void RpmLedReceiver::onReceive(const esp_now_recv_info_t* info, const uint8_t* data, int len)
{
    if (info == nullptr || data == nullptr || len != static_cast<int>(sizeof(RpmLedFrame))) return;

    RpmLedFrame frame{};
    memcpy(&frame, data, sizeof(frame));
    if (!rpmLedValidate(frame)) return;

    portENTER_CRITICAL(&stateMux);
    if (!haveSequence || static_cast<int16_t>(frame.sequence - lastSequence) > 0)
    {
        currentRpm = frame.rpmPercent;
        currentShiftLight = frame.shiftLight != 0;
        lastSequence = frame.sequence;
        haveSequence = true;
        lastReceiveMs = millis();
    }
    portEXIT_CRITICAL(&stateMux);
}

void RpmLedReceiver::update()
{
    // No work is required here; the callback only copies a validated snapshot.
}

uint8_t RpmLedReceiver::rpmPercent()
{
    portENTER_CRITICAL(&stateMux);
    const uint8_t value = currentRpm;
    portEXIT_CRITICAL(&stateMux);
    return value;
}

bool RpmLedReceiver::shiftLight()
{
    portENTER_CRITICAL(&stateMux);
    const bool value = currentShiftLight;
    portEXIT_CRITICAL(&stateMux);
    return value;
}

bool RpmLedReceiver::hasFreshData()
{
    portENTER_CRITICAL(&stateMux);
    const uint32_t age = millis() - lastReceiveMs;
    const bool fresh = haveSequence && age <= TELEMETRY_TIMEOUT_MS;
    portEXIT_CRITICAL(&stateMux);
    return fresh;
}
