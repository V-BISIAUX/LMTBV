/*
  ESP8266 — Envoi capteurs + GPS via USB vers Raspberry Pi
  ─────────────────────────────────────────────────────────
  Capteurs :
    - DHT11        : Température & Humidité        → D3 (GPIO0)
    - Flying Fish  : Qualité de l'air (analogique) → A0
    - G28U7FTTL    : GPS NMEA-0183 via SoftwareSerial
                       TXD GPS → D4 (GPIO2)
                       RXD GPS → D1 (GPIO5)

  Connexion Pi :
    Câble USB-A (ESP) → micro-USB port "USB" (Pi Zero 2W)
    L'ESP apparaît sur la Pi comme /dev/ttyUSB0
*/

#include <SoftwareSerial.h>
#include <DHT.h>
#include <TinyGPSPlus.h>

// ─── Broches ─────────────────────────────────────────────────────────────────
#define DHT_PIN    4        // D3 = GPIO0
#define DHT_TYPE   DHT11
#define AIR_PIN    A0

static const uint8_t  GPS_RX_PIN = 2;   // D4 = GPIO2 — reçoit TXD du GPS
static const uint8_t  GPS_TX_PIN = 5;   // D1 = GPIO5 — envoie sur RXD du GPS
static const uint32_t GPS_BAUD   = 9600;

// ─── Intervalle d'envoi ───────────────────────────────────────────────────────
#define SEND_INTERVAL_MS  2000   // Envoi toutes les 2 secondes

// ─── Objets ──────────────────────────────────────────────────────────────────
DHT            dht(DHT_PIN, DHT_TYPE);
SoftwareSerial gpsSerial(GPS_RX_PIN, GPS_TX_PIN);
TinyGPSPlus    gps;

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

// ─── Lecture GPS ─────────────────────────────────────────────────────────────
void lireGPS() {
  while (gpsSerial.available()) {
    char c = gpsSerial.read();
    gps.encode(c);
    if (c == '\n') {
      nmeaLine = "";
    } else if (c != '\r') {
      nmeaLine += c;
    }
  }
}

// ─── Construction et envoi du JSON ───────────────────────────────────────────
void envoyerDonnees() {
  lireGPS();

  float temperature = dht.readTemperature();
  float humidity    = dht.readHumidity();

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

  // Envoi via USB vers la Pi (une ligne JSON terminée par \n)
  Serial.println(json);
}

// ─── Setup ───────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  dht.begin();
  gpsSerial.begin(GPS_BAUD);
}

// ─── Loop ────────────────────────────────────────────────────────────────────
void loop() {
  lireGPS();

  static unsigned long lastSend = 0;
  if (millis() - lastSend >= SEND_INTERVAL_MS) {
    lastSend = millis();
    envoyerDonnees();
  }

  static bool warned = false;
  if (millis() > 5000 && gps.charsProcessed() < 10 && !warned) {
    warned = true;
    Serial.println("{\"error\":\"GPS: peu ou pas de donnees recues\"}");
  }
}
