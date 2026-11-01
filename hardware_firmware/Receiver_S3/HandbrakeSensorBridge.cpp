#include "HandbrakeSensorBridge.h"
#include "ESPNowManager.h"
#include <string.h>

namespace {
uint8_t rxFrame[sizeof(HandbrakeSensorFrame)] = {};
size_t rxPos = 0;
portMUX_TYPE responseMux = portMUX_INITIALIZER_UNLOCKED;
HandbrakeSensorFrame queuedResponse{};
volatile bool responsePending = false;
void resetParser() { rxPos = 0; }
}

void HandbrakeSensorBridge::begin() {
    resetParser();
    portENTER_CRITICAL(&responseMux);
    responsePending = false;
    memset(&queuedResponse, 0, sizeof(queuedResponse));
    portEXIT_CRITICAL(&responseMux);
}

void HandbrakeSensorBridge::consumeSerialByte(uint8_t value) {
    if (rxPos == 0) {
        if (value == HANDBRAKE_SENSOR_MAGIC0) rxFrame[rxPos++] = value;
        return;
    }
    if (rxPos == 1) {
        if (value == HANDBRAKE_SENSOR_MAGIC1) rxFrame[rxPos++] = value;
        else if (value == HANDBRAKE_SENSOR_MAGIC0) { rxFrame[0] = value; rxPos = 1; }
        else resetParser();
        return;
    }
    rxFrame[rxPos++] = value;
    if (rxPos < sizeof(HandbrakeSensorFrame)) return;

    HandbrakeSensorFrame frame{};
    memcpy(&frame, rxFrame, sizeof(frame));
    resetParser();
    if (!handbrakeSensorValidateFrame(frame) || frame.kind != HandbrakeSensorFrameKind::COMMAND)
        return;
    ESPNow::sendHandbrakeSensorFrame(frame);
}

void HandbrakeSensorBridge::onHandbrakeFrame(const HandbrakeSensorFrame& frame) {
    if (!handbrakeSensorValidateFrame(frame) || frame.kind != HandbrakeSensorFrameKind::STATUS)
        return;
    portENTER_CRITICAL(&responseMux);
    queuedResponse = frame;
    responsePending = true;
    portEXIT_CRITICAL(&responseMux);
}

void HandbrakeSensorBridge::update() {
    HandbrakeSensorFrame frame{};
    bool ready = false;
    portENTER_CRITICAL(&responseMux);
    if (responsePending) {
        frame = queuedResponse;
        responsePending = false;
        ready = true;
    }
    portEXIT_CRITICAL(&responseMux);
    if (ready) Serial.write(reinterpret_cast<const uint8_t*>(&frame), sizeof(frame));
}
