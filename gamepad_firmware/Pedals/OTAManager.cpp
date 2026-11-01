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

void sendNoLongerAvailable()
{
    server.send(
        403,
        "text/html",
        "<html><body>"
        "<h2>OTA window closed</h2>"
        "<p>The OTA window has expired.</p>"
        "<p>Reboot the pedals module to enable OTA again.</p>"
        "</body></html>"
    );
}

String otaPage()
{
    uint32_t elapsed = millis() - otaStartTime;
    uint32_t remaining = 0;

    if (elapsed < OTA_WINDOW_MS) {
        remaining = OTA_WINDOW_MS - elapsed;
    }

    String html;
    html.reserve(2200);

    html += "<!DOCTYPE html><html><head>";
    html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
    html += "<title>GamePad Pro Pedals OTA</title>";
    html += "<style>";
    html += "body{font-family:Arial,sans-serif;margin:30px;max-width:650px;}";
    html += "input,button{font-size:18px;margin-top:12px;}";
    html += ".box{padding:20px;border:1px solid #ccc;border-radius:10px;}";
    html += "</style></head><body><div class='box'>";

    html += "<h2>GamePad Pro Pedals</h2>";
    html += "<p><b>Firmware:</b> ";
    html += FW_STRING;
    html += "</p>";

    html += "<p><b>ESP-NOW channel:</b> ";
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
    html += "<button type='submit'>Upload Firmware</button>";
    html += "</form>";

    html += "<hr><p>Upload a firmware .bin file compiled for this ESP32 board.</p>";
    html += "<p>Do not disconnect power during the update.</p>";
    html += "</div></body></html>";

    return html;
}

void handleRoot()
{
    if (!otaActive) {
        sendNoLongerAvailable();
        return;
    }

    server.send(200, "text/html", otaPage());
}

void handleUpdate()
{
    if (!otaActive) {
        sendNoLongerAvailable();
        return;
    }

    if (!otaUpdateFinished) {
        server.send(
            400,
            "text/plain",
            "Firmware upload did not complete successfully."
        );
        return;
    }

    server.send(
        200,
        "text/html",
        "<html><body><h2>Firmware update successful</h2>"
        "<p>The pedals module will reboot now.</p></body></html>"
    );

    otaRestartPending = true;
}

void handleUpload()
{
    if (!otaActive) {
        return;
    }

    HTTPUpload& upload = server.upload();

    switch (upload.status) {

        case UPLOAD_FILE_START:
        {
            otaUpdateStarted = false;
            otaUpdateFinished = false;
            uploadedBytes = 0;

            if (upload.filename.length() == 0 ||
                (!upload.filename.endsWith(".bin") &&
                 !upload.filename.endsWith(".BIN"))) {
                Serial.println("[OTA] Rejected filename");
                return;
            }

            Serial.printf(
                "[OTA] Upload started: %s\n",
                upload.filename.c_str()
            );

            if (!Update.begin(UPDATE_SIZE_UNKNOWN, U_FLASH)) {
                Serial.printf(
                    "[OTA] Update.begin failed: %s\n",
                    Update.errorString()
                );
                return;
            }

            otaUpdateStarted = true;
            break;
        }

        case UPLOAD_FILE_WRITE:
        {
            if (!otaUpdateStarted) {
                return;
            }

            size_t written = Update.write(
                upload.buf,
                upload.currentSize
            );

            if (written != upload.currentSize) {
                Serial.printf(
                    "[OTA] Write failed: %s\n",
                    Update.errorString()
                );

                Update.abort();
                otaUpdateStarted = false;
                return;
            }

            uploadedBytes += written;
            break;
        }

        case UPLOAD_FILE_END:
        {
            if (!otaUpdateStarted) {
                return;
            }

            if (Update.end(true)) {
                otaUpdateFinished = true;

                Serial.printf(
                    "[OTA] Upload complete: %lu bytes\n",
                    static_cast<unsigned long>(uploadedBytes)
                );
            } else {
                otaUpdateFinished = false;

                Serial.printf(
                    "[OTA] Update.end failed: %s\n",
                    Update.errorString()
                );
            }

            otaUpdateStarted = false;
            break;
        }

        case UPLOAD_FILE_ABORTED:
        {
            Serial.println("[OTA] Upload aborted");

            if (otaUpdateStarted) {
                Update.abort();
            }

            otaUpdateStarted = false;
            otaUpdateFinished = false;
            uploadedBytes = 0;
            break;
        }

        default:
            break;
    }
}

void stopOTA()
{
    if (!otaActive) {
        return;
    }

    // Stop accepting HTTP requests and disconnect the temporary AP.
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

    // ESP-NOW and the OTA access point share channel 1.
    WiFi.mode(WIFI_AP_STA);
    WiFi.setSleep(false);
    delay(100);

    if (!WiFi.softAP(
            OTA_AP_SSID,
            OTA_AP_PASSWORD,
            ESPNOW_CHANNEL,
            false,
            1)) {

        Serial.println("[OTA] Failed to start SoftAP");
        return false;
    }

    server.on("/", HTTP_GET, handleRoot);

    server.on(
        "/update",
        HTTP_POST,
        handleUpdate,
        handleUpload
    );

    server.begin();
    otaActive = true;

    Serial.println();
    Serial.println("==========================================");
    Serial.println("             OTA UPDATE MODE");
    Serial.println("==========================================");

    Serial.printf("SSID       : %s\n", OTA_AP_SSID);
    Serial.printf("Password   : %s\n", OTA_AP_PASSWORD);
    Serial.printf("IP Address : %s\n", WiFi.softAPIP().toString().c_str());
    Serial.printf("Channel    : %u\n", ESPNOW_CHANNEL);
    Serial.printf("Window     : %lu seconds\n",
                  static_cast<unsigned long>(OTA_WINDOW_MS / 1000));

    Serial.println("Open http://192.168.4.1/");
    Serial.println("==========================================");
    Serial.println();

    return true;
}


void OTA::update()
{
    if (!otaActive) {
        return;
    }

    // Process HTTP requests and upload data.
    server.handleClient();

    if (otaRestartPending) {
        otaRestartPending = false;

        Serial.println("[OTA] Rebooting into new firmware...");
        delay(500);
        ESP.restart();
        return;
    }

    const uint32_t elapsed = millis() - otaStartTime;
    const bool initialWindowExpired = elapsed >= OTA_WINDOW_MS;
    const bool pcConnected = WiFi.softAPgetStationNum() > 0;
    const bool uploadInProgress = otaUpdateStarted;

    // Before 60 seconds, the OTA AP is available to connect.
    // After 60 seconds, retain it if a PC is connected or an
    // upload is in progress. Otherwise, close the OTA AP.
    if (initialWindowExpired &&
        !pcConnected &&
        !uploadInProgress) {

        stopOTA();
    }
}


bool OTA::active()
{
    return otaActive;
}


uint32_t OTA::remainingMs()
{
    if (!otaActive) {
        return 0;
    }

    const uint32_t elapsed = millis() - otaStartTime;

    if (elapsed >= OTA_WINDOW_MS) {
        return 0;
    }

    return OTA_WINDOW_MS - elapsed;
}

#endif
