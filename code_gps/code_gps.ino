#include <SoftwareSerial.h>
#include <TinyGPSPlus.h>

// RX, TX (Arduino)
SoftwareSerial gpsSerial(4, 3);
TinyGPSPlus gps;

unsigned long lastDisplayTime = 0;
const unsigned long interval = 5000; // 5 secondes

void setup() {
  // Port série USB (pour le moniteur série)
  Serial.begin(9600);
  while (!Serial) {
    ; // Attendre l'ouverture du port (utile sur certaines cartes)
  }
  // Port série logiciel
  gpsSerial.begin(9600);
  Serial.println("Demarrage OK");
}

void loop() {
  // Lecture continue des données GPS
  while (gpsSerial.available()) {
    char c = gpsSerial.read();
    //Serial.print (c);
    gps.encode(c);
  }

  // Affichage toutes les 5 secondes
  if (millis() - lastDisplayTime >= interval) {
    lastDisplayTime = millis();

    if (gps.location.isValid()) {
      Serial.print("Latitude  : ");
      Serial.println(gps.location.lat(), 6);

      Serial.print("Longitude : ");
      Serial.println(gps.location.lng(), 6);
    } else {
      Serial.println("En attente du signal GPS...");
    }

    Serial.println("-----------------------------");
  }
}