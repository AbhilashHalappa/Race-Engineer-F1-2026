
#include "Config.h"
#include "OTAManager.h"
#include "Version.h"

#if ENABLE_OTA

#include <WiFi.h>
#include <WebServer.h>
#include <Update.h>

namespace
{
    WebServer server(OTA_HTTP_PORT);

    uint32_t otaStartTime = 0;

    bool otaActive = false;
    bool otaUpdateStarted = false;
    bool otaUpdateFinished = false;
    bool otaRestartPending = false;

    uint32_t uploadedBytes = 0;

    void sendUnavailable()
    {
        server.send(
            403,
            "text/html",
            "<html><body><h2>OTA unavailable</h2>"
            "<p>The update window has closed.</p>"
            "<p>Reboot the wheel to enable OTA again.</p>"
            "</body></html>"
        );
    }

    String otaPage()
    {
        const uint32_t elapsed = millis() - otaStartTime;
        const uint32_t remaining =
            elapsed < OTA_WINDOW_MS ? OTA_WINDOW_MS - elapsed : 0;

        String html;
        html.reserve(1600);

        html += "<!DOCTYPE html><html><head>";
        html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
        html += "<title>GamePad Pro Wheel OTA</title>";
        html += "<style>body{font-family:Arial;margin:25px;max-width:650px}"
                ".box{padding:20px;border:1px solid #ccc;border-radius:10px}"
                "input,button{font-size:18px;margin-top:12px}</style>";
        html += "</head><body><div class='box'>";

        html += "<h2>GamePad Pro Wheel Dashboard</h2>";
        html += "<p><b>Firmware:</b> ";
        html += FW_STRING;
        html += "</p>";

        html += "<p><b>ESP-NOW channel:</b> ";
        html += String(ESPNOW_CHANNEL);
        html += "</p>";

        if (remaining > 0)
        {
            html += "<p>Initial window: ";
            html += String((remaining + 999) / 1000);
            html += " seconds remaining.</p>";
        }
        else
        {
            html += "<p>Connected client: OTA remains available.</p>";
        }

        html += "<form method='POST' action='/update' "
                "enctype='multipart/form-data'>";
        html += "<input type='file' name='firmware' accept='.bin' required><br>";
        html += "<button type='submit'>Upload Firmware</button>";
        html += "</form>";

        html += "<hr><p>Select the compiled wheel firmware .bin file.</p>";
        html += "<p>Do not disconnect power during the update.</p>";
        html += "</div></body></html>";

        return html;
    }

    void handleRoot()
    {
        if (!otaActive)
        {
            sendUnavailable();
            return;
        }

        server.send(200, "text/html", otaPage());
    }

    void handleUpdate()
    {
        if (!otaActive)
        {
            sendUnavailable();
            return;
        }

        if (!otaUpdateFinished)
        {
            server.send(
                400,
                "text/plain",
                "Firmware upload failed or did not complete."
            );
            return;
        }

        server.send(
            200,
            "text/html",
            "<html><body><h2>Firmware update successful</h2>"
            "<p>The wheel will reboot now.</p></body></html>"
        );

        otaRestartPending = true;
    }

    void handleUpload()
    {
        if (!otaActive)
            return;

        HTTPUpload& upload = server.upload();

        switch (upload.status)
        {
            case UPLOAD_FILE_START:
            {
                otaUpdateStarted = false;
                otaUpdateFinished = false;
                uploadedBytes = 0;

                if (upload.filename.length() == 0 ||
                    (!upload.filename.endsWith(".bin") &&
                     !upload.filename.endsWith(".BIN")))
                {
                    Serial.println("[OTA] Rejected filename");
                    return;
                }

                if (!Update.begin(UPDATE_SIZE_UNKNOWN, U_FLASH))
                {
                    Serial.printf(
                        "[OTA] Update.begin failed: %s\n",
                        Update.errorString()
                    );
                    return;
                }

                otaUpdateStarted = true;

                Serial.printf(
                    "[OTA] Upload started: %s\n",
                    upload.filename.c_str()
                );
                break;
            }

            case UPLOAD_FILE_WRITE:
            {
                if (!otaUpdateStarted)
                    return;

                const size_t written =
                    Update.write(upload.buf, upload.currentSize);

                if (written != upload.currentSize)
                {
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
                if (!otaUpdateStarted)
                    return;

                if (Update.end(true))
                {
                    otaUpdateFinished = true;

                    Serial.printf(
                        "[OTA] Upload complete: %lu bytes\n",
                        static_cast<unsigned long>(uploadedBytes)
                    );
                }
                else
                {
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

                if (otaUpdateStarted)
                    Update.abort();

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
        if (!otaActive)
            return;

        server.stop();
        WiFi.softAPdisconnect(true);

        otaActive = false;

        Serial.println("[OTA] OTA access point closed");
    }
}

bool OTA::begin()
{
    otaStartTime = millis();

    otaActive = false;
    otaUpdateStarted = false;
    otaUpdateFinished = false;
    otaRestartPending = false;
    uploadedBytes = 0;

    // Keep the existing ESP-NOW radio active while enabling the AP.
    WiFi.mode(WIFI_AP_STA);
    WiFi.setSleep(false);
    delay(100);

    if (!WiFi.softAP(
            OTA_AP_SSID,
            OTA_AP_PASSWORD,
            ESPNOW_CHANNEL,
            false,
            1))
    {
        Serial.println("[OTA] Failed to start access point");
        return false;
    }

    server.on("/", HTTP_GET, handleRoot);
    server.on("/update", HTTP_POST, handleUpdate, handleUpload);
    server.begin();

    otaActive = true;

    Serial.printf("[OTA] SSID: %s\n", OTA_AP_SSID);
    Serial.printf("[OTA] IP: %s\n", WiFi.softAPIP().toString().c_str());
    Serial.printf("[OTA] Channel: %u\n", ESPNOW_CHANNEL);
    Serial.printf(
        "[OTA] Initial window: %lu seconds\n",
        static_cast<unsigned long>(OTA_WINDOW_MS / 1000)
    );

    return true;
}

void OTA::update()
{
    if (!otaActive)
        return;

    server.handleClient();

    if (otaRestartPending)
    {
        otaRestartPending = false;
        delay(500);
        ESP.restart();
        return;
    }

    const bool expired =
        (millis() - otaStartTime) >= OTA_WINDOW_MS;

    const bool clientConnected =
        WiFi.softAPgetStationNum() > 0;

    // Never close the AP while a firmware upload is in progress.
    if (expired &&
        !clientConnected &&
        !otaUpdateStarted)
    {
        stopOTA();
    }
}

bool OTA::active()
{
    return otaActive;
}

uint32_t OTA::remainingMs()
{
    if (!otaActive)
        return 0;

    const uint32_t elapsed = millis() - otaStartTime;

    if (elapsed >= OTA_WINDOW_MS)
        return 0;

    return OTA_WINDOW_MS - elapsed;
}

#endif
