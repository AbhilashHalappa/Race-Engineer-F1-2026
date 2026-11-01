#pragma once

#include <Arduino.h>

namespace OTA {

bool begin();
void update();
bool active();
uint32_t remainingMs();

}