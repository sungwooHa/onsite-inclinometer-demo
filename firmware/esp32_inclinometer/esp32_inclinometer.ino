#include <Wire.h>
#include <math.h>
#include "BluetoothSerial.h"
#include "esp_gap_bt_api.h"

// =========================
// Bluetooth
// =========================
BluetoothSerial SerialBT;

const char* BT_DEVICE_NAME = "MIDAS_ONSITE_SENSOR";
const char* DEVICE_ID = "midas-onsite-sensor-01";
const char* DEVICE_NAME_KR = "마이다스 온사이트 센서";

// =========================
// Pin Mapping
// =========================
#define MPU_ADDR 0x68

#define REG_PWR_MGMT_1 0x6B
#define REG_WHO_AM_I   0x75

#define SDA_PIN 21          // J,8  = D21
#define SCL_PIN 22          // J,11 = D22
#define BUZZER_PIN 18       // J,6  = D18
#define BUTTON_PIN 23       // J,12 = D23
#define STATUS_LED_PIN 2    // ESP32 보드 내장 LED 후보

// =========================
// Sensor Scale
// =========================
const float ACCEL_SCALE = 16384.0; // ±2g 가정
const float GYRO_SCALE  = 131.0;   // ±250 deg/s 가정

// =========================
// Tilt Detection Threshold
// 현재 장착 기준:
// 정상 Roll 평균 ≈ -93.2
// 비정상/기울어짐 Roll 평균 ≈ -113.0
//
// 너무 민감하지 않게:
// Roll < -100.0 이면 기울어짐/위험
// Roll > -97.0 이면 정상 복귀
// -100.0 ~ -97.0 사이에서는 이전 상태 유지
// =========================
const float TILTED_ROLL_THRESHOLD = -100.0;
const float NORMAL_ROLL_THRESHOLD = -97.0;

// candidate 상태가 이 시간 이상 연속 유지돼야 전이를 확정한다.
// 1초 미만의 순간 떨림은 전이로 치지 않아 STATE_CHANGED가 나가지 않는다.
const unsigned long STATE_DWELL_MS = 1000;

const float MOVING_GYRO_THRESHOLD = 5.0;

// =========================
// Buzzer Pattern
// 기울어짐 상태로 전이될 때 삐-익 / 삐-익 장음 경고를 MAX_BEEPS 번만 울린다.
// 속도(ON/OFF 길이)는 그대로, 횟수만 제한한다.
// 5번 다 울린 뒤에는 정상으로 복귀했다가 다시 기울어져야 또 울린다.
// =========================
const unsigned long BEEP_ON_MS  = 1200;
const unsigned long BEEP_OFF_MS = 800;
const int MAX_BEEPS = 5;

bool buzzerOn = false;
unsigned long lastBeepChangeTime = 0;
int beepCount = 0;

// =========================
// Status LED Blink
// Bluetooth 미연결/페어링 대기 = 천천히 점멸
// Bluetooth 연결됨 = ON 고정
// 재시작/초기화 중 = 빠른 점멸
// =========================
const unsigned long BT_WAIT_BLINK_ON_MS = 300;
const unsigned long BT_WAIT_BLINK_OFF_MS = 700;

bool statusLedOn = false;
unsigned long lastStatusLedChangeTime = 0;
bool isStatusLedBusy = false;

// =========================
// Button Handling
// INPUT_PULLUP 기준:
// 안 누름 = HIGH
// 누름   = LOW
// =========================
const unsigned long DEBOUNCE_MS = 40;
const unsigned long LONG_PRESS_MS = 2000;

bool lastRawButton = HIGH;
bool stableButton = HIGH;
unsigned long lastButtonChangeTime = 0;
unsigned long buttonPressedAt = 0;
bool longPressHandled = false;

// =========================
// State
// =========================
String currentState = "알수없음";
String previousState = "알수없음";

// dwell(유지시간) 게이트: candidate가 STATE_DWELL_MS 이상 유지돼야 확정
String candidateState = "알수없음";
unsigned long candidateSince = 0;

float lastPitch = 0.0;
float lastRoll = 0.0;
float lastGyroZ = 0.0;
bool lastMoving = false;

