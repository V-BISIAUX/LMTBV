/*
  ESP8266 — Serveur Web de capteurs avec GPS
  ─────────────────────────────────────────
  Capteurs :
    - DHT11        : Température & Humidité        → D3 (GPIO0)
    - Flying Fish  : Qualité de l'air (analogique) → A0
    - G28U7FTTL    : GPS NMEA-0183 via SoftwareSerial
                       TXD GPS → D4 (GPIO2) ← ESP écoute
                       RXD GPS → D1 (GPIO5) → ESP envoie

  ⚠ Broches GPS identiques au code de référence qui fonctionne :
      GPS_RX_PIN = 2 (GPIO2 = D4)  reçoit le TXD du GPS
      GPS_TX_PIN = 5 (GPIO5 = D1)  envoie sur le RXD du GPS
*/

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <SoftwareSerial.h>
#include <DHT.h>
#include <TinyGPSPlus.h>

// ─── Configuration WiFi ──────────────────────────────────────────────────────
const char* SSID     = "HUAWEI-1CTPX9";
const char* PASSWORD = "xxxxx;";

// ─── Broches ─────────────────────────────────────────────────────────────────
#define DHT_PIN    4      // D3 = GPIO0  (libéré du conflit GPS)
#define DHT_TYPE   DHT11
#define AIR_PIN    A0

// GPS — même config que le code de référence qui fonctionne
static const uint8_t  GPS_RX_PIN = 2;     // D4 = GPIO2 — reçoit TXD du GPS
static const uint8_t  GPS_TX_PIN = 5;     // D1 = GPIO5 — envoie sur RXD du GPS
static const uint32_t GPS_BAUD   = 9600;

// ─── Objets ──────────────────────────────────────────────────────────────────
DHT              dht(DHT_PIN, DHT_TYPE);
SoftwareSerial   gpsSerial(GPS_RX_PIN, GPS_TX_PIN);
TinyGPSPlus      gps;
ESP8266WebServer server(80);

// ─── Buffer NMEA (repris du code de référence) ───────────────────────────────
String nmeaLine = "";

// ─── Helpers qualité air ─────────────────────────────────────────────────────
int rawToAirQuality(int raw) {
  return map(constrain(raw, 0, 1023), 0, 1023, 100, 0);
}

String airLabel(int q) {
  if (q >= 80) return "Excellent";
  if (q >= 60) return "Bon";
  if (q >= 40) return "Modere";
  if (q >= 20) return "Mauvais";
  return "Tres mauvais";
}

// ─── Lecture GPS (reprise exacte du code de référence) ───────────────────────
void lireGPS() {
  while (gpsSerial.available()) {
    char c = gpsSerial.read();
    gps.encode(c);

    // Reconstruction des trames NMEA brutes pour debug
    if (c == '\n') {
      if (nmeaLine.length() > 0) {
        Serial.print(F("NMEA: "));
        Serial.println(nmeaLine);
        nmeaLine = "";
      }
    } else if (c != '\r') {
      nmeaLine += c;
    }
  }
}

