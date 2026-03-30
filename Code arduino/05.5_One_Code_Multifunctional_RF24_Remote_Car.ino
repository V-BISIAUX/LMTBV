/**********************************************************************
  Filename    : Multifunctional_RF24_Remote_Car.ino
  Product     : Freenove 4WD Car for UNO
  Description : 2 modes : télécommande + autonome
  Modification: 2024
    - S3 OFF → Mode télécommande : joystick + buzzer (Z)
    - S3 ON  → Mode autonome     : évitement obstacles (HC-SR04 + servo scan)
    - S1     → LEDs avant ON/OFF  (dans les 2 modes)
    - S2     → LEDs arrière ON/OFF (dans les 2 modes)
    - POT1   → teinte des LEDs    (dans les 2 modes)
    - POT2   → luminosité des LEDs(dans les 2 modes)
**********************************************************************/
#include "Freenove_WS2812B_RGBLED_Controller.h"
#include "Servo.h"
#include "RF24.h"
#include <FlexiTimer2.h>

// ── Pins moteurs ─────────────────────────────────────────────────────
#define MOTOR_DIRECTION       0   // Mettre à 1 pour inverser le sens si le câblage est inversé
#define PIN_DIRECTION_LEFT    4   // Broche de direction du moteur gauche
#define PIN_DIRECTION_RIGHT   3   // Broche de direction du moteur droit
#define PIN_MOTOR_PWM_LEFT    6   // Broche PWM (vitesse) du moteur gauche
#define PIN_MOTOR_PWM_RIGHT   5   // Broche PWM (vitesse) du moteur droit
#define MOTOR_PWM_DEAD        10  // Valeur PWM minimale en dessous de laquelle le moteur ne tourne pas

// ── Servo ────────────────────────────────────────────────────────────
#define PIN_SERVO             2   // Broche de commande du servo (supporte le capteur ultrason)
#define SERVO_CENTER          90  // Position centrale du servo (face avant)

// ── Ultrason HC-SR04 ─────────────────────────────────────────────────
#define PIN_SONIC_TRIG        7           // Broche TRIG : déclenche la mesure
#define PIN_SONIC_ECHO        8           // Broche ECHO : reçoit l'écho
#define MAX_DISTANCE          300         // Distance maximale mesurable (cm)
#define SONIC_TIMEOUT         (MAX_DISTANCE * 60)  // Timeout en µs pour pulseIn
#define SOUND_VELOCITY        340         // Vitesse du son en m/s

// ── Buzzer / Batterie ─────────────────────────────────────────────────
// La broche A0 sert de buzzer (sortie) ou de mesure batterie (entrée) selon l'usage
#define PIN_BATTERY           A0
#define PIN_BUZZER            A0

// ── Strip LED WS2812B ─────────────────────────────────────────────────
#define STRIP_I2C_ADDRESS     0x20  // Adresse I2C du contrôleur de LEDs
#define STRIP_LEDS_COUNT      10    // Nombre total de LEDs
#define LEDS_FRONT_START      0     // Indice de la première LED avant
#define LEDS_FRONT_END        4     // Indice de la dernière LED avant
#define LEDS_REAR_START       5     // Indice de la première LED arrière
#define LEDS_REAR_END         9     // Indice de la dernière LED arrière

// ── NRF24L01 ──────────────────────────────────────────────────────────
#define PIN_SPI_CE            9   // Broche CE du module radio
#define PIN_SPI_CSN           10  // Broche CSN du module radio

// ── Joystick ──────────────────────────────────────────────────────────
#define JOYSTICK_CENTER       512  // Valeur au repos du joystick (milieu de la plage 0–1023)
#define JOYSTICK_DEADZONE     50   // Zone morte : mouvements trop faibles ignorés
#define JOYSTICK_SENSITIVITY  0.6  // Facteur de réduction de la sensibilité

// ── Timeout radio ─────────────────────────────────────────────────────
#define NRF_UPDATE_TIMEOUT    1000  // Si aucun paquet reçu depuis 1s, on arrête le robot