bool lastBtConnected = false;

// =========================
// Low-level I2C read
// =========================
int16_t read16(uint8_t reg) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);

  Wire.requestFrom(MPU_ADDR, 2);

  if (Wire.available() < 2) {
    return 0;
  }

  return (Wire.read() << 8) | Wire.read();
}

uint8_t read8(uint8_t reg) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);

  Wire.requestFrom(MPU_ADDR, 1);

  if (Wire.available()) {
    return Wire.read();
  }

  return 0;
}

// =========================
// Status LED UX
// =========================
void setStatusLedConnected() {
  isStatusLedBusy = false;
  statusLedOn = true;
  digitalWrite(STATUS_LED_PIN, HIGH);
}

void setStatusLedOff() {
  statusLedOn = false;
  digitalWrite(STATUS_LED_PIN, LOW);
}

void updateStatusLedWaitingBlink() {
  if (isStatusLedBusy) {
    return;
  }

  if (SerialBT.hasClient()) {
    setStatusLedConnected();
    return;
  }

  unsigned long now = millis();
  unsigned long interval = statusLedOn ? BT_WAIT_BLINK_ON_MS : BT_WAIT_BLINK_OFF_MS;

  if (now - lastStatusLedChangeTime >= interval) {
    statusLedOn = !statusLedOn;
    digitalWrite(STATUS_LED_PIN, statusLedOn ? HIGH : LOW);
    lastStatusLedChangeTime = now;
  }
}

void blinkStatusLedFast(int count) {
  isStatusLedBusy = true;

  for (int i = 0; i < count; i++) {
    digitalWrite(STATUS_LED_PIN, HIGH);
    delay(100);
    digitalWrite(STATUS_LED_PIN, LOW);
    delay(100);
  }

  isStatusLedBusy = false;
  statusLedOn = false;
  lastStatusLedChangeTime = millis();
}

// =========================
// Bluetooth
// =========================
void startBluetooth() {
  Serial.println();
  Serial.println("[BT] Starting Bluetooth...");

  bool started = SerialBT.begin(BT_DEVICE_NAME);

  if (started) {
    Serial.print("[BT] Started successfully. Device name: ");
    Serial.println(BT_DEVICE_NAME);
  } else {
    Serial.println("[BT] Start failed");
  }
}

bool isBluetoothConnected() {
  return SerialBT.hasClient();
}

void restartBluetooth() {
  Serial.println("[BT] Restart requested");

  // UX: Bluetooth 재시작 중 빠르게 3회 깜빡임
  blinkStatusLedFast(3);

  if (SerialBT.hasClient()) {
    SerialBT.println("{\"event\":\"BT_RESTART_REQUESTED\"}");
    delay(100);
  }

  SerialBT.end();
  delay(500);

  startBluetooth();

  lastBtConnected = false;
  statusLedOn = false;
  lastStatusLedChangeTime = millis();

  Serial.println("[BT] Restart finished");
}

void clearBluetoothPairings() {
  Serial.println("[BT] Clearing paired devices...");

  int bondedDeviceCount = esp_bt_gap_get_bond_device_num();

  Serial.print("[BT] Bonded device count: ");
  Serial.println(bondedDeviceCount);

  if (bondedDeviceCount <= 0) {
    Serial.println("[BT] No bonded devices to remove");
    return;
  }

  esp_bd_addr_t* bondedDeviceList =
    (esp_bd_addr_t*)malloc(sizeof(esp_bd_addr_t) * bondedDeviceCount);

  if (bondedDeviceList == NULL) {
    Serial.println("[BT] Failed to allocate memory for bonded device list");
    return;
  }

  if (esp_bt_gap_get_bond_device_list(&bondedDeviceCount, bondedDeviceList) == ESP_OK) {
    for (int i = 0; i < bondedDeviceCount; i++) {
      esp_bt_gap_remove_bond_device(bondedDeviceList[i]);
      Serial.print("[BT] Removed bonded device index: ");
      Serial.println(i);
    }
  } else {
    Serial.println("[BT] Failed to get bonded device list");
  }

  free(bondedDeviceList);

  Serial.println("[BT] Pairing information cleared");
}

