#include <Adafruit_DPS310.h>
#include <Wire.h>

#define TCAADDR 0x70
#define printDelayTime 1000
#define DIAG_INTERVAL_MS 50   // 20Hz — faster than before

Adafruit_DPS310 dps;
Adafruit_Sensor *dps_temp = nullptr;
Adafruit_Sensor *dps_pressure = nullptr;

bool diagnosticMode   = false;
bool diagInitialized  = false;
unsigned long lastDiagTime = 0;

int diagPorts[8];     // TCA ports where sensors were found
int diagPortCount = 0;

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

// Called once when DIAG command received — finds and configures all sensors
void initDiagnostic() {
  diagPortCount = 0;

  for (int i = 0; i <= 7; i++) {
    tcaselect(i);
    delay(10);
    if (!dps.begin_I2C()) continue;

    // Use 128Hz rate + 1 sample = fastest output, ~128 readings/sec per sensor
    dps.configurePressure(DPS310_128HZ, DPS310_1SAMPLE);
    dps.configureTemperature(DPS310_1HZ, DPS310_1SAMPLE);

    diagPorts[diagPortCount++] = i;

    char buf[40];
    snprintf(buf, sizeof(buf), "Diagnostic: sensor on TCA port %d", i);
    Serial.println(buf);
  }

  Serial.print("Diagnostic ready: ");
  Serial.print(diagPortCount);
  Serial.println(" sensor(s)");

  delay(20); // let sensors settle before first read
  diagInitialized = true;
}

void setup() {
  Serial.begin(115200);
  Wire.begin(); // <--- IMPORTANT!
  Wire.setClock(400000); // 400kHz fast mode — faster I2C
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
      diagInitialized = false; // re-scan sensors every time we start
      Serial.println("Diagnostic mode ON");
    } else if (cmd == "STOP") {
      diagnosticMode = false;
      diagInitialized = false;
      Serial.println("Diagnostic mode OFF");
    }
  }

  // Diagnostic mode
  if (diagnosticMode) {
    if (!diagInitialized) {
      initDiagnostic();
    }

    if (millis() - lastDiagTime >= DIAG_INTERVAL_MS) {
      lastDiagTime = millis();

      Serial.print("Data:,");
      for (int i = 0; i < diagPortCount; i++) {
        tcaselect(diagPorts[i]);

        dps_pressure = dps.getPressureSensor();
        sensors_event_t pressure_event;
        dps_pressure->getEvent(&pressure_event);

        if (i > 0) Serial.print(",");
        Serial.print(pressure_event.pressure, 4); // hPa — GUI multiplies by 100 for Pa
      }
      Serial.println();
    }
    return; // skip normal scanning while in diagnostic mode
  }

  // Normal scanning mode 
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
