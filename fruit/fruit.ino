#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <DHT.h>
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
  lcd.print("Connecting WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

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