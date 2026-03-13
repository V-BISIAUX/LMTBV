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
#define MOTOR_DIRECTION       0   // Inverser si besoin (0 ou 1)
#define PIN_DIRECTION_LEFT    4
#define PIN_DIRECTION_RIGHT   3
#define PIN_MOTOR_PWM_LEFT    6
#define PIN_MOTOR_PWM_RIGHT   5
#define MOTOR_PWM_DEAD        10

// ── Servo ────────────────────────────────────────────────────────────
#define PIN_SERVO             2
#define SERVO_CENTER          90

// ── Ultrason HC-SR04 ─────────────────────────────────────────────────
#define PIN_SONIC_TRIG        7
#define PIN_SONIC_ECHO        8
#define MAX_DISTANCE          300
#define SONIC_TIMEOUT         (MAX_DISTANCE * 60)
#define SOUND_VELOCITY        340

// ── Buzzer / Batterie ─────────────────────────────────────────────────
#define PIN_BATTERY           A0
#define PIN_BUZZER            A0

// ── Strip LED WS2812B ─────────────────────────────────────────────────
#define STRIP_I2C_ADDRESS     0x20
#define STRIP_LEDS_COUNT      10
#define LEDS_FRONT_START      0   // LEDs avant : indices 0 à 4
#define LEDS_FRONT_END        4
#define LEDS_REAR_START       5   // LEDs arrière : indices 5 à 9
#define LEDS_REAR_END         9

// ── NRF24L01 ──────────────────────────────────────────────────────────
#define PIN_SPI_CE            9
#define PIN_SPI_CSN           10

// ── Joystick ──────────────────────────────────────────────────────────
#define JOYSTICK_CENTER       512
#define JOYSTICK_DEADZONE     50
#define JOYSTICK_SENSITIVITY  0.6

// ── Timeout radio ─────────────────────────────────────────────────────
#define NRF_UPDATE_TIMEOUT    1000

// ── Paramètres évitement obstacles ───────────────────────────────────
#define OA_OBSTACLE_DISTANCE      40    // Distance (cm) = obstacle
#define OA_OBSTACLE_DISTANCE_LOW  15    // Distance critique (très proche)
#define OA_CRUISE_SPEED           130   // Vitesse de croisière
#define OA_BACK_SPEED             120   // Vitesse marche arrière
#define OA_ROTATE_SPEED           150   // Vitesse rotation sur place
#define OA_SCAN_ANGLE_INTERVAL    50    // Amplitude scan servo (±50°)
#define OA_WAITING_SERVO_TIME     150   // Délai stabilisation servo (ms)

// ── Enum données reçues ───────────────────────────────────────────────
enum RemoteData {
  POT1       = 0,
  POT2       = 1,
  JOYSTICK_X = 2,
  JOYSTICK_Y = 3,
  JOYSTICK_Z = 4,
  S1         = 5,
  S2         = 6,
  S3         = 7
};

// ── Objets ────────────────────────────────────────────────────────────
RF24 radio(PIN_SPI_CE, PIN_SPI_CSN);
const byte addresses[6] = "Free1";
Freenove_WS2812B_Controller strip(STRIP_I2C_ADDRESS, STRIP_LEDS_COUNT, TYPE_GRB);
Servo servo;

// ── Variables globales ────────────────────────────────────────────────
int  nrfDataRead[8];
bool nrfComplete       = false;
bool isBuzzered        = false;
u32  lastNrfUpdateTime = 0;

// ════════════════════════════════════════════════════════════════════
void setup() {
  pinsSetup();
  servo.attach(PIN_SERVO);
  servo.write(SERVO_CENTER);
  if (!nrf24L01Setup()) {
    alarm(4, 2);
  }
  while (!strip.begin());
  strip.setAllLedsColor(0x000000);
}

// ════════════════════════════════════════════════════════════════════
void loop() {
  if (getNrf24L01Data()) {
    clearNrfFlag();
    lastNrfUpdateTime = millis();

    // LEDs actives dans les deux modes
    updateLeds();

    // S3 détermine le mode de conduite
    if (nrfDataRead[S3] == 0) {
      // ── MODE AUTONOME (S3 allumé) ─────────────────────────────
      updateAutonomousMode();
    } else {
      // ── MODE TÉLÉCOMMANDE (S3 éteint) ────────────────────────
      updateCarActionByNrfRemote();
    }
  }

  // Sécurité : perte du signal radio → arrêt immédiat
  if (millis() - lastNrfUpdateTime > NRF_UPDATE_TIMEOUT) {
    lastNrfUpdateTime = millis();
    resetNrfDataBuf();
    motorRun(0, 0);
    setBuzzer(false);
    servo.write(SERVO_CENTER);
  }
}