void resetBluetoothPairing() {
  Serial.println("[BT] Pairing reset requested by long button press");

  // UX: 페어링 초기화 중 빠르게 8회 깜빡임
  blinkStatusLedFast(8);

  if (SerialBT.hasClient()) {
    SerialBT.println("{\"event\":\"BT_PAIRING_RESET_REQUESTED\"}");
    delay(100);
  }

  SerialBT.end();
  delay(500);

  clearBluetoothPairings();
  delay(500);

  startBluetooth();

  lastBtConnected = false;
  statusLedOn = false;
  lastStatusLedChangeTime = millis();

  Serial.println("[BT] Pairing reset finished");
  Serial.println("[BT] If Windows still fails, remove MIDAS_ONSITE_SENSOR from Windows Bluetooth settings and pair again.");
}

void stopOperationBecauseBtDisconnected() {
  currentState = "알수없음";
  previousState = "알수없음";

  buzzerOn = false;
  digitalWrite(BUZZER_PIN, LOW);
}

void checkBluetoothConnection() {
  bool connected = SerialBT.hasClient();

  if (connected != lastBtConnected) {
    if (connected) {
      Serial.println("[BT] Client connected");
      SerialBT.println("{\"event\":\"BT_CONNECTED\",\"deviceId\":\"midas-onsite-sensor-01\"}");

      // 연결되면 LED ON 고정
      setStatusLedConnected();

      // 연결되면 첫 상태를 다시 전송하도록 초기화
      previousState = "알수없음";
    } else {
      Serial.println("[BT] Client disconnected");

      // 연결이 끊기면 장비 동작 중지
      // LED는 꺼짐이 아니라 대기 점멸로 전환됨
      stopOperationBecauseBtDisconnected();

      statusLedOn = false;
      lastStatusLedChangeTime = millis();
    }

    lastBtConnected = connected;
  }
}

// =========================
// JSON Event Sending
// =========================
String toEnglishState(const String& stateKr) {
  if (stateKr == "기울어짐") return "TILTED";
  if (stateKr == "정상") return "NORMAL";
  return "UNKNOWN";
}

void sendStateEvent(const String& prevState, const String& nextState, const char* reason) {
  String json = "{";
  json += "\"event\":\"STATE_CHANGED\",";
  json += "\"deviceId\":\"";
  json += DEVICE_ID;
  json += "\",";
  json += "\"deviceName\":\"";
  json += DEVICE_NAME_KR;
  json += "\",";
  json += "\"bluetoothName\":\"";
  json += BT_DEVICE_NAME;
  json += "\",";
  json += "\"previousState\":\"";
  json += toEnglishState(prevState);
  json += "\",";
  json += "\"state\":\"";
  json += toEnglishState(nextState);
  json += "\",";
  json += "\"reason\":\"";
  json += reason;
  json += "\",";
  json += "\"roll\":";
  json += String(lastRoll, 1);
  json += ",";
  json += "\"pitch\":";
  json += String(lastPitch, 1);
  json += ",";
  json += "\"gyroZ\":";
  json += String(lastGyroZ, 2);
  json += ",";
  json += "\"moving\":";
  json += lastMoving ? "true" : "false";
  json += "}";

  Serial.println(json);
  SerialBT.println(json);
}

void sendCurrentStatus(const char* reason) {
  String json = "{";
  json += "\"event\":\"CURRENT_STATUS\",";
  json += "\"deviceId\":\"";
  json += DEVICE_ID;
  json += "\",";
  json += "\"deviceName\":\"";
  json += DEVICE_NAME_KR;
  json += "\",";
  json += "\"bluetoothName\":\"";
  json += BT_DEVICE_NAME;
  json += "\",";
  json += "\"state\":\"";
  json += toEnglishState(currentState);
  json += "\",";
  json += "\"reason\":\"";
  json += reason;
  json += "\",";
  json += "\"roll\":";
  json += String(lastRoll, 1);
  json += ",";
  json += "\"pitch\":";
  json += String(lastPitch, 1);
  json += ",";
  json += "\"gyroZ\":";
  json += String(lastGyroZ, 2);
  json += ",";
  json += "\"moving\":";
  json += lastMoving ? "true" : "false";
  json += "}";

  Serial.println(json);
  SerialBT.println(json);
}

