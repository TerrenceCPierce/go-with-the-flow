#include <Adafruit_DPS310.h>
#include <Wire.h>

#define TCAADDR 0x70
#define MAX_PORTS 8
#define DIAG_INTERVAL_MS 50  // 20 Hz diagnostic streaming

// ── Sensor arrays (one DPS310 object per TCA port) ──
Adafruit_DPS310   dpsArray[MAX_PORTS];
Adafruit_Sensor*  dpsPressureArray[MAX_PORTS];

int  validPorts[MAX_PORTS];
int  numValidPorts = 0;
bool sensorsInitialized = false;

// ── Mode tracking ──
enum Mode { IDLE, EXPERIMENT, DIAGNOSTIC };
Mode currentMode = IDLE;

bool guiConnected   = false;
unsigned long lastDiagTime = 0;

// ── I2C helpers ──
void tcaselect(uint8_t i) {
  if (i > 7) return;
  Wire.beginTransmission(TCAADDR);
  Wire.write(1 << i);
  Wire.endTransmission();
}

// ── Scan and initialize all sensors (called once) ──
void initSensors() {
  numValidPorts = 0;

  for (int i = 0; i < MAX_PORTS; i++) {
    tcaselect(i);
    delay(50);

    if (dpsArray[i].begin_I2C()) {
      validPorts[numValidPorts++] = i;
      dpsPressureArray[i] = dpsArray[i].getPressureSensor();

      dpsArray[i].configurePressure(DPS310_64HZ, DPS310_64SAMPLES);
      dpsArray[i].configureTemperature(DPS310_64HZ, DPS310_64SAMPLES);

      Serial.print("Sensor found on TCA port ");
      Serial.println(i);
    }
  }

  Serial.print("Total sensors: ");
  Serial.println(numValidPorts);
  sensorsInitialized = true;
}

// ── Reconfigure sensors for fast diagnostic streaming ──
void configDiagnostic() {
  for (int j = 0; j < numValidPorts; j++) {
    int port = validPorts[j];
    tcaselect(port);
    dpsArray[port].configurePressure(DPS310_128HZ, DPS310_1SAMPLE);
    dpsArray[port].configureTemperature(DPS310_1HZ, DPS310_1SAMPLE);
  }
  delay(20);
}

// ── Reconfigure sensors for slower, averaged experiment readings ──
void configExperiment() {
  for (int j = 0; j < numValidPorts; j++) {
    int port = validPorts[j];
    tcaselect(port);
    dpsArray[port].configurePressure(DPS310_64HZ, DPS310_64SAMPLES);
    dpsArray[port].configureTemperature(DPS310_64HZ, DPS310_64SAMPLES);
  }
  delay(20);
}

// ── Read one pressure sample from each sensor, send as "Data:,p1,p2,..." ──
void sendDataLine() {
  Serial.print("Data:,");
  for (int j = 0; j < numValidPorts; j++) {
    int port = validPorts[j];
    tcaselect(port);
    delay(20);

    sensors_event_t ev;
    dpsPressureArray[port]->getEvent(&ev);

    if (j > 0) Serial.print(",");
    Serial.print(ev.pressure, 4);
  }
  Serial.println();
}

// ── Process serial commands (non-blocking) ──
void processCommand(String cmd) {
  cmd.trim();

  if (cmd == "GReady") {
    guiConnected = true;
    currentMode = EXPERIMENT;
    configExperiment();
    Serial.println("Arduino Ready 1");

  } else if (cmd == "a") {
    if (currentMode != EXPERIMENT) {
      currentMode = EXPERIMENT;
      configExperiment();
    }
    delay(1000);
    Serial.println("Arduino Data Ready");
    delay(100);
    sendDataLine();

  } else if (cmd == "DIAG") {
    currentMode = DIAGNOSTIC;
    configDiagnostic();
    Serial.println("Diagnostic mode ON");

  } else if (cmd == "STOP") {
    currentMode = IDLE;
    configExperiment();
    Serial.println("Diagnostic mode OFF");

  } else if (cmd == "PORTS") {
    Serial.print("Ports:,");
    for (int j = 0; j < numValidPorts; j++) {
      if (j > 0) Serial.print(",");
      Serial.print(validPorts[j]);
    }
    Serial.println();
  }
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  Wire.setClock(400000);

  delay(1000);
  Serial.println("Initializing sensors...");
  initSensors();
  Serial.println("Arduino Ready 1");
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    processCommand(cmd);
  }

  if (currentMode == DIAGNOSTIC) {
    if (millis() - lastDiagTime >= DIAG_INTERVAL_MS) {
      lastDiagTime = millis();
      Serial.print("Data:,");
      for (int j = 0; j < numValidPorts; j++) {
        int port = validPorts[j];
        tcaselect(port);

        sensors_event_t ev;
        dpsPressureArray[port]->getEvent(&ev);

        if (j > 0) Serial.print(",");
        Serial.print(ev.pressure, 4);
      }
      Serial.println();
    }
  }
}