// ════════════════════════════════════════════════════════════════════
//  LEDs — actives dans les deux modes
// ════════════════════════════════════════════════════════════════════
void updateLeds() {
  // POT1 → teinte (0-255)
  u8 hue        = map(nrfDataRead[POT1], 0, 1023, 0, 255);
  // POT2 → luminosité (0-255)
  u8 brightness = map(nrfDataRead[POT2], 0, 1023, 0, 255);

  // Couleur via la roue WS2812B avec luminosité appliquée
  u32 baseColor = strip.Wheel(hue);
  u8 r = ((baseColor >> 16) & 0xFF) * brightness / 255;
  u8 g = ((baseColor >>  8) & 0xFF) * brightness / 255;
  u8 b = ( baseColor        & 0xFF) * brightness / 255;
  u32 color = ((u32)r << 16) | ((u32)g << 8) | b;

  // S1 : LEDs avant (LOW = allumé)
  bool frontOn = (nrfDataRead[S1] == 0);
  for (int i = LEDS_FRONT_START; i <= LEDS_FRONT_END; i++) {
    strip.setLedColorData(i, frontOn ? color : 0x000000);
  }

  // S2 : LEDs arrière (LOW = allumé)
  bool rearOn = (nrfDataRead[S2] == 0);
  for (int i = LEDS_REAR_START; i <= LEDS_REAR_END; i++) {
    strip.setLedColorData(i, rearOn ? color : 0x000000);
  }

  strip.show();
}

// ════════════════════════════════════════════════════════════════════
//  MODE TÉLÉCOMMANDE
// ════════════════════════════════════════════════════════════════════
void updateCarActionByNrfRemote() {
  int x = applyJoystickSettings(nrfDataRead[JOYSTICK_X]);
  int y = applyJoystickSettings(nrfDataRead[JOYSTICK_Y]);

  int pwmL, pwmR;
  if (y < 0) {
    pwmL = (-y + x) / 2;
    pwmR = (-y - x) / 2;
  } else {
    pwmL = (-y - x) / 2;
    pwmR = (-y + x) / 2;
  }
  motorRun(pwmL, pwmR);

  // Clic joystick Z → buzzer
  setBuzzer(nrfDataRead[JOYSTICK_Z] == 0);
}

// ════════════════════════════════════════════════════════════════════
//  MODE AUTONOME — évitement d'obstacles avec servo scan
// ════════════════════════════════════════════════════════════════════

// Mesure une distance en cm avec le HC-SR04
float getSonar() {
  digitalWrite(PIN_SONIC_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_SONIC_TRIG, LOW);
  unsigned long pingTime = pulseIn(PIN_SONIC_ECHO, HIGH, SONIC_TIMEOUT);
  if (pingTime == 0) return MAX_DISTANCE;
  return (float)pingTime * SOUND_VELOCITY / 2.0 / 10000.0;
}

// Oriente le servo et mesure la distance dans cette direction
float scanAt(int angle) {
  servo.write(angle);
  delay(OA_WAITING_SERVO_TIME);
  return getSonar();
}

void updateAutonomousMode() {
  // Mesure rapide vers l'avant pendant la croisière
  servo.write(SERVO_CENTER);
  float distFront = getSonar();

  if (distFront > OA_OBSTACLE_DISTANCE) {
    // Voie libre → avancer
    motorRun(OA_CRUISE_SPEED, OA_CRUISE_SPEED);
    return;
  }

  // Obstacle détecté → arrêt et scan des 3 directions
  motorRun(0, 0);
  float distLeft   = scanAt(SERVO_CENTER + OA_SCAN_ANGLE_INTERVAL);
  float distCenter = scanAt(SERVO_CENTER);
  float distRight  = scanAt(SERVO_CENTER - OA_SCAN_ANGLE_INTERVAL);
  servo.write(SERVO_CENTER);

  // Si très proche : reculer d'abord
  if (distCenter < OA_OBSTACLE_DISTANCE_LOW) {
    motorRun(-OA_BACK_SPEED, -OA_BACK_SPEED);
    delay(400);
    motorRun(0, 0);
  }

  // Choisir la direction la plus dégagée
  if (distLeft > OA_OBSTACLE_DISTANCE && distRight > OA_OBSTACLE_DISTANCE) {
    // Les deux côtés libres → choisir le plus dégagé
    if (distLeft >= distRight) {
      motorRun(-OA_ROTATE_SPEED, OA_ROTATE_SPEED); // Tourner à gauche
    } else {
      motorRun(OA_ROTATE_SPEED, -OA_ROTATE_SPEED); // Tourner à droite
    }
    delay(400);
  }
  else if (distLeft > OA_OBSTACLE_DISTANCE) {
    // Gauche libre → tourner à gauche
    motorRun(-OA_ROTATE_SPEED, OA_ROTATE_SPEED);
    delay(400);
  }
  else if (distRight > OA_OBSTACLE_DISTANCE) {
    // Droite libre → tourner à droite
    motorRun(OA_ROTATE_SPEED, -OA_ROTATE_SPEED);
    delay(400);
  }
  else {
    // Impasse → reculer et faire demi-tour
    motorRun(-OA_BACK_SPEED, -OA_BACK_SPEED);
    delay(500);
    motorRun(-OA_ROTATE_SPEED, OA_ROTATE_SPEED);
    delay(700);
  }

  motorRun(0, 0);
}

// ════════════════════════════════════════════════════════════════════
//  JOYSTICK
// ════════════════════════════════════════════════════════════════════
int applyJoystickSettings(int rawValue) {
  int centered = rawValue - JOYSTICK_CENTER;
  if (abs(centered) < JOYSTICK_DEADZONE) return 0;
  if (centered > 0)
    centered = (centered - JOYSTICK_DEADZONE) * JOYSTICK_SENSITIVITY;
  else
    centered = (centered + JOYSTICK_DEADZONE) * JOYSTICK_SENSITIVITY;
  return constrain(centered, -512, 512);
}

// ════════════════════════════════════════════════════════════════════
//  NRF24L01
// ════════════════════════════════════════════════════════════════════
bool nrf24L01Setup() {
  if (radio.begin()) {
    radio.setPALevel(RF24_PA_MAX);
    radio.setDataRate(RF24_1MBPS);
    radio.setRetries(0, 15);
    radio.openWritingPipe(addresses);
    radio.openReadingPipe(1, addresses);
    radio.startListening();
    FlexiTimer2::set(20, 1.0 / 1000, checkNrfReceived);
    FlexiTimer2::start();
    return true;
  }
  return false;
}

void checkNrfReceived() {
  delayMicroseconds(1000);
  if (radio.available()) {
    while (radio.available()) {
      radio.read(nrfDataRead, sizeof(nrfDataRead));
    }
    nrfComplete = true;
    return;
  }
  nrfComplete = false;
}

bool getNrf24L01Data() { return nrfComplete; }
void clearNrfFlag()    { nrfComplete = false; }

void resetNrfDataBuf() {
  nrfDataRead[POT1]       = 0;
  nrfDataRead[POT2]       = 0;
  nrfDataRead[JOYSTICK_X] = 512;
  nrfDataRead[JOYSTICK_Y] = 512;
  nrfDataRead[JOYSTICK_Z] = 1;
  nrfDataRead[S1]         = 1;
  nrfDataRead[S2]         = 1;
  nrfDataRead[S3]         = 1;  // S3=1 → mode télécommande par défaut
}

// ════════════════════════════════════════════════════════════════════
//  MOTEURS
// ════════════════════════════════════════════════════════════════════
void motorRun(int speedl, int speedr) {
  int dirL = (speedl > 0) ? (0 ^ MOTOR_DIRECTION) : (1 ^ MOTOR_DIRECTION);
  int dirR = (speedr > 0) ? (1 ^ MOTOR_DIRECTION) : (0 ^ MOTOR_DIRECTION);
  speedl = constrain(abs(speedl), 0, 255);
  speedr = constrain(abs(speedr), 0, 255);
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
void setBuzzer(bool flag) {
  isBuzzered = flag;
  pinMode(PIN_BUZZER, flag ? OUTPUT : INPUT);
  digitalWrite(PIN_BUZZER, flag);
}

void alarm(u8 beat, u8 repeat) {
  beat   = constrain(beat,   1, 9);
  repeat = constrain(repeat, 1, 255);
  for (int j = 0; j < repeat; j++) {
    for (int i = 0; i < beat; i++) {
      setBuzzer(true);  delay(100);
      setBuzzer(false); delay(100);
    }
    delay(500);
  }
}

// ════════════════════════════════════════════════════════════════════
//  INITIALISATION PINS
// ════════════════════════════════════════════════════════════════════
void pinsSetup() {
  pinMode(PIN_DIRECTION_LEFT,  OUTPUT);
  pinMode(PIN_MOTOR_PWM_LEFT,  OUTPUT);
  pinMode(PIN_DIRECTION_RIGHT, OUTPUT);
  pinMode(PIN_MOTOR_PWM_RIGHT, OUTPUT);
  pinMode(PIN_SONIC_TRIG,      OUTPUT);
  pinMode(PIN_SONIC_ECHO,      INPUT);
  setBuzzer(false);
}
