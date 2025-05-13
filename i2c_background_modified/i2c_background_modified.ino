#include <Dps310.h>

// Dps310 Opject
Dps310 Dps310PressureSensorPitot = Dps310();
Dps310 Dps310PressureSensorAmbient = Dps310();

int delayAmount = 750;

void setup()
{
  Serial.begin(115200);
  while (!Serial);

  //Call begin to initialize Dps310PressureSensor
  //The parameter 0x76 is the bus address. The default address is 0x77 and does not need to be given.
  //Dps310PressureSensor.begin(Wire, 0x76);
  //Use the commented line below instead to use the default I2C address.
  Dps310PressureSensorPitot.begin(Wire);

  Dps310PressureSensorAmbient.begin(Wire, 0x76);

  //temperature measure rate (value from 0 to 7)
  //2^temp_mr temperature measurement results per second
  int16_t temp_mr = 2;
  //temperature oversampling rate (value from 0 to 7)
  //2^temp_osr internal temperature measurements per result
  //A higher value increases precision
  int16_t temp_osr = 2;
  //pressure measure rate (value from 0 to 7)
  //2^prs_mr pressure measurement results per second
  int16_t prs_mr = 4;
  //pressure oversampling rate (value from 0 to 7)
  //2^prs_osr internal pressure measurements per result
  //A higher value increases precision
  int16_t prs_osr = 4;
  //startMeasureBothCont enables background mode
  //temperature and pressure ar measured automatically
  //High precision and hgh measure rates at the same time are not available.
  //Consult Datasheet (or trial and error) for more information
  int16_t ret1 = Dps310PressureSensorPitot.startMeasureBothCont(temp_mr, temp_osr, prs_mr, prs_osr);
  int16_t ret2 = Dps310PressureSensorAmbient.startMeasureBothCont(temp_mr, temp_osr, prs_mr, prs_osr);
  //Use one of the commented lines below instead to measure only temperature or pressure
  //int16_t ret = Dps310PressureSensor.startMeasureTempCont(temp_mr, temp_osr);
  //int16_t ret = Dps310PressureSensor.startMeasurePressureCont(prs_mr, prs_osr);


  if (ret1 != 0)
  {
    Serial.print("Pitot Init FAILED! ret = ");
    Serial.println(ret1);
  }
  else
  {
    Serial.println("Init complete!");
  }

  if (ret2 != 0)
  {
    Serial.print("Ambient Init FAILED! ret = ");
    Serial.println(ret2);
  }
  else
  {
    Serial.println("Init complete!");
  }
}



void loop()
{
  //getDataNoPython();

  
  String command = get_Vals_serial();

  if (command == "a") {
    Serial.println("Received a");
    // get data
    getData();
  }
  else if (command == "b") {
    Serial.println("Received b");
    // get baseline pressure
  }

  //getData();
  

}

String get_Vals_serial() {
  // gets the angle and distance values from Python
  // Need to tell Python script it's ready
  while (!Serial.available()) {
    Serial.println("Arduino Ready");
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
  int num_samples = 5;
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

  while (!Serial.available()) {
    Serial.println("Arduino Data Ready");
    delay(delayAmount);
  }
  Serial.print("Data:,");
  Serial.print(avg_pressurePitot);
  Serial.print(",");
  Serial.println(avg_pressureAmbient);



  //Wait some time, so that the Dps310 can refill its buffer
  //delay(delayAmount);
}

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
  }
  else {
    return arr[(int)(size / 2)];
  }
}


void retData(float* temperature, uint8_t temperatureCount, float* pressurePitot, float* pressureAmbient, uint8_t pressureCount, double* result) {
  double* dataArr = new double[2];
  int16_t ret1 = Dps310PressureSensorPitot.getContResults(temperature, temperatureCount, pressurePitot, pressureCount);
  int16_t ret2 = Dps310PressureSensorAmbient.getContResults(temperature, temperatureCount, pressureAmbient, pressureCount);
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
