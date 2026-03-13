#include <Adafruit_DPS310.h>
#include <Wire.h>

#define TCAADDR 0x70
#define printDelayTime 1000
#define DIAG_INTERVAL_MS 100

Adafruit_DPS310 dps;
Adafruit_Sensor *dps_temp = nullptr;
Adafruit_Sensor *dps_pressure = nullptr;

bool diagnosticMode = false;
unsigned long lastDiagTime = 0;

void tcaselect(uint8_t i) {
  if (i > 7) return;
  Wire.beginTransmission(TCAADDR);
  Wire.write(1 << i);
  Wire.endTransmission();
}

void bufferlessPrint(const char* str) {
  while (!Serial);
  Serial.println(str);
  Serial.flush();
}

void setup() {
  Serial.begin(115200);
  Wire.begin(); // <--- IMPORTANT!
  Wire.setClock(100000); // Optional: slow down I2C if needed
  bufferlessPrint("Start of setup");
  delay(printDelayTime);
}

void loop() {
  // Check for incoming serial commands
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "DIAG") {
      diagnosticMode = true;
      Serial.println("Diagnostic mode ON");
    } else if (cmd == "STOP") {
      diagnosticMode = false;
      Serial.println("Diagnostic mode OFF");
    }
  }

  // Diagnostic mode
  if (diagnosticMode) {
    if (millis() - lastDiagTime >= DIAG_INTERVAL_MS) {
      lastDiagTime = millis();

      float readings[2] = {-1.0, -1.0};
      int found = 0;

      for (int i = 0; i <= 7 && found < 2; i++) {
        tcaselect(i);
        delay(10);
        if (!dps.begin_I2C()) continue;

        dps.configurePressure(DPS310_64HZ, DPS310_64SAMPLES);
        dps_pressure = dps.getPressureSensor();

        unsigned long start = millis();
        while (!dps.pressureAvailable()) {
          if (millis() - start > 200) break;
        }
        if (!dps.pressureAvailable()) continue;

        sensors_event_t pressure_event;
        dps_pressure->getEvent(&pressure_event);
        readings[found++] = pressure_event.pressure; // hPa — GUI multiplies by 100 to get Pa
      }

      Serial.print("Data:,");
      Serial.print(readings[0], 4);
      Serial.print(",");
      Serial.println(readings[1], 4);
    }
    return; // skip normal scanning while in diagnostic mode
  }

  bufferlessPrint("Start of loop");
  delay(printDelayTime);

  for (int i = 0; i <= 7; i++) {
    char buf[32];
    snprintf(buf, sizeof(buf), "TCA Port # %d", i);
    bufferlessPrint(buf);

    tcaselect(i);
    delay(100);

    if (!dps.begin_I2C()) {
      Serial.println("Failed to find DPS");
      continue;
    }

    Serial.println("DPS OK!");

    dps_temp = dps.getTemperatureSensor();
    dps_pressure = dps.getPressureSensor();

    dps.configurePressure(DPS310_64HZ, DPS310_64SAMPLES);
    dps.configureTemperature(DPS310_64HZ, DPS310_64SAMPLES);

    sensors_event_t temp_event, pressure_event;

    if (dps.temperatureAvailable()) {
      dps_temp->getEvent(&temp_event);
      Serial.print("Temperature = ");
      Serial.print(temp_event.temperature);
      Serial.println(" *C");
      delay(500);
    }

    if (dps.pressureAvailable()) {
      dps_pressure->getEvent(&pressure_event);
      Serial.print("Pressure = ");
      Serial.print(pressure_event.pressure);
      Serial.println(" hPa");
    }

    Serial.println();
    delay(1000);
  }
}
