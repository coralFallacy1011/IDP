#include <WiFi.h>
#include <HTTPClient.h>
#include <Adafruit_Fingerprint.h>

const char* ssid = "OnePlus 12";
const char* password = "Shriyansh";

const char* serverURL =
"http://192.168.1.107:5000/verify";

HardwareSerial mySerial(2);
Adafruit_Fingerprint finger(&mySerial);

void setup()
{
  Serial.begin(115200);

  WiFi.begin(ssid, password);

  Serial.print("Connecting");

  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi Connected");

  mySerial.begin(57600, SERIAL_8N1, 16, 17);

  finger.begin(57600);

  if (!finger.verifyPassword())
  {
    Serial.println("Fingerprint sensor not found");
    while (1);
  }

  Serial.println("Fingerprint sensor ready");
}

void loop()
{
  if (finger.getImage() != FINGERPRINT_OK)
    return;

  if (finger.image2Tz() != FINGERPRINT_OK)
    return;

  if (finger.fingerFastSearch() != FINGERPRINT_OK)
  {
    Serial.println("Unknown Finger");
    delay(1000);
    return;
  }

  Serial.print("Found ID: ");
  Serial.println(finger.fingerID);

  Serial.print("Confidence: ");
  Serial.println(finger.confidence);

  sendToServer(
      finger.fingerID,
      finger.confidence);

  delay(3000);
}

void sendToServer(int id, int confidence)
{
  if (WiFi.status() != WL_CONNECTED)
    return;

  HTTPClient http;

  http.begin(serverURL);

  http.addHeader(
      "Content-Type",
      "application/json");

  String payload =
      "{\"finger_id\":"
      + String(id)
      + ",\"confidence\":"
      + String(confidence)
      + "}";

  int responseCode =
      http.POST(payload);

  Serial.print("HTTP Response: ");
  Serial.println(responseCode);

  if (responseCode > 0)
  {
    String response =
        http.getString();

    Serial.println(response);
  }

  http.end();
}