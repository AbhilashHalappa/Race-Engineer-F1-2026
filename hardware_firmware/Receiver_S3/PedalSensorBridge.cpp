#include "PedalSensorBridge.h"
#include "ESPNowManager.h"
#include <string.h>

namespace {
uint8_t rxFrame[sizeof(PedalSensorFrame)] = {};
size_t rxPos = 0;
portMUX_TYPE responseMux = portMUX_INITIALIZER_UNLOCKED;
PedalSensorFrame queuedResponse{};
volatile bool responsePending = false;

void resetParser() { rxPos = 0; }
}

void PedalSensorBridge::begin() {
    resetParser();
    portENTER_CRITICAL(&responseMux);
    responsePending = false;
    memset(&queuedResponse, 0, sizeof(queuedResponse));
    portEXIT_CRITICAL(&responseMux);
}

void PedalSensorBridge::consumeSerialByte(uint8_t value) {
    if (rxPos == 0) {
        if (value == PEDAL_SENSOR_MAGIC0) rxFrame[rxPos++] = value;
        return;
    }
    if (rxPos == 1) {
        if (value == PEDAL_SENSOR_MAGIC1) rxFrame[rxPos++] = value;
        else if (value == PEDAL_SENSOR_MAGIC0) { rxFrame[0] = value; rxPos = 1; }
        else resetParser();
        return;
    }
    rxFrame[rxPos++] = value;
    if (rxPos < sizeof(PedalSensorFrame)) return;

    PedalSensorFrame frame{};
    memcpy(&frame, rxFrame, sizeof(frame));
    resetParser();
    if (!pedalSensorValidateFrame(frame) || frame.kind != PedalSensorFrameKind::COMMAND)
        return;
    ESPNow::sendPedalSensorFrame(frame);
}

void PedalSensorBridge::onPedalFrame(const PedalSensorFrame& frame) {
    if (!pedalSensorValidateFrame(frame) || frame.kind != PedalSensorFrameKind::STATUS)
        return;
    portENTER_CRITICAL(&responseMux);
    queuedResponse = frame;
    responsePending = true;
    portEXIT_CRITICAL(&responseMux);
}

void PedalSensorBridge::update() {
    PedalSensorFrame frame{};
    bool ready = false;
    portENTER_CRITICAL(&responseMux);
    if (responsePending) {
        frame = queuedResponse;
        responsePending = false;
        ready = true;
    }
    portEXIT_CRITICAL(&responseMux);
    if (ready) {
        Serial.write(reinterpret_cast<const uint8_t*>(&frame), sizeof(frame));
    }
}
