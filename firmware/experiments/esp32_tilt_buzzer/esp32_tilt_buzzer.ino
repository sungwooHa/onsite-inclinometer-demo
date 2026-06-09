/*
 * ESP32 + MPU6050 — 기울기 감지 + 부저 알림 (샘플)
 *
 * 동작:
 *  - MPU6050 가속도계로 Roll 각도를 계산, 히스테리시스로 정상/기울어짐 판정
 *  - "기울어짐"이면 부저를 삐삐삐(120ms ON/OFF) 반복, 정상이면 무음
 *  - 상태가 바뀌는 순간에만 시리얼로 사람이 읽는 로그 출력 (JSON 프로토콜 아님)
 *  - 외부 라이브러리 의존성 없음 (Wire I2C 레지스터 직접 접근)
 *
 * 배선 (ESP32 DevKit <-> MPU6050 / 부저):
 *  3V3 -> VCC, GND -> GND, GPIO21 -> SDA, GPIO22 -> SCL, AD0 -> GND(주소 0x68)
 *  GPIO18 -> 부저(+),  GND -> 부저(-)
 *
 * 참고:
 *  - 임계값은 "절대 Roll 각도" 기준(TILTED/NORMAL_ROLL_THRESHOLD).
 *    메인 펌웨어(esp32_inclinometer)의 baseline 대비 사잇각 방식과 다름 —
 *    설치 자세가 바뀌면 측정 기준값(정상 ~-91.4 / 기울어짐 ~-111.4)을 다시 잡아야 함.
 *  - 시리얼 출력은 디버그용 텍스트라 bridge.py 프로토콜과는 호환되지 않음.
 */

#include <Wire.h>
#include <math.h>

#define MPU_ADDR 0x68

#define REG_PWR_MGMT_1 0x6B
#define REG_WHO_AM_I 0x75

#define BUZZER_PIN 18

const float ACCEL_SCALE = 16384.0;
const float GYRO_SCALE = 131.0;

// 측정 기준
// 정상: Roll 약 -91.4
// 기울어짐: Roll 약 -111.4
const float TILTED_ROLL_THRESHOLD = -105.0;  // 이보다 작으면 기울어짐
const float NORMAL_ROLL_THRESHOLD = -98.0;   // 이보다 크면 정상

const float MOVING_GYRO_THRESHOLD = 5.0;

// 삐삐삐 패턴 설정
const unsigned long BEEP_ON_MS = 120;
const unsigned long BEEP_OFF_MS = 120;

String currentState = "알수없음";
String previousState = "알수없음";

bool buzzerOn = false;
unsigned long lastBeepChangeTime = 0;

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

void updateBuzzerPattern() {
  unsigned long now = millis();

  if (currentState == "기울어짐") {
    if (buzzerOn && now - lastBeepChangeTime >= BEEP_ON_MS) {
      buzzerOn = false;
      digitalWrite(BUZZER_PIN, LOW);
      lastBeepChangeTime = now;
    } else if (!buzzerOn && now - lastBeepChangeTime >= BEEP_OFF_MS) {
      buzzerOn = true;
      digitalWrite(BUZZER_PIN, HIGH);
      lastBeepChangeTime = now;
    }
  } else {
    buzzerOn = false;
    digitalWrite(BUZZER_PIN, LOW);
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000);

  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  Wire.begin(21, 22);      // SDA = D21, SCL = D22
  Wire.setClock(100000);

  Serial.println();
  Serial.println("힌지 상태 감지 + 부저 알림 시작");

  // WHO_AM_I 확인
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(REG_WHO_AM_I);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, 1);

  if (Wire.available()) {
    uint8_t whoami = Wire.read();
    Serial.print("WHO_AM_I = 0x");
    if (whoami < 16) Serial.print("0");
    Serial.println(whoami, HEX);
  }

  // Sleep 해제
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(REG_PWR_MGMT_1);
  Wire.write(0x00);
  byte error = Wire.endTransmission();

  if (error == 0) {
    Serial.println("센서 활성화 성공");
  } else {
    Serial.print("센서 활성화 실패. I2C error: ");
    Serial.println(error);
  }

  Serial.println("상태 변경 이벤트 대기 중...");
  Serial.println();
}

void loop() {
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

  // Roll 기준 히스테리시스 판정
  if (roll < TILTED_ROLL_THRESHOLD) {
    currentState = "기울어짐";
  } else if (roll > NORMAL_ROLL_THRESHOLD) {
    currentState = "정상";
  }

  // 상태 변경 순간에만 Serial 출력
  if (currentState != previousState) {
    Serial.print("[상태 변경] ");
    Serial.print(previousState);
    Serial.print(" -> ");
    Serial.print(currentState);

    Serial.print(" | Pitch:");
    Serial.print(pitch, 1);

    Serial.print(" Roll:");
    Serial.print(roll, 1);

    Serial.print(" GyroZ:");
    Serial.print(gz, 2);

    Serial.print(" Moving:");
    Serial.println(isMoving ? "YES" : "NO");

    previousState = currentState;
  }

  // 기울어짐이면 삐삐삐 반복, 정상이면 무음
  updateBuzzerPattern();

  delay(20);
}