// ── Paramètres évitement obstacles ───────────────────────────────────
#define OA_OBSTACLE_DISTANCE      40    // Distance (cm) à partir de laquelle un obstacle est détecté
#define OA_OBSTACLE_DISTANCE_LOW  15    // Distance critique : le robot recule immédiatement
#define OA_CRUISE_SPEED           130   // Vitesse en ligne droite
#define OA_BACK_SPEED             120   // Vitesse en marche arrière
#define OA_ROTATE_SPEED           150   // Vitesse de rotation sur place
#define OA_SCAN_ANGLE_INTERVAL    50    // Angle de scan à gauche et à droite (±50° par rapport au centre)
#define OA_WAITING_SERVO_TIME     150   // Délai (ms) pour laisser le servo atteindre sa position

// ── Enum données reçues ───────────────────────────────────────────────
// Indices du tableau nrfDataRead[], correspondant aux données envoyées par la télécommande
enum RemoteData {
  POT1       = 0,  // Potentiomètre 1 → teinte LEDs
  POT2       = 1,  // Potentiomètre 2 → luminosité LEDs
  JOYSTICK_X = 2,  // Axe X du joystick
  JOYSTICK_Y = 3,  // Axe Y du joystick
  JOYSTICK_Z = 4,  // Bouton du joystick (clic)
  S1         = 5,  // Interrupteur S1 → LEDs avant
  S2         = 6,  // Interrupteur S2 → LEDs arrière
  S3         = 7   // Interrupteur S3 → choix du mode (0 = autonome, 1 = télécommande)
};

// ── Objets ────────────────────────────────────────────────────────────
RF24 radio(PIN_SPI_CE, PIN_SPI_CSN);                              // Module radio
const byte addresses[6] = "Free1";                               // Adresse radio partagée avec la télécommande
Freenove_WS2812B_Controller strip(STRIP_I2C_ADDRESS, STRIP_LEDS_COUNT, TYPE_GRB); // Contrôleur LEDs
Servo servo;                                                     // Servo-moteur (pour le scan ultrason)

// ── Variables globales ────────────────────────────────────────────────
int  nrfDataRead[8];           // Tableau des données reçues par radio
bool nrfComplete       = false; // Vrai quand un nouveau paquet a été reçu
bool isBuzzered        = false; // État actuel du buzzer
u32  lastNrfUpdateTime = 0;    // Horodatage du dernier paquet reçu (pour le timeout)

// ════════════════════════════════════════════════════════════════════
void setup() {
  pinsSetup();                 // Configure les broches moteurs, ultrason et buzzer
  servo.attach(PIN_SERVO);
  servo.write(SERVO_CENTER);   // Centre le servo au démarrage
  if (!nrf24L01Setup()) {
    alarm(4, 2);               // Si le module radio échoue : 2 séries de 4 bips d'alerte
  }
  while (!strip.begin());      // Attend que le contrôleur de LEDs soit prêt
  strip.setAllLedsColor(0x000000); // Éteint toutes les LEDs
}

// ════════════════════════════════════════════════════════════════════
void loop() {
  if (getNrf24L01Data()) {       // Si un nouveau paquet radio est disponible
    clearNrfFlag();              // Marque le paquet comme traité
    lastNrfUpdateTime = millis();// Met à jour le temps du dernier paquet reçu

    // Mise à jour des LEDs (active dans les deux modes)
    updateLeds();

    // Sélection du mode selon l'interrupteur S3
    if (nrfDataRead[S3] == 0) {
      // ── MODE AUTONOME (S3 allumé) ─────────────────────────────
      updateAutonomousMode();
    } else {
      // ── MODE TÉLÉCOMMANDE (S3 éteint) ────────────────────────
      updateCarActionByNrfRemote();
    }
  }

  // Sécurité : si aucun paquet reçu depuis plus de 1s, on arrête tout
  if (millis() - lastNrfUpdateTime > NRF_UPDATE_TIMEOUT) {
    lastNrfUpdateTime = millis();
    resetNrfDataBuf();           // Remet les valeurs par défaut (robot immobile)
    motorRun(0, 0);              // Arrêt des moteurs
    setBuzzer(false);            // Buzzer éteint
    servo.write(SERVO_CENTER);   // Servo centré
  }
}

