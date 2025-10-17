#include <Adafruit_DPS310.h>
#include <Wire.h>

#define TCAADDR 0x70
#define printDelayTime 1000
#define MAX_PORTS 8  // TCA9548A has 8 possible ports

// Each port can have its own DPS310 object
Adafruit_DPS310 dpsArray[MAX_PORTS];
Adafruit_Sensor* dpsTempArray[MAX_PORTS];
Adafruit_Sensor* dpsPressureArray[MAX_PORTS];

int validPorts[MAX_PORTS];
int numValidPorts = 0;

void tcaselect(uint8_t i) {
  if (i > 7) return;
  Wire.beginTransmission(TCAADDR);
  Wire.write(1 << i);
  Wire.endTransmission();
}

void bufferlessPrint(const char* str) {
  while (!Serial)
    ;
  Serial.println(str);
  Serial.flush();
}

int delayAmount = 1000;

void setup() {
  Serial.begin(115200);
  Wire.begin();
  Wire.setClock(100000);

  //bufferlessPrint("Start of setup");
  delay(printDelayTime);

  // Scan all ports once and store valid DPS310s
  for (int i = 0; i < MAX_PORTS; i++) {
    tcaselect(i);
    delay(100);

    if (dpsArray[i].begin_I2C()) {
      char buf[32];
      //snprintf(buf, sizeof(buf), "Port %d has DPS310", i);
      //bufferlessPrint(buf);

      validPorts[numValidPorts++] = i;

      // Get sensor handles
      dpsTempArray[i] = dpsArray[i].getTemperatureSensor();
      dpsPressureArray[i] = dpsArray[i].getPressureSensor();

      // Configure once
      dpsArray[i].configurePressure(DPS310_64HZ, DPS310_64SAMPLES);
      dpsArray[i].configureTemperature(DPS310_64HZ, DPS310_64SAMPLES);

    } else {
      char buf[32];
      //snprintf(buf, sizeof(buf), "Port %d has NO DPS310", i);
      //bufferlessPrint(buf);
    }
  }

  if (numValidPorts == 0) {
    //bufferlessPrint("No valid DPS310 sensors found!");
  }
}

String isGUIConnected = "0";

void loop() {
  //Serial.println(isGUIConnected);
  //detect this in the GUI
  while (!(isGUIConnected == "1")) {
    //Serial.println("Arduino Ready " + isGUIConnected);
    delay(500);

    String command = get_Vals_serial();
    if (command == "GReady") {
      isGUIConnected = "1";
    }
  }
  //getDataNoPython();


  String command = get_Vals_serial();

  if (command == "a") {
    Serial.println("Received a");
    // get data
    getData();
  } else if (command == "b") {
    Serial.println("Received b");
    // get baseline pressure
  }

  //getData();
}

String get_Vals_serial() {
  // gets the angle and distance values from Python
  // Need to tell Python script it's ready
  while (!Serial.available()) {
    Serial.println("Arduino Ready " + isGUIConnected);
    delay(delayAmount);
  }

  //Serial.println("Exited While");

  // Gets rid of anything unimportant that was sent to Arduino from Python
  //while (Serial.available()) {
  //  String incomingString = Serial.readStringUntil('\n');
  //}

  // https://docs.arduino.cc/language-reference/en/functions/communication/serial/read/
  while (!Serial.available()) {}  // stays in while loop until there's something available to read
  if (Serial.available() > 0) {
    // read the incoming byte:
    String incomingString = Serial.readStringUntil('\n');

    return incomingString;
  }
}

void getData() {

  delay(printDelayTime);
  float pressureData[numValidPorts];

  for (int j = 0; j < numValidPorts; j++) {
    int port = validPorts[j];
    char buf[32];
    //snprintf(buf, sizeof(buf), "Reading from port %d", port);
    //bufferlessPrint(buf);

    tcaselect(port);
    delay(50);

    sensors_event_t temp_event, pressure_event;

    // Always try to read temperature
    /*
    dpsTempArray[port]->getEvent(&temp_event);
    Serial.print("Temperature = ");
    Serial.print(temp_event.temperature);
    Serial.println(" *C");
    */

    // Always try to read pressure
    dpsPressureArray[port]->getEvent(&pressure_event);
    pressureData[j] = pressure_event.pressure;

    delay(1000);
  }
  //while (!Serial.available()) {
  Serial.println("Arduino Data Ready");
  delay(delayAmount);
  //}

  Serial.print("Data:,");
  Serial.print(pressureData[0]);
  Serial.print(",");
  Serial.println(pressureData[1]);

  //Wait some time, so that the Dps310 can refill its buffer
  //delay(delayAmount);
}
/*
void getDataNoPython() {
  int num_samples = 3;
  double dataArr1[num_samples];
  double dataArr2[num_samples];

  for (int16_t i = 0; i < num_samples; i++)
  {
    uint8_t pressureCount = 30;
    float pressurePitot[pressureCount];
    float pressureAmbient[pressureCount];
    uint8_t temperatureCount = 30;
    float temperature[temperatureCount];
    double temp[2];
    retData(temperature, temperatureCount, pressurePitot, pressureAmbient, pressureCount, temp);
    dataArr1[i] = temp[0];
    dataArr2[i] = temp[1];
    //Serial.print("Data:,");
    //Serial.print(temp[0]);
    //Serial.print(",");
    //Serial.println(temp[1]);
  }
  double avg_pressurePitot = findMedian(dataArr1, num_samples);
  double avg_pressureAmbient = findMedian(dataArr2, num_samples);
  // Send data to python to write
  Serial.print("Data:,");
  Serial.print(avg_pressurePitot);
  Serial.print(",");
  Serial.println(avg_pressureAmbient);



  //Wait some time, so that the Dps310 can refill its buffer
  //delay(delayAmount);
}
*/
float findMedian(double arr[], int size) {
  //bubble sort from https://www.geeksforgeeks.org/bubble-sort/
  int i, j;
  for (i = 0; i < size - 1; i++) {
    // Last i elements are already
    // in place
    for (j = 0; j < size - i - 1; j++) {
      if (arr[j] > arr[j + 1]) {
        double temp = arr[j];
        arr[j] = arr[j + 1];
        arr[j + 1] = temp;
      }
    }
  }

  if (!(size % (2))) {
    return (arr[(int)(size / 2)] + arr[(int)(size / 2 + 1)]) / 2;
  } else {
    return arr[(int)(size / 2)];
  }
}

/*
void retData(float* temperature, uint8_t temperatureCount, float* pressurePitot, float* pressureAmbient, uint8_t pressureCount, double* result) {
  double* dataArr = new double[2];
  unsigned long time1 = millis();
  int16_t ret1 = Dps310PressureSensorPitot.getContResults(temperature, temperatureCount, pressurePitot, pressureCount);
  int16_t ret2 = Dps310PressureSensorAmbient.getContResults(temperature, temperatureCount, pressureAmbient, pressureCount);
  unsigned long time2 = millis();
  //Serial.print("Read Time is ");
  //Serial.println(time2 - time1);
  
  while(ret1 != 0 || ret2 != 0){
    delay(delayAmount);
    Serial.println("Retrying");
    ret1 = Dps310PressureSensorPitot.getContResults(temperature, temperatureCount, pressurePitot, pressureCount);
    ret2 = Dps310PressureSensorAmbient.getContResults(temperature, temperatureCount, pressureAmbient, pressureCount);
  }

  double sumPitot = 0;
  double sumAmbient = 0;
  for (int16_t i = 0; i < pressureCount; i++)
  {
    sumPitot += pressurePitot[i];
    sumAmbient += pressureAmbient[i];
    //Serial.print("Data:,");
    //Serial.print(sumPitot);
    //Serial.print(",");
    //Serial.println(sumAmbient);
  }
  double avg_pressurePitot = sumPitot / (float)pressureCount;
  double avg_pressureAmbient = sumAmbient / (float)pressureCount;
  result[0] = avg_pressurePitot;
  result[1] = avg_pressureAmbient;

  //Serial.print("Data:,");
  //Serial.print(avg_pressurePitot);
  //Serial.print(",");
  //Serial.println(avg_pressureAmbient);
  delay(delayAmount);
  //delete temperature;
  //delete pressurePitot;
  //delete pressureAmbient;
  //return dataArr;

}
*/