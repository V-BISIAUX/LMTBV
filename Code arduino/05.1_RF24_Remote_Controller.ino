/**********************************************************************
* Filename    : RF24_Remote_Controller.ino
* Product     : Freenove 4WD Car for UNO
* Description : Télécommande NRF24L01 — lit les capteurs et envoie les données au robot
* Auther      : www.freenove.com
* Modification: 2019/08/06
**********************************************************************/

// Bibliothèques nécessaires pour la communication SPI et le module radio NRF24L01
#include <SPI.h>
#include "RF24.h"

RF24 radio(9, 10);                // Objet radio : CE sur broche 9, CSN sur broche 10
const byte addresses[6] = "Free1";// Adresse de communication (doit être la même côté robot)

int dataWrite[8];                 // Tableau contenant les 8 valeurs à envoyer

// Déclaration des broches d'entrée/sortie
const int pot1Pin = A0,           // Potentiomètre 1
          pot2Pin = A1,           // Potentiomètre 2
          joystickXPin = A2,      // Axe X du joystick (analogique)
          joystickYPin = A3,      // Axe Y du joystick (analogique)
          joystickZPin = 7,       // Bouton du joystick (clic, numérique)
          s1Pin = 4,              // Interrupteur S1
          s2Pin = 3,              // Interrupteur S2
          s3Pin = 2,              // Interrupteur S3
          led1Pin = 6,            // LED1 : indique la position du POT1
          led2Pin = 5,            // LED2 : indique la position du POT2
          led3Pin = 8;            // LED3 : indique si la transmission radio réussit

void setup() {
  // Initialisation du module radio NRF24L01
  radio.begin();                      // Démarre le module radio
  radio.setPALevel(RF24_PA_MAX);      // Puissance d'émission maximale
  radio.setDataRate(RF24_1MBPS);      // Débit : 1 Mbit/s
  radio.setRetries(0, 15);            // 15 tentatives de renvoi si échec, sans délai entre elles
  radio.openWritingPipe(addresses);   // Ouvre le canal d'émission
  radio.openReadingPipe(1, addresses);// Ouvre le canal de réception (non utilisé ici)
  radio.stopListening();              // Mode émetteur uniquement

  // Configuration des broches
  pinMode(joystickZPin, INPUT);       // Bouton joystick : entrée
  pinMode(s1Pin, INPUT);              // S1 : entrée
  pinMode(s2Pin, INPUT);              // S2 : entrée
  pinMode(s3Pin, INPUT);              // S3 : entrée
  pinMode(led1Pin, OUTPUT);           // LED1 : sortie
  pinMode(led2Pin, OUTPUT);           // LED2 : sortie
  pinMode(led3Pin, OUTPUT);           // LED3 : sortie
}

void loop()
{
  // Lecture de tous les capteurs et stockage dans le tableau d'envoi
  dataWrite[0] = analogRead(pot1Pin);           // Valeur du POT1 (0–1023)
  dataWrite[1] = analogRead(pot2Pin);           // Valeur du POT2 (0–1023)
  dataWrite[2] = analogRead(joystickXPin);      // Position X du joystick
  dataWrite[3] = analogRead(joystickYPin);      // Position Y du joystick
  dataWrite[4] = digitalRead(joystickZPin);     // Bouton du joystick (0 = appuyé)
  dataWrite[5] = digitalRead(s1Pin);            // État de S1 (0 = activé)
  dataWrite[6] = digitalRead(s2Pin);            // État de S2
  dataWrite[7] = digitalRead(s3Pin);            // État de S3

  // Envoi du tableau via radio : LED3 s'allume si la transmission réussit
  if (radio.writeFast(&dataWrite, sizeof(dataWrite)))
  {
    digitalWrite(led3Pin, HIGH);  // Transmission OK
  }
  else {
    digitalWrite(led3Pin, LOW);   // Échec de transmission
  }
  delay(20); // Attendre 20 ms avant le prochain envoi

  // Faire varier la luminosité des LEDs selon la position des potentiomètres
  analogWrite(led1Pin, map(dataWrite[0], 0, 1023, 0, 255));
  analogWrite(led2Pin, map(dataWrite[1], 0, 1023, 0, 255));
}
