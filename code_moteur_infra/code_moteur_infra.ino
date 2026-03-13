#include <Wire.h>
#include <Adafruit_MLX90614.h>
#include <Servo.h>

Adafruit_MLX90614 mlx = Adafruit_MLX90614();
Servo myservo;

int pos = 0;

// Réglages
const int STEP_DEG = 2;        // pas de balayage (1 = plus précis, plus lent)
const int SERVO_SETTLE_MS = 80; // temps pour que le servo se stabilise
const int NSAMPLES = 3;        // moyenne de plusieurs mesures pour réduire le bruit

float readObjectTempAvgC() {
  float sum = 0;
  for (int i = 0; i < NSAMPLES; i++) {
    sum += mlx.readObjectTempC();
    delay(10);
  }
  return sum / NSAMPLES;
}

void setup() {
  Serial.begin(9600);
  myservo.attach(9);

  Serial.println("Initialisation du capteur MLX90614...");

  if (!mlx.begin()) {
    Serial.println("Erreur : capteur MLX90614 non détecté !");
    while (1);
  }

  Serial.println("Capteur MLX90614 prêt.");
}

void loop() {
  float maxTemp = -1000.0;   // très bas pour init
  int angleMax = 0;

  // Balayage 0 -> 180
  for (pos = 0; pos <= 180; pos += STEP_DEG) {
    myservo.write(pos);
    delay(SERVO_SETTLE_MS);

    float tObj = readObjectTempAvgC();
    float tAmb = mlx.readAmbientTempC();

    // Affichage instantané
   /* Serial.print("Angle: ");
    Serial.print(pos);
    Serial.print(" deg | Obj: ");
    Serial.print(tObj);
    Serial.print(" C | Amb: ");
    Serial.print(tAmb);
    Serial.println(" C"); */

    // Recherche du max
    if (tObj > maxTemp) {
      maxTemp = tObj;
      angleMax = pos;
    }
  }

  // Résultat du balayage
  Serial.println("==== RESULTAT ====");
  Serial.print("Point le plus chaud: ");
  Serial.print(maxTemp);
  Serial.print(" C a l'angle ");
  Serial.print(angleMax);
  Serial.println(" deg");
  Serial.println("==================");

  // Option : pointer le servo vers le point le plus chaud
  myservo.write(angleMax);

  delay(1500); // pause avant un nouveau scan
}