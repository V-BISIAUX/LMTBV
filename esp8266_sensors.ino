/*
  ESP8266 - Serveur Web de capteurs
  - DHT11  : Température & Humidité (ex: GPIO2 / D4)
  - Flying Fish MQ : Qualité de l'air (entrée analogique A0)

  Bibliothèques requises :
    - ESP8266WiFi        (incluse avec le board ESP8266)
    - ESP8266WebServer   (incluse avec le board ESP8266)
    - DHT sensor library (Adafruit) + Adafruit Unified Sensor
*/

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <DHT.h>

// ─── Configuration WiFi ────────────────────────────────────────────────────
const char* SSID     = "Nom_wifi";
const char* PASSWORD = "XXXXX;";

// ─── Broches & capteurs ────────────────────────────────────────────────────
#define DHT_PIN  4          // GPIO2 = D2 sur NodeMCU
#define DHT_TYPE DHT11
#define AIR_PIN  A0         // Entrée analogique unique de l'ESP8266

DHT dht(DHT_PIN, DHT_TYPE);
ESP8266WebServer server(80);

// ─── Helpers ───────────────────────────────────────────────────────────────

// Convertit la valeur brute (0-1023) du Flying Fish en pourcentage de qualité
// 0   = air très pollué
// 100 = air très pur
int rawToAirQuality(int raw) {
  // Le Flying Fish donne une tension haute quand l'air est pollué
  return map(constrain(raw, 0, 1023), 0, 1023, 100, 0);
}

// Retourne une description textuelle de la qualité de l'air
String airLabel(int quality) {
  if (quality >= 80) return "Excellent";
  if (quality >= 60) return "Bon";
  if (quality >= 40) return "Modere";
  if (quality >= 20) return "Mauvais";
  return "Tres mauvais";
}

// ─── Route : /data (JSON) ─────────────────────────────────────────────────
void handleData() {
  float temperature = dht.readTemperature();
  float humidity    = dht.readHumidity();
  int   rawAir      = analogRead(AIR_PIN);
  int   airQuality  = rawToAirQuality(rawAir);

  // Gestion d'erreur DHT
  String tempStr = isnan(temperature) ? "null" : String(temperature, 1);
  String humiStr = isnan(humidity)    ? "null" : String(humidity,    1);

  String json = "{";
  json += "\"temperature\":"  + tempStr + ",";
  json += "\"humidity\":"     + humiStr + ",";
  json += "\"air_raw\":"      + String(rawAir) + ",";
  json += "\"air_quality\":"  + String(airQuality) + ",";
  json += "\"air_label\":\""  + airLabel(airQuality) + "\"";
  json += "}";

  // CORS : permet à une page HTML externe d'interroger l'ESP
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", json);
}

// ─── Route : / (page HTML embarquée minimale) ─────────────────────────────
void handleRoot() {
  String html = "<!DOCTYPE html><html><head><meta charset='utf-8'>"
    "<title>ESP8266 Capteurs</title></head><body>"
    "<h2>ESP8266 - Capteurs en ligne</h2>"
    "<p>Interrogez <code>/data</code> pour obtenir les mesures en JSON.</p>"
    "<ul>"
    "<li><a href='/data'>/data</a> — mesures JSON en temps réel</li>"
    "</ul>"
    "</body></html>";
  server.send(200, "text/html", html);
}

// ─── Route 404 ────────────────────────────────────────────────────────────
void handleNotFound() {
  server.send(404, "text/plain", "404 - Route inconnue");
}

// ─── Setup ────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  dht.begin();

  Serial.println("\nConnexion au WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nConnecte !");
  Serial.print("Adresse IP : ");
  Serial.println(WiFi.localIP());

  server.on("/",     handleRoot);
  server.on("/data", handleData);
  server.onNotFound(handleNotFound);
  server.begin();

  Serial.println("Serveur HTTP demarre sur le port 80");
}

// ─── Loop ─────────────────────────────────────────────────────────────────
void loop() {
  server.handleClient();
}
