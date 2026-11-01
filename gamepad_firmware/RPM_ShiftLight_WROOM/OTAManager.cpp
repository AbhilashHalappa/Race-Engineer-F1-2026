#include "Config.h"
#include "OTAManager.h"
#include "Version.h"

#if ENABLE_OTA

#include <WiFi.h>
#include <WebServer.h>
#include <Update.h>

namespace {
WebServer server(OTA_HTTP_PORT);
uint32_t otaStartTime = 0;
bool otaActive = false;
bool otaUpdateStarted = false;
bool otaUpdateFinished = false;
bool otaRestartPending = false;
uint32_t uploadedBytes = 0;

void sendUnavailable()
{
    server.send(403, "text/html",
        "<html><body><h2>OTA window closed</h2>"
        "<p>The OTA window has expired. Reboot the RPM LED controller to enable OTA again.</p>"
        "</body></html>");
}

String otaPage()
{
    const uint32_t elapsed = millis() - otaStartTime;
    const uint32_t remaining = elapsed < OTA_WINDOW_MS ? OTA_WINDOW_MS - elapsed : 0;
    String html;
    html.reserve(1800);
    html += "<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>";
    html += "<title>RPM Shift Light OTA</title><style>body{font-family:Arial;margin:30px;max-width:650px}";
    html += ".box{padding:20px;border:1px solid #ccc;border-radius:10px}input,button{font-size:18px;margin-top:12px}</style></head><body><div class='box'>";
    html += "<h2>ESP32-WROOM RPM Shift Light</h2><p><b>Firmware:</b> ";
    html += FW_STRING;
    html += "</p><p><b>ESP-NOW channel:</b> ";
    html += String(ESPNOW_CHANNEL);
    html += "</p>";
    if (elapsed < OTA_WINDOW_MS) {
        html += "<p>Initial OTA window: ";
        html += String((remaining + 999) / 1000);
        html += " seconds remaining.</p>";
    } else {
        html += "<p>PC connected: OTA remains available.</p>";
    }
    html += "<form method='POST' action='/update' enctype='multipart/form-data'>";
    html += "<input type='file' name='firmware' accept='.bin' required><br>";
    html += "<button type='submit'>Upload Firmware</button></form><hr>";
    html += "<p>Upload an ESP32-WROOM firmware .bin file. Do not disconnect power during update.</p>";
    html += "</div></body></html>";
    return html;
}

void handleRoot()
{
    if (!otaActive) { sendUnavailable(); return; }
    server.send(200, "text/html", otaPage());
}

void handleUpdate()
{
    if (!otaActive) { sendUnavailable(); return; }
    if (!otaUpdateFinished) {
        server.send(400, "text/plain", "Firmware upload did not complete successfully.");
        return;
    }
    server.send(200, "text/html",
        "<html><body><h2>Firmware update successful</h2>"
        "<p>The RPM LED controller will reboot now.</p></body></html>");
    otaRestartPending = true;
}

void handleUpload()
{
    if (!otaActive) return;
    HTTPUpload& upload = server.upload();
    switch (upload.status) {
        case UPLOAD_FILE_START:
            otaUpdateStarted = false;
            otaUpdateFinished = false;
            uploadedBytes = 0;
            if (upload.filename.length() == 0 ||
                (!upload.filename.endsWith(".bin") && !upload.filename.endsWith(".BIN"))) {
                Serial.println("[OTA] Rejected filename");
                return;
            }
            Serial.printf("[OTA] Upload started: %s\n", upload.filename.c_str());
            if (!Update.begin(UPDATE_SIZE_UNKNOWN, U_FLASH)) {
                Serial.printf("[OTA] Update.begin failed: %s\n", Update.errorString());
                return;
            }
            otaUpdateStarted = true;
            break;

        case UPLOAD_FILE_WRITE:
            if (!otaUpdateStarted) return;
            {
                const size_t written = Update.write(upload.buf, upload.currentSize);
                if (written != upload.currentSize) {
                    Serial.printf("[OTA] Write failed: %s\n", Update.errorString());
                    Update.abort();
                    otaUpdateStarted = false;
                    return;
                }
                uploadedBytes += written;
            }
            break;

        case UPLOAD_FILE_END:
            if (!otaUpdateStarted) return;
            if (Update.end(true)) {
                otaUpdateFinished = true;
                Serial.printf("[OTA] Upload complete: %lu bytes\n",
                              static_cast<unsigned long>(uploadedBytes));
            } else {
                otaUpdateFinished = false;
                Serial.printf("[OTA] Update.end failed: %s\n", Update.errorString());
            }
            otaUpdateStarted = false;
            break;

        case UPLOAD_FILE_ABORTED:
            Serial.println("[OTA] Upload aborted");
            if (otaUpdateStarted) Update.abort();
            otaUpdateStarted = false;
            otaUpdateFinished = false;
            uploadedBytes = 0;
            break;

        default:
            break;
    }
}

void stopOTA()
{
    if (!otaActive) return;
    server.stop();
    WiFi.softAPdisconnect(true);
    otaActive = false;
    Serial.println("[OTA] OTA window closed");
}
} // namespace

bool OTA::begin()
{
    otaStartTime = millis();
    otaActive = false;
    otaUpdateStarted = false;
    otaUpdateFinished = false;
    otaRestartPending = false;
    uploadedBytes = 0;

    // Match the pedal OTA behaviour: AP and ESP-NOW share the fixed channel.
    WiFi.mode(WIFI_AP_STA);
    WiFi.setSleep(false);
    delay(100);

    if (!WiFi.softAP(OTA_AP_SSID, OTA_AP_PASSWORD, ESPNOW_CHANNEL, false, 1)) {
        Serial.println("[OTA] Failed to start SoftAP");
        return false;
    }

    server.on("/", HTTP_GET, handleRoot);
    server.on("/update", HTTP_POST, handleUpdate, handleUpload);
    server.begin();
    otaActive = true;

    Serial.println();
    Serial.println("==========================================");
    Serial.println("           RPM LED OTA UPDATE MODE");
    Serial.println("==========================================");
    Serial.printf("SSID       : %s\n", OTA_AP_SSID);
    Serial.printf("Password   : %s\n", OTA_AP_PASSWORD);
    Serial.printf("IP Address : %s\n", WiFi.softAPIP().toString().c_str());
    Serial.printf("Channel    : %u\n", ESPNOW_CHANNEL);
    Serial.printf("Window     : %lu seconds\n",
                  static_cast<unsigned long>(OTA_WINDOW_MS / 1000));
    Serial.println("Open http://192.168.4.1/");
    Serial.println("==========================================");
    return true;
}

void OTA::update()
{
    if (!otaActive) return;
    server.handleClient();

    if (otaRestartPending) {
        otaRestartPending = false;
        Serial.println("[OTA] Rebooting into new firmware...");
        delay(500);
        ESP.restart();
        return;
    }

    const bool initialWindowExpired = (millis() - otaStartTime) >= OTA_WINDOW_MS;
    const bool pcConnected = WiFi.softAPgetStationNum() > 0;
    if (initialWindowExpired && !pcConnected && !otaUpdateStarted) stopOTA();
}

bool OTA::active() { return otaActive; }

uint32_t OTA::remainingMs()
{
    if (!otaActive) return 0;
    const uint32_t elapsed = millis() - otaStartTime;
    return elapsed >= OTA_WINDOW_MS ? 0 : OTA_WINDOW_MS - elapsed;
}

#endif
