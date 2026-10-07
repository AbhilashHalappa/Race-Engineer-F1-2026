#include "Gamepad.h"

#include "Pins.h"
#include "Config.h"
#include "PedalCalibration.h"

USBHIDGamepad gamepad;

namespace
{
    WheelPayload wheel = {};
    PedalPayload pedals = {};
    ShifterPayload shifter = {};

    portMUX_TYPE inputMux = portMUX_INITIALIZER_UNLOCKED;

    struct HidReportState
    {
        int8_t x;
        int8_t y;
        int8_t z;
        int8_t rz;
        int8_t rx;
        int8_t ry;
        uint8_t hat;
        uint32_t buttons;
    };

    HidReportState lastReport = {};
    bool haveLastReport = false;
    uint32_t lastReportTime = 0;

    int8_t mapAxis(uint16_t raw)
    {
        return constrain(map(raw, 0, 4095, -127, 127), -127, 127);
    }

    bool reportsEqual(const HidReportState& a,
                      const HidReportState& b)
    {
        return a.x == b.x &&
               a.y == b.y &&
               a.z == b.z &&
               a.rz == b.rz &&
               a.rx == b.rx &&
               a.ry == b.ry &&
               a.hat == b.hat &&
               a.buttons == b.buttons;
    }
}

void Gamepad::begin()
{
    // Register HID before starting the native USB peripheral so CDC + HID
    // enumerate through the single USB-C connector.
    // Steering is handled by a separate standalone device (not this hub).
    gamepad.begin();
    USB.begin();
}

void Gamepad::setWheelData(const WheelPayload& data)
{
    portENTER_CRITICAL(&inputMux);
    wheel = data;
    portEXIT_CRITICAL(&inputMux);
}

void Gamepad::setPedalData(const PedalPayload& data)
{
    portENTER_CRITICAL(&inputMux);
    pedals = data;
    portEXIT_CRITICAL(&inputMux);
}

void Gamepad::setShifterData(const ShifterPayload& data)
{
    portENTER_CRITICAL(&inputMux);
    shifter = data;
    portEXIT_CRITICAL(&inputMux);
}

void Gamepad::update()
{
    const uint32_t now = millis();

    if ((now - lastReportTime) < HID_REPORT_INTERVAL_MS)
    {
        return;
    }

    WheelPayload wheelSnapshot;
    PedalPayload pedalSnapshot;
    ShifterPayload shifterSnapshot;

    portENTER_CRITICAL(&inputMux);
    wheelSnapshot = wheel;
    pedalSnapshot = pedals;
    shifterSnapshot = shifter;
    portEXIT_CRITICAL(&inputMux);

    //--------------------------------------------------
    // Build one complete HID report
    //--------------------------------------------------
    // Wheel inputs use bits 0..27 and are intentionally shifted to USB
    // buttons 2..29. The three remaining high HID slots are reserved for the
    // wireless sequential shifter: USB buttons 30, 31 and 32.
    // X/Y are otherwise unused here — steering comes from a standalone device.

    uint32_t usbButtons = wheelSnapshot.buttonState << 1;
    usbButtons |=
        (static_cast<uint32_t>(shifterSnapshot.buttonState & 0x07u) << 29);

    HidReportState report = {};

    // Foot clutch uses X when enabled. Analog handbrake uses the previously
    // unused Y axis when enabled in Receiver settings.
    report.x       = PedalCalibration::clutchEnabled()
                       ? mapAxis(PedalCalibration::applyClutch(pedalSnapshot.clutch))
                       : 0;
    report.y       = PedalCalibration::handbrakeEnabled()
                       ? mapAxis(PedalCalibration::applyHandbrake(shifterSnapshot.handbrake))
                       : 0;
    report.z       = mapAxis(PedalCalibration::applyThrottle(pedalSnapshot.throttle));
    report.rz      = mapAxis(PedalCalibration::applyBrake(pedalSnapshot.brake));
    report.rx      = mapAxis(wheelSnapshot.clutchLeft);
    report.ry      = mapAxis(wheelSnapshot.clutchRight);
    report.hat     = 0;
    report.buttons = usbButtons;

    const bool changed =
        !haveLastReport || !reportsEqual(report, lastReport);

    const bool keepAliveDue =
        !haveLastReport || (now - lastReportTime) >= HID_KEEPALIVE_MS;

    if (!changed && !keepAliveDue)
    {
        return;
    }

    // USBHIDGamepad::send() updates all buttons and axes and produces only
    // one USB report.
    const bool sent = gamepad.send(
        report.x,
        report.y,
        report.z,
        report.rz,
        report.rx,
        report.ry,
        report.hat,
        report.buttons
    );

    if (sent)
    {
        lastReport = report;
        haveLastReport = true;
        lastReportTime = now;
    }
}