// ════════════════════════════════════════════════════════════════════
//  LEDs — actives dans les deux modes
// ════════════════════════════════════════════════════════════════════
void updateLeds() {
  // Conversion des valeurs POT1 et POT2 (0–1023) en teinte et luminosité (0–255)
  u8 hue        = map(nrfDataRead[POT1], 0, 1023, 0, 255);
  u8 brightness = map(nrfDataRead[POT2], 0, 1023, 0, 255);

  // Calcul de la couleur finale : teinte sur la roue chromatique, atténuée par la luminosité
  u32 baseColor = strip.Wheel(hue);
  u8 r = ((baseColor >> 16) & 0xFF) * brightness / 255;
  u8 g = ((baseColor >>  8) & 0xFF) * brightness / 255;
  u8 b = ( baseColor        & 0xFF) * brightness / 255;
  u32 color = ((u32)r << 16) | ((u32)g << 8) | b;

  // S1 = 0 (appuyé) → LEDs avant allumées avec la couleur calculée, sinon éteintes
  bool frontOn = (nrfDataRead[S1] == 0);
  for (int i = LEDS_FRONT_START; i <= LEDS_FRONT_END; i++) {
    strip.setLedColorData(i, frontOn ? color : 0x000000);
  }

  // S2 = 0 (appuyé) → LEDs arrière allumées, sinon éteintes
  bool rearOn = (nrfDataRead[S2] == 0);
  for (int i = LEDS_REAR_START; i <= LEDS_REAR_END; i++) {
    strip.setLedColorData(i, rearOn ? color : 0x000000);
  }

  strip.show(); // Applique les changements sur le strip
}

// ════════════════════════════════════════════════════════════════════
//  MODE TÉLÉCOMMANDE
// ════════════════════════════════════════════════════════════════════
void updateCarActionByNrfRemote() {
  // Applique la zone morte et la sensibilité aux valeurs brutes du joystick
  int x = applyJoystickSettings(nrfDataRead[JOYSTICK_X]);
  int y = applyJoystickSettings(nrfDataRead[JOYSTICK_Y]);

  // Calcul des vitesses gauche/droite à partir des axes X (rotation) et Y (avance/recul)
  // Ce mélange (tank drive) permet de tourner en avançant simultanément
  int pwmL, pwmR;
  if (y < 0) {
    pwmL = (-y + x) / 2;
    pwmR = (-y - x) / 2;
  } else {
    pwmL = (-y - x) / 2;
    pwmR = (-y + x) / 2;
  }
  motorRun(pwmL, pwmR);

  // Clic sur le joystick (Z = 0) → active le buzzer
  setBuzzer(nrfDataRead[JOYSTICK_Z] == 0);
}

// ════════════════════════════════════════════════════════════════════
//  MODE AUTONOME — évitement d'obstacles avec servo scan
// ════════════════════════════════════════════════════════════════════

// Envoie une impulsion ultrason et retourne la distance mesurée en cm
float getSonar() {
  digitalWrite(PIN_SONIC_TRIG, HIGH);
  delayMicroseconds(10);               // Impulsion de 10 µs pour déclencher la mesure
  digitalWrite(PIN_SONIC_TRIG, LOW);
  unsigned long pingTime = pulseIn(PIN_SONIC_ECHO, HIGH, SONIC_TIMEOUT);
  if (pingTime == 0) return MAX_DISTANCE; // Aucun écho → renvoie la distance max
  return (float)pingTime * SOUND_VELOCITY / 2.0 / 10000.0; // Conversion µs → cm
}

// Oriente le servo vers un angle donné et retourne la distance mesurée dans cette direction
float scanAt(int angle) {
  servo.write(angle);
  delay(OA_WAITING_SERVO_TIME); // Attend que le servo soit bien en position
  return getSonar();
}