// =========================
// Buzzer
// =========================
void updateBuzzerPattern() {
  unsigned long now = millis();

  if (currentState == "기울어짐") {
    // 이미 5번 다 울렸으면 더 울리지 않고 조용히 대기
    if (beepCount >= MAX_BEEPS) {
      if (buzzerOn) {
        buzzerOn = false;
        digitalWrite(BUZZER_PIN, LOW);
      }
      return;
    }

    if (buzzerOn && now - lastBeepChangeTime >= BEEP_ON_MS) {
      buzzerOn = false;
      digitalWrite(BUZZER_PIN, LOW);
      lastBeepChangeTime = now;
      beepCount++;  // 삐- 한 번이 끝남
    } else if (!buzzerOn && now - lastBeepChangeTime >= BEEP_OFF_MS) {
      buzzerOn = true;
      digitalWrite(BUZZER_PIN, HIGH);
      lastBeepChangeTime = now;
    }
  } else {
    buzzerOn = false;
    digitalWrite(BUZZER_PIN, LOW);
    beepCount = 0;  // 정상 복귀 시 리셋 → 다음 기울어짐에 다시 5번
  }
}

// =========================
// Button
// 짧게 누름: Bluetooth 재시작
// 2초 이상 길게 누름: ESP32 페어링 정보 삭제 + Bluetooth 재시작
// Bluetooth가 연결되어 있지 않아도 버튼은 항상 동작
// =========================
void updateButton() {
  bool raw = digitalRead(BUTTON_PIN);
  unsigned long now = millis();

  if (raw != lastRawButton) {
    lastButtonChangeTime = now;
    lastRawButton = raw;
  }

  if ((now - lastButtonChangeTime) > DEBOUNCE_MS) {
    if (raw != stableButton) {
      stableButton = raw;

      if (stableButton == LOW) {
        buttonPressedAt = now;
        longPressHandled = false;
        Serial.println("[BUTTON] PRESSED");
      } else {
        Serial.println("[BUTTON] RELEASED");

        if (!longPressHandled) {
          Serial.println("[BUTTON] Short press: restart Bluetooth");
          restartBluetooth();
        }
      }
    }
  }

  if (stableButton == LOW && !longPressHandled) {
    if (now - buttonPressedAt >= LONG_PRESS_MS) {
      longPressHandled = true;
      Serial.println("[BUTTON] Long press: clear pairing and restart Bluetooth");
      resetBluetoothPairing();
    }
  }
}

// =========================
// MPU Setup
// =========================
void setupMpu() {
  Wire.begin(SDA_PIN, SCL_PIN);

  // 50cm 점퍼선 사용을 고려해 I2C 속도 낮춤
  Wire.setClock(50000);

  Serial.println("[MPU] Initializing...");

  uint8_t whoami = read8(REG_WHO_AM_I);

  Serial.print("[MPU] WHO_AM_I = 0x");
  if (whoami < 16) Serial.print("0");
  Serial.println(whoami, HEX);

  Wire.beginTransmission(MPU_ADDR);
  Wire.write(REG_PWR_MGMT_1);
  Wire.write(0x00);
  byte error = Wire.endTransmission();

  if (error == 0) {
    Serial.println("[MPU] Sensor wake up success");
  } else {
    Serial.print("[MPU] Sensor wake up failed. I2C error: ");
    Serial.println(error);
  }
}

