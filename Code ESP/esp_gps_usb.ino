/*
  ESP8266 — Lecture de capteurs et envoi des données via USB vers un Raspberry Pi

  Capteurs utilisés :
    - DHT11       : mesure la température et l'humidité       → broche D3 (GPIO0)
    - Flying Fish : mesure la qualité de l'air (valeur analogique) → broche A0
    - G28U7FTTL   : module GPS, communication série logicielle
                      TXD GPS → D4 (GPIO2)
                      RXD GPS → D1 (GPIO5)

  Connexion avec le Raspberry Pi :
    L'ESP8266 est branché via USB. Il apparaît sur la Pi comme /dev/ttyUSB0.
*/

#include <SoftwareSerial.h>
#include <DHT.h>
#include <TinyGPSPlus.h>

// ─── Broches ─────────────────────────────────────────────────────────────────
#define DHT_PIN   4     // Broche de données du capteur DHT11
#define DHT_TYPE  DHT11
#define AIR_PIN   A0     // Broche analogique du capteur de qualité de l'air

static const uint8_t  GPS_RX_PIN = 2; // Réception des données GPS (D4)
static const uint8_t  GPS_TX_PIN = 5; // Émission vers le GPS (D1)  
static const uint32_t GPS_BAUD = 9600; // Vitesse de communication avec le GPS

// ─── Intervalle d'envoi ───────────────────────────────────────────────────────
#define SEND_INTERVAL_MS  2000  // Délai entre deux envois de données (en ms)

// ─── Objets ──────────────────────────────────────────────────────────────────
DHT dht(DHT_PIN, DHT_TYPE);           // Capteur DHT11
SoftwareSerial gpsSerial(GPS_RX_PIN, GPS_TX_PIN); // Port série logiciel pour le GPS
TinyGPSPlus gps;     // Décodeur de trames GPS NMEA

String nmeaLine = ""; // Stockage temporaire de la trame GPS en cours de réception

// ─── Helpers qualité air ─────────────────────────────────────────────────────

// Convertit la valeur brute (0–1023) en indice de qualité (0 = mauvais, 100 = excellent)
int rawToAirQuality(int raw) {
  return map(constrain(raw, 0, 1023), 0, 1023, 100, 0);
}

// Retourne une étiquette textuelle selon l'indice de qualité de l'air
String airLabel(int q) {
  if (q >= 80) return "Excellent";
  if (q >= 60) return "Bon";
  if (q >= 40) return "Modere";
  if (q >= 20) return "Mauvais";
  return "Tres mauvais";
}

// ─── Lecture GPS ─────────────────────────────────────────────────────────────

// Lit les caractères disponibles sur le port GPS et les passe au décodeur TinyGPS
void lireGPS() {
  while (gpsSerial.available()) {
    char c = gpsSerial.read();
    gps.encode(c); // Décode le caractère reçu
    if (c == '\n') {
      nmeaLine = ""; // Fin de trame : on repart à zéro
    } else if (c != '\r') {
      nmeaLine += c; // Accumule les caractères de la trame courante
    }
  }
}

// ─── Construction et envoi du JSON ───────────────────────────────────────────

// Lit tous les capteurs, construit un objet JSON et l'envoie via le port série USB
void envoyerDonnees() {
  lireGPS();

  // Lecture température et humidité
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();

  // Lecture et conversion de la qualité de l'air
  int rawAir = analogRead(AIR_PIN);
  int airQuality = rawToAirQuality(rawAir);

  // Si la lecture DHT échoue, on met "null" dans le JSON
  String tempStr = isnan(temperature) ? "null" : String(temperature, 1);
  String humiStr = isnan(humidity) ? "null" : String(humidity,    1);

  // Données GPS : si le champ n'est pas encore valide, on met "null"
  String lat = gps.location.isValid() ? String(gps.location.lat(), 6) : "null";
  String lng = gps.location.isValid() ? String(gps.location.lng(), 6) : "null";
  String alt = gps.altitude.isValid() ? String(gps.altitude.meters(), 1) : "null";
  String spd = gps.speed.isValid() ? String(gps.speed.kmph(), 1) : "null";
  String course = gps.course.isValid() ? String(gps.course.deg(), 1) : "null";
  String sats = gps.satellites.isValid() ? String(gps.satellites.value()) : "null";
  String hdop = gps.hdop.isValid() ? String(gps.hdop.hdop(), 2) : "null";

  // Formatage de la date et de l'heure GPS en chaînes ISO
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

  // Indique si le GPS a un fix
  String fix = gps.location.isValid() ? "true" : "false";

  // Construction du JSON avec toutes les données
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

  // Envoi du JSON sur le port USB
  Serial.println(json);
}

// ─── Setup ───────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);      // Initialise la communication USB avec la Pi
  dht.begin();         // Démarre le capteur DHT11
  gpsSerial.begin(GPS_BAUD); // Démarre la communication série avec le GPS
}

// ─── Loop ────────────────────────────────────────────────────────────────────
void loop() {
  lireGPS(); // Lit en continu les données GPS pour ne pas en manquer

  // Envoie les données toutes les SEND_INTERVAL_MS millisecondes
  static unsigned long lastSend = 0;
  if (millis() - lastSend >= SEND_INTERVAL_MS) {
    lastSend = millis();
    envoyerDonnees();
  }

  // Avertissement si le GPS n'envoie rien après 5 secondes (câblage ou module défectueux)
  static bool warned = false;
  if (millis() > 5000 && gps.charsProcessed() < 10 && !warned) {
    warned = true;
    Serial.println("{\"error\":\"GPS: peu ou pas de donnees recues\"}");
  }
}
