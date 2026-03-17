#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <DHT.h>
<<<<<<< HEAD
#include <LiquidCrystal_I2C.h>   // ✅ LCD library

#define DHTPIN D3
#define DHTTYPE DHT11
#define MQ135_PIN A0

DHT dht(DHTPIN, DHTTYPE);
LiquidCrystal_I2C lcd(0x27, 16, 2);  // ✅ Change 0x27 to 0x3F if display is blank

const char* ssid     = "OPPO A15s";
const char* password = "ledsms01";

String serverBase = "http://192.168.43.235:5000/update";

unsigned long previousMillis = 0;
const long interval = 10000;

void setup() {
  Serial.begin(115200);
  delay(2000);
  dht.begin();

  // ✅ LCD init
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Apple Monitor");
  lcd.setCursor(0, 1);
  lcd.print("Starting...");
  delay(2000);
  lcd.clear();

  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");

  lcd.setCursor(0, 0);
=======
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

char ssid[] = "MyESPWiFi";
char pass[] = "12345678";

#define DHTPIN D4
#define DHTTYPE DHT11
#define MQ135_PIN A0
#define FAN_PIN D5

DHT dht(DHTPIN, DHTTYPE);

LiquidCrystal_I2C lcd(0x27,16,2);

// CHANGE TO YOUR PC IP
String serverName = "http://10.251.27.229:5000/update";

float tempThreshold = 26;   // fan ON temperature

void setup() {

  Serial.begin(115200);

  dht.begin();

  pinMode(FAN_PIN, OUTPUT);
  digitalWrite(FAN_PIN, LOW);

  lcd.init();
  lcd.backlight();

  lcd.setCursor(0,0);
  lcd.print("Apple Monitor");

  WiFi.begin(ssid, pass);

  lcd.setCursor(0,1);
>>>>>>> 56819865be70e812411e1008daf22ce1016d29cf
  lcd.print("Connecting WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

<<<<<<< HEAD
  Serial.println();
  Serial.println("✅ WiFi Connected");
  Serial.print("ESP IP: ");
  Serial.println(WiFi.localIP());

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("WiFi Connected!");
  delay(1500);
  lcd.clear();
}

void sendData(float temp, float hum, int mq135) {

  WiFiClient client;
  HTTPClient http;

  String url = serverBase +
               "?temp="  + String(temp, 1) +
               "&hum="   + String(hum, 1) +
               "&mq135=" + String(mq135);

  Serial.println("📡 Sending: " + url);

  http.begin(client, url);
  http.setTimeout(15000);

  int httpCode = http.GET();

  Serial.print("HTTP Code: ");
  Serial.println(httpCode);

  if (httpCode == 200) {
    String response = http.getString();
    Serial.println("✅ Success: " + response);

    // ✅ Parse spoil_risk from JSON response
    int riskIndex = response.indexOf("\"spoil_risk\":");
    if (riskIndex != -1) {
      float risk = response.substring(riskIndex + 13).toFloat();

      // ✅ LCD Line 1: Temp + Humidity
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("T:");
      lcd.print(temp, 1);
      lcd.print((char)223);  // degree symbol
      lcd.print("C H:");
      lcd.print(hum, 0);
      lcd.print("%");

      // ✅ LCD Line 2: MQ135 + Risk
      lcd.setCursor(0, 1);
      lcd.print("MQ:");
      lcd.print(mq135);
      lcd.print(" Risk:");
      lcd.print(risk, 1);
      lcd.print("%");
    }

  } else {
    Serial.println("❌ Failed: " + http.errorToString(httpCode));

    // ✅ Show error on LCD
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Send Failed");
    lcd.setCursor(0, 1);
    lcd.print("Code: ");
    lcd.print(httpCode);
  }

  http.end();
}

void loop() {
  unsigned long currentMillis = millis();

  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;

    float temp = NAN, hum = NAN;
    for (int i = 0; i < 5; i++) {
      temp = dht.readTemperature();
      hum  = dht.readHumidity();
      if (!isnan(temp) && !isnan(hum) && temp > 1.0 && hum > 0.0) break;
      Serial.println("⚠ DHT retry " + String(i + 1));
      delay(2000);
    }

    int mq135 = analogRead(MQ135_PIN);

    if (isnan(temp) || isnan(hum) || temp < 1.0 || hum == 0.0) {
      Serial.println("❌ Sensor Error — skipping");
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("Sensor Error!");
      return;
    }

    Serial.println("📊 Reading Sensors...");
    Serial.printf("Temp: %.1f°C  Hum: %.1f%%  MQ135: %d\n", temp, hum, mq135);

    if (WiFi.status() == WL_CONNECTED) {
      sendData(temp, hum, mq135);
    } else {
      Serial.println("⚠ WiFi Disconnected. Reconnecting...");
      WiFi.begin(ssid, password);
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("WiFi Lost...");
    }

    Serial.println("-----------------------------");
  }
}

=======
  lcd.clear();
  lcd.print("WiFi Connected");

  Serial.println("WiFi Connected");
  Serial.print("ESP IP: ");
  Serial.println(WiFi.localIP());

  delay(2000);
}

void loop() {

  float temp = dht.readTemperature();
  float hum = dht.readHumidity();
  int mq135 = analogRead(MQ135_PIN);

  if (!isnan(temp) && !isnan(hum)) {

    Serial.printf("Temp: %.1f°C  Hum: %.1f%%  MQ135: %d\n", temp, hum, mq135);

    // LCD Display
    lcd.clear();

    lcd.setCursor(0,0);
    lcd.print("T:");
    lcd.print(temp);
    lcd.print(" H:");
    lcd.print(hum);

    lcd.setCursor(0,1);
    lcd.print("Gas:");
    lcd.print(mq135);

    // Fan Control
    if(temp > tempThreshold){

      digitalWrite(FAN_PIN, HIGH);

      lcd.setCursor(12,0);
      lcd.print("FAN");

      Serial.println("Fan ON");

    }
    else{

      digitalWrite(FAN_PIN, LOW);

      Serial.println("Fan OFF");

    }

    // Send data to Flask
    if (WiFi.status() == WL_CONNECTED) {

      WiFiClient client;
      HTTPClient http;

      String url = serverName +
                   "?temp=" + String(temp,1) +
                   "&hum=" + String(hum,1) +
                   "&mq135=" + String(mq135);

      http.begin(client, url);

      int httpCode = http.GET();

      Serial.println("Sending Data...");
      Serial.println(url);

      Serial.print("HTTP Code: ");
      Serial.println(httpCode);

      http.end();
    }

  }
  else{

    Serial.println("Sensor Error");
  }

  delay(60000); // 1 minute
}
>>>>>>> 56819865be70e812411e1008daf22ce1016d29cf