// =========================
// Sensor Read + State Update
// =========================
void updateSensorState() {
  int16_t axRaw = read16(0x3B);
  int16_t ayRaw = read16(0x3D);
  int16_t azRaw = read16(0x3F);

  int16_t gxRaw = read16(0x43);
  int16_t gyRaw = read16(0x45);
  int16_t gzRaw = read16(0x47);

  float ax = axRaw / ACCEL_SCALE;
  float ay = ayRaw / ACCEL_SCALE;
  float az = azRaw / ACCEL_SCALE;

  float gx = gxRaw / GYRO_SCALE;
  float gy = gyRaw / GYRO_SCALE;
  float gz = gzRaw / GYRO_SCALE;

  float roll  = atan2(ay, az) * 180.0 / PI;
  float pitch = atan2(-ax, sqrt(ay * ay + az * az)) * 180.0 / PI;

  bool isMoving =
    abs(gx) > MOVING_GYRO_THRESHOLD ||
    abs(gy) > MOVING_GYRO_THRESHOLD ||
    abs(gz) > MOVING_GYRO_THRESHOLD;

  lastRoll = roll;
  lastPitch = pitch;
  lastGyroZ = gz;
  lastMoving = isMoving;

  // 히스테리시스 상태 판정 (candidate만 결정, 아직 확정 아님)
  // -100.0 ~ -97.0 갭 안에서는 candidate를 바꾸지 않아 현재 candidate 유지
  String candidate = candidateState;
  if (roll < TILTED_ROLL_THRESHOLD) {
    candidate = "기울어짐";
  } else if (roll > NORMAL_ROLL_THRESHOLD) {
    candidate = "정상";
  }

  unsigned long now = millis();

  // dwell 게이트: candidate가 바뀌면 타이머 리셋(전이 취소/재시작)
  if (candidate != candidateState) {
    candidateState = candidate;
    candidateSince = now;
  }

  // candidate가 현재 확정 상태와 다르고, STATE_DWELL_MS 이상 연속 유지됐을 때만 확정
  if (candidateState != currentState &&
      (now - candidateSince) >= STATE_DWELL_MS) {
    currentState = candidateState;
  }

  // 상태 변경 순간에만 이벤트 출력 + Bluetooth 전송
  if (currentState != previousState) {
    sendStateEvent(previousState, currentState, "ROLL_THRESHOLD");
    previousState = currentState;
  }
}

// =========================
// Setup / Loop
// =========================
void setup() {
  Serial.begin(115200);
  delay(2000);

  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  pinMode(BUTTON_PIN, INPUT_PULLUP);

  pinMode(STATUS_LED_PIN, OUTPUT);
  setStatusLedOff();
  lastStatusLedChangeTime = millis();

  Serial.println();
  Serial.println("==================================");
  Serial.println("MIDAS ONSITE SENSOR START");
  Serial.println("Device: 마이다스 온사이트 센서");
  Serial.println("Bluetooth: MIDAS_ONSITE_SENSOR");
  Serial.println("==================================");

  setupMpu();
  startBluetooth();

  Serial.println();
  Serial.println("[SYSTEM] Ready");
  Serial.println("[SYSTEM] Bluetooth waiting: LED slow blinking, sensor and buzzer disabled");
  Serial.println("[SYSTEM] Bluetooth connected: LED ON, sensor and buzzer enabled");
  Serial.println("[SYSTEM] Tilted: long buzzer only, LED remains Bluetooth status");
  Serial.println("[SYSTEM] Tilt threshold: roll < -100.0");
  Serial.println("[SYSTEM] Normal threshold: roll > -97.0");
  Serial.println("[SYSTEM] Buzzer: 1200ms ON / 800ms OFF, 5 beeps per tilt");
  Serial.println("[SYSTEM] Short button press: restart Bluetooth, LED fast blink 3 times");
  Serial.println("[SYSTEM] Long button press 2s: clear Bluetooth pairing, LED fast blink 8 times");
  Serial.println();
}

void loop() {
  checkBluetoothConnection();
  updateButton();

  // Bluetooth 연결이 없으면 센서 감지/부저/이벤트 전송을 하지 않음
  // 단, 버튼과 LED 대기 점멸은 계속 동작
  if (!isBluetoothConnected()) {
    digitalWrite(BUZZER_PIN, LOW);
    buzzerOn = false;

    updateStatusLedWaitingBlink();

    delay(50);
    return;
  }

  // Bluetooth 연결된 경우 LED ON 유지
  // 기울어짐 상태에서는 LED를 바꾸지 않고 부저만 울림
  setStatusLedConnected();

  // Bluetooth 연결된 경우에만 실제 감시 동작
  updateSensorState();
  updateBuzzerPattern();

  delay(20);
}