// ─── Route : /data (JSON) ────────────────────────────────────────────────────
void handleData() {
  lireGPS(); // Vidage du buffer GPS avant de répondre

  float temperature = dht.readTemperature();
  float humidity    = dht.readHumidity();

  // Debug DHT dans le moniteur série
  if (isnan(temperature) || isnan(humidity)) {
    Serial.println(F("[DHT] Erreur de lecture !"));
  } else {
    Serial.print(F("[DHT] Temp="));
    Serial.print(temperature);
    Serial.print(F("C  Humi="));
    Serial.println(humidity);
  }

  int rawAir     = analogRead(AIR_PIN);
  int airQuality = rawToAirQuality(rawAir);

  String tempStr = isnan(temperature) ? "null" : String(temperature, 1);
  String humiStr = isnan(humidity)    ? "null" : String(humidity,    1);

  String lat    = gps.location.isValid()   ? String(gps.location.lat(), 6) : "null";
  String lng    = gps.location.isValid()   ? String(gps.location.lng(), 6) : "null";
  String alt    = gps.altitude.isValid()   ? String(gps.altitude.meters(), 1) : "null";
  String spd    = gps.speed.isValid()      ? String(gps.speed.kmph(), 1) : "null";
  String course = gps.course.isValid()     ? String(gps.course.deg(), 1) : "null";
  String sats   = gps.satellites.isValid() ? String(gps.satellites.value()) : "null";
  String hdop   = gps.hdop.isValid()       ? String(gps.hdop.hdop(), 2) : "null";

  String gpsDate = "null", gpsTime = "null";
  if (gps.date.isValid()) {
    char buf[20];
    snprintf(buf, sizeof(buf), "\"%04d-%02d-%02d\"",
             gps.date.year(), gps.date.month(), gps.date.day());
    gpsDate = buf;
  }
  if (gps.time.isValid()) {
    char buf[20];
    snprintf(buf, sizeof(buf), "\"%02d:%02d:%02d\"",
             gps.time.hour(), gps.time.minute(), gps.time.second());
    gpsTime = buf;
  }

  String fix = gps.location.isValid() ? "true" : "false";

  String json = "{";
  json += "\"temperature\":"  + tempStr + ",";
  json += "\"humidity\":"     + humiStr + ",";
  json += "\"air_raw\":"      + String(rawAir) + ",";
  json += "\"air_quality\":"  + String(airQuality) + ",";
  json += "\"air_label\":\""  + airLabel(airQuality) + "\",";
  json += "\"gps\":{";
  json += "\"fix\":"          + fix + ",";
  json += "\"latitude\":"     + lat + ",";
  json += "\"longitude\":"    + lng + ",";
  json += "\"altitude\":"     + alt + ",";
  json += "\"speed_kmh\":"    + spd + ",";
  json += "\"course_deg\":"   + course + ",";
  json += "\"satellites\":"   + sats + ",";
  json += "\"hdop\":"         + hdop + ",";
  json += "\"date\":"         + gpsDate + ",";
  json += "\"time\":"         + gpsTime;
  json += "}}";

  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", json);
}

// ─── Route : / ───────────────────────────────────────────────────────────────
void handleRoot() {
  String html = "<!DOCTYPE html><html><head><meta charset='utf-8'>"
    "<title>ESP8266 Capteurs + GPS</title></head><body>"
    "<h2>ESP8266 — DHT11 / Flying Fish / GPS G28U7FTTL</h2>"
    "<p><a href='/data'>/data</a> — mesures JSON en temps réel</p>"
    "</body></html>";
  server.send(200, "text/html", html);
}

void handleNotFound() {
  server.send(404, "text/plain", "404 - Route inconnue");
}

// ─── Setup ───────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println(F("\n=== ESP8266 Capteurs + GPS ==="));

  dht.begin();
  Serial.println(F("[DHT] Capteur initialise sur GPIO0 (D3)"));

  gpsSerial.begin(GPS_BAUD);
  Serial.println(F("[GPS] SoftwareSerial demarre"));
  Serial.println(F("[GPS] GPS TX -> D4 (GPIO2) | GPS RX -> D1 (GPIO5)"));

  // Alerte si aucune donnée GPS après 5 secondes
  static bool warned = false;
  // (vérification dans le loop)

  Serial.print(F("[WiFi] Connexion a : "));
  Serial.println(SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(F("\n[WiFi] Connecte !"));
  Serial.print(F("[WiFi] Adresse IP : "));
  Serial.println(WiFi.localIP());

  server.on("/",     handleRoot);
  server.on("/data", handleData);
  server.onNotFound(handleNotFound);
  server.begin();
  Serial.println(F("[HTTP] Serveur demarre sur le port 80"));
}

// ─── Loop ────────────────────────────────────────────────────────────────────
void loop() {
  lireGPS(); // Lecture continue GPS (même logique que le code de référence)
  server.handleClient();

  // Alerte si aucune donnée GPS reçue après 5 secondes
  static bool warned = false;
  if (millis() > 5000 && gps.charsProcessed() < 10 && !warned) {
    warned = true;
    Serial.println(F("[GPS] ATTENTION : peu ou pas de donnees recues."));
    Serial.println(F("[GPS] Verifier cablage, alimentation et baudrate."));
  }
}