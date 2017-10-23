#include <Arduino.h>
int ST2Relay = 4;
int ST1Relay = 3;
int FANRelay = 2;
unsigned long timeout = 3600000;
unsigned long cooldown = 45000; // fan cooldown after heating
unsigned long previousFanTime = millis();
unsigned long currentMillis = millis();
int currentstate = 0;
int debounce = 500; //time between state changes
unsigned int integerValue=0;  // Max value is 65535
char incomingByte;

void setup() {
  pinMode(ST2Relay, OUTPUT);
  pinMode(ST1Relay, OUTPUT);
  pinMode(FANRelay, OUTPUT);
  digitalWrite(ST2Relay, HIGH);
  digitalWrite(ST1Relay, HIGH);
  digitalWrite(FANRelay, HIGH);
  Serial.begin(9600);                             // serial data rate is set for 9600bps(bits per second)
  delay(500);
  }

  int hvacmode(int n){
    int newstate = 0;
    if (n==3){
      digitalWrite(ST2Relay, LOW);
      digitalWrite(ST1Relay, LOW);
      digitalWrite(FANRelay, HIGH);
      newstate = 3;
    }
    else if (n==2){
      digitalWrite(ST2Relay, HIGH);
      digitalWrite(ST1Relay, LOW);
      digitalWrite(FANRelay, HIGH);
      newstate = 2;
    }
    else if (n==1){
      digitalWrite(ST2Relay, HIGH);
      digitalWrite(ST1Relay, HIGH);
      digitalWrite(FANRelay, LOW);
      previousFanTime = millis();
      newstate = 1;
      }
    else if ((currentstate>1) && (currentstate<4)){
         digitalWrite(ST2Relay, HIGH);
         digitalWrite(ST1Relay, HIGH);
         digitalWrite(FANRelay, LOW);
         previousFanTime = millis();
         newstate = 1;
       }
    else if ((n==0) && (currentstate != 1)){
      digitalWrite(ST2Relay, HIGH);
      digitalWrite(ST1Relay, HIGH);
      digitalWrite(FANRelay, HIGH);
      newstate = 0;
      }
    else {
      newstate = currentstate;
    }
  delay(debounce);
  return newstate;
  }

void loop(){
  unsigned long currentMillis = millis();
  unsigned long LastMessage;
    if (Serial.available() > 0) {   // something came across serial
     integerValue = 0;         // throw away previous integerValue
     while(1) {            // force into a loop until 'n' is received
       incomingByte = Serial.read();
       if (incomingByte == '\n') break;   // exit the while(1), we're done receiving
       if (incomingByte == -1) continue;  // if no characters are in the buffer read() returns -1
       integerValue *= 10;  // shift left 1 decimal place
       // convert ASCII to integer, add, and shift left 1 decimal place
       integerValue = ((incomingByte - 48) + integerValue);
       }
    LastMessage = millis();
    if (integerValue == 9){
        Serial.println(currentstate);  // report current state
        }
    else {
        currentstate = hvacmode(integerValue);
         }
    delay(10);
    }
  if ((currentstate == 1) && (((unsigned long)(currentMillis - previousFanTime)) >= cooldown)) {
        currentstate = 0;
        currentstate = hvacmode(0);
    }
  else if ((currentstate > 1) && (((unsigned long)(currentMillis - LastMessage)) >= timeout)){
        currentstate = 0;
        currentstate = hvacmode(0);
      }
  else {
    delay(10);
  }
  }