void updateAutonomousMode() {
  // Mesure la distance devant le robot (servo au centre)
  servo.write(SERVO_CENTER);
  float distFront = getSonar();

  if (distFront > OA_OBSTACLE_DISTANCE) {
    // Aucun obstacle détecté → avancer tout droit
    motorRun(OA_CRUISE_SPEED, OA_CRUISE_SPEED);
    return;
  }

  // Obstacle détecté → arrêt et scan des 3 directions (gauche, centre, droite)
  motorRun(0, 0);
  float distLeft   = scanAt(SERVO_CENTER + OA_SCAN_ANGLE_INTERVAL); // Gauche
  float distCenter = scanAt(SERVO_CENTER);                          // Centre
  float distRight  = scanAt(SERVO_CENTER - OA_SCAN_ANGLE_INTERVAL); // Droite
  servo.write(SERVO_CENTER);

  // Si l'obstacle est très proche, reculer brièvement avant de choisir une direction
  if (distCenter < OA_OBSTACLE_DISTANCE_LOW) {
    motorRun(-OA_BACK_SPEED, -OA_BACK_SPEED);
    delay(400);
    motorRun(0, 0);
  }

  // Choisir la direction la plus dégagée parmi gauche et droite
  if (distLeft > OA_OBSTACLE_DISTANCE && distRight > OA_OBSTACLE_DISTANCE) {
    // Les deux côtés libres → prendre le plus dégagé
    if (distLeft >= distRight) {
      motorRun(-OA_ROTATE_SPEED, OA_ROTATE_SPEED); // Tourner à gauche
    } else {
      motorRun(OA_ROTATE_SPEED, -OA_ROTATE_SPEED); // Tourner à droite
    }
    delay(400);
  }
  else if (distLeft > OA_OBSTACLE_DISTANCE) {
    // Seule la gauche est libre → tourner à gauche
    motorRun(-OA_ROTATE_SPEED, OA_ROTATE_SPEED);
    delay(400);
  }
  else if (distRight > OA_OBSTACLE_DISTANCE) {
    // Seule la droite est libre → tourner à droite
    motorRun(OA_ROTATE_SPEED, -OA_ROTATE_SPEED);
    delay(400);
  }
  else {
    // Impasse : aucune issue → reculer puis faire demi-tour
    motorRun(-OA_BACK_SPEED, -OA_BACK_SPEED);
    delay(500);
    motorRun(-OA_ROTATE_SPEED, OA_ROTATE_SPEED);
    delay(700);
  }

  motorRun(0, 0); // Arrêt après la manœuvre
}

// ════════════════════════════════════════════════════════════════════
//  JOYSTICK
// ════════════════════════════════════════════════════════════════════

// Centre la valeur brute, applique la zone morte et la sensibilité
// Retourne une valeur dans [-512, 512], 0 si dans la zone morte
int applyJoystickSettings(int rawValue) {
  int centered = rawValue - JOYSTICK_CENTER; // Recentrage autour de 0
  if (abs(centered) < JOYSTICK_DEADZONE) return 0; // Zone morte → considéré comme immobile
  if (centered > 0)
    centered = (centered - JOYSTICK_DEADZONE) * JOYSTICK_SENSITIVITY;
  else
    centered = (centered + JOYSTICK_DEADZONE) * JOYSTICK_SENSITIVITY;
  return constrain(centered, -512, 512); // Limite la plage de sortie
}

// ════════════════════════════════════════════════════════════════════
//  NRF24L01
// ════════════════════════════════════════════════════════════════════

// Initialise le module radio en mode récepteur et démarre la lecture périodique via timer
bool nrf24L01Setup() {
  if (radio.begin()) {
    radio.setPALevel(RF24_PA_MAX);       // Puissance maximale
    radio.setDataRate(RF24_1MBPS);       // Débit : 1 Mbit/s
    radio.setRetries(0, 15);             // 15 tentatives de renvoi si besoin
    radio.openWritingPipe(addresses);
    radio.openReadingPipe(1, addresses);
    radio.startListening();              // Mode récepteur
    // Déclenche checkNrfReceived() toutes les 20 ms via un timer matériel
    FlexiTimer2::set(20, 1.0 / 1000, checkNrfReceived);
    FlexiTimer2::start();
    return true;
  }
  return false; // Échec d'initialisation
}

// Appelée automatiquement toutes les 20 ms par le timer : lit les données radio si disponibles
void checkNrfReceived() {
  delayMicroseconds(1000); // Petite attente pour stabiliser la lecture SPI
  if (radio.available()) {
    while (radio.available()) {
      radio.read(nrfDataRead, sizeof(nrfDataRead)); // Lit tous les paquets en attente
    }
    nrfComplete = true;  // Signale qu'un paquet valide a été reçu
    return;
  }
  nrfComplete = false;   // Aucun paquet disponible
}

bool getNrf24L01Data() { return nrfComplete; }   // Vrai si un nouveau paquet est prêt
void clearNrfFlag()    { nrfComplete = false; }  // Réinitialise le flag après traitement

// Remet les données à des valeurs neutres (robot immobile, tout éteint)
void resetNrfDataBuf() {
  nrfDataRead[POT1]       = 0;    // LEDs éteintes
  nrfDataRead[POT2]       = 0;
  nrfDataRead[JOYSTICK_X] = 512;  // Joystick centré
  nrfDataRead[JOYSTICK_Y] = 512;
  nrfDataRead[JOYSTICK_Z] = 1;    // Bouton relâché
  nrfDataRead[S1]         = 1;    // Interrupteurs ouverts
  nrfDataRead[S2]         = 1;
  nrfDataRead[S3]         = 1;    // S3=1 → mode télécommande par défaut
}

// ════════════════════════════════════════════════════════════════════
//  MOTEURS
// ════════════════════════════════════════════════════════════════════

// Fait tourner les moteurs aux vitesses spécifiées (valeurs signées : positif = avant, négatif = arrière)
void motorRun(int speedl, int speedr) {
  // Calcul du sens de rotation selon le signe de la vitesse (XOR pour gérer l'inversion globale)
  int dirL = (speedl > 0) ? (0 ^ MOTOR_DIRECTION) : (1 ^ MOTOR_DIRECTION);
  int dirR = (speedr > 0) ? (1 ^ MOTOR_DIRECTION) : (0 ^ MOTOR_DIRECTION);
  speedl = constrain(abs(speedl), 0, 255);
  speedr = constrain(abs(speedr), 0, 255);
  // Si les deux vitesses sont sous le seuil mort, on force l'arrêt complet
  if (speedl < MOTOR_PWM_DEAD && speedr < MOTOR_PWM_DEAD) {
    speedl = 0; speedr = 0;
  }
  digitalWrite(PIN_DIRECTION_LEFT,  dirL);
  digitalWrite(PIN_DIRECTION_RIGHT, dirR);
  analogWrite(PIN_MOTOR_PWM_LEFT,   speedl);
  analogWrite(PIN_MOTOR_PWM_RIGHT,  speedr);
}

// ════════════════════════════════════════════════════════════════════
//  BUZZER
// ════════════════════════════════════════════════════════════════════

// Active ou désactive le buzzer
void setBuzzer(bool flag) {
  isBuzzered = flag;
  pinMode(PIN_BUZZER, flag ? OUTPUT : INPUT); // En entrée = buzzer silencieux
  digitalWrite(PIN_BUZZER, flag);
}

// Fait sonner le buzzer en 'beat' bips, répétés 'repeat' fois
void alarm(u8 beat, u8 repeat) {
  beat   = constrain(beat,   1, 9);
  repeat = constrain(repeat, 1, 255);
  for (int j = 0; j < repeat; j++) {
    for (int i = 0; i < beat; i++) {
      setBuzzer(true);  delay(100); // Bip ON pendant 100 ms
      setBuzzer(false); delay(100); // Bip OFF pendant 100 ms
    }
    delay(500); // Pause entre les séries
  }
}

// ════════════════════════════════════════════════════════════════════
//  INITIALISATION PINS
// ════════════════════════════════════════════════════════════════════
void pinsSetup() {
  pinMode(PIN_DIRECTION_LEFT,  OUTPUT); // Sens moteur gauche
  pinMode(PIN_MOTOR_PWM_LEFT,  OUTPUT); // Vitesse moteur gauche
  pinMode(PIN_DIRECTION_RIGHT, OUTPUT); // Sens moteur droit
  pinMode(PIN_MOTOR_PWM_RIGHT, OUTPUT); // Vitesse moteur droit
  pinMode(PIN_SONIC_TRIG,      OUTPUT); // TRIG ultrason : sortie
  pinMode(PIN_SONIC_ECHO,      INPUT);  // ECHO ultrason : entrée
  setBuzzer(false);                     // Buzzer éteint par défaut
}
