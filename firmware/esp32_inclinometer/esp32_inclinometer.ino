/*
 * ESP32 + MPU6050 — 지중경사계(Inclinometer) 시연 펌웨어
 *
 * 동작:
 *  - 모형 벽에 부착된 MPU6050로 "baseline(영점) 대비 기울기 각도"를 측정
 *  - 임계각 초과가 SUSTAIN_MS 이상 지속되면 시리얼로 DANGER 이벤트 전송
 *  - 다시 RESET_DEG 미만으로 복귀하면 NORMAL 이벤트 전송
 *  - 외부 라이브러리 의존성 없음 (Wire I2C 레지스터 직접 접근)
 *
 * 배선 (ESP32 DevKit <-> MPU6050):
 *  3V3 -> VCC,  GND -> GND,  GPIO21 -> SDA,  GPIO22 -> SCL,  AD0 -> GND(주소 0x68)
 *
 * 시리얼: 115200 baud, 줄 단위 JSON
 *  텔레메트리: {"t":12345,"angle":3.2,"state":"NORMAL"}   (디버그용, 브리지는 무시)
 *  이벤트    : {"event":"DANGER","angle":7.8}
 *              {"event":"NORMAL","angle":1.2}
 *  명령(수신): 'z' 또는 'Z' = baseline 재설정(영점 재캡처)
 *
 * 기울기 계산:
 *  부착 방향에 무관하도록, 부팅 시 중력벡터를 baseline으로 캡처하고
 *  현재 중력벡터와 baseline 사이의 "사잇각"을 기울기로 사용한다.
 */

#include <Wire.h>
#include <math.h>

// ---- MPU6050 레지스터 ----
static const uint8_t MPU_ADDR        = 0x68;
static const uint8_t REG_PWR_MGMT_1  = 0x6B;
static const uint8_t REG_ACCEL_XOUT_H = 0x3B;
static const float   ACCEL_SENS      = 16384.0f; // ±2g 기본, LSB/g

// ---- 핀 ----
static const int SDA_PIN = 21;
static const int SCL_PIN = 22;

// ---- 임계/히스테리시스 (도 단위) — 시연 환경에 맞게 조정 ----
static const float TRIGGER_DEG = 5.0f;          // 이 각도 이상이면 위험 후보
static const float RESET_DEG   = 2.0f;          // 이 각도 미만이면 평시 복귀
static const unsigned long SUSTAIN_MS   = 400;  // 상태 유지 시간(채터링 방지)
static const unsigned long TELEMETRY_MS = 200;  // 텔레메트리 출력 주기

// ---- baseline 중력벡터(단위벡터) ----
float bx = 0, by = 0, bz = 1;

bool danger = false;
unsigned long aboveSince = 0, belowSince = 0, lastTelem = 0;

void mpuWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

bool readAccel(float &ax, float &ay, float &az) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(REG_ACCEL_XOUT_H);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)MPU_ADDR, 6) != 6) return false;
  int16_t rx = (Wire.read() << 8) | Wire.read();
  int16_t ry = (Wire.read() << 8) | Wire.read();
  int16_t rz = (Wire.read() << 8) | Wire.read();
  ax = rx / ACCEL_SENS;
  ay = ry / ACCEL_SENS;
  az = rz / ACCEL_SENS;
  return true;
}

void captureBaseline() {
  float sx = 0, sy = 0, sz = 0;
  int n = 0;
  for (int i = 0; i < 200; i++) {
    float ax, ay, az;
    if (readAccel(ax, ay, az)) { sx += ax; sy += ay; sz += az; n++; }
    delay(5);
  }
  if (n > 0) {
    bx = sx / n; by = sy / n; bz = sz / n;
    float norm = sqrt(bx * bx + by * by + bz * bz);
    if (norm > 0) { bx /= norm; by /= norm; bz /= norm; }
  }
  Serial.println("{\"event\":\"BASELINE_SET\"}");
}

float tiltDegrees(float ax, float ay, float az) {
  float norm = sqrt(ax * ax + ay * ay + az * az);
  if (norm <= 0) return 0;
  float ux = ax / norm, uy = ay / norm, uz = az / norm;
  float dot = ux * bx + uy * by + uz * bz;
  if (dot > 1) dot = 1;
  if (dot < -1) dot = -1;
  return acos(dot) * 180.0 / PI;
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);
  mpuWrite(REG_PWR_MGMT_1, 0x00); // 슬립 해제
  delay(100);
  captureBaseline();
}

void loop() {
  // 시리얼 명령 처리 (영점 재설정)
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'z' || c == 'Z') captureBaseline();
  }

  float ax, ay, az;
  if (!readAccel(ax, ay, az)) { delay(20); return; }

  float angle = tiltDegrees(ax, ay, az);
  unsigned long now = millis();

  if (!danger) {
    if (angle >= TRIGGER_DEG) {
      if (aboveSince == 0) aboveSince = now;
      if (now - aboveSince >= SUSTAIN_MS) {
        danger = true; belowSince = 0;
        Serial.print("{\"event\":\"DANGER\",\"angle\":");
        Serial.print(angle, 1);
        Serial.println("}");
      }
    } else {
      aboveSince = 0;
    }
  } else {
    if (angle <= RESET_DEG) {
      if (belowSince == 0) belowSince = now;
      if (now - belowSince >= SUSTAIN_MS) {
        danger = false; aboveSince = 0;
        Serial.print("{\"event\":\"NORMAL\",\"angle\":");
        Serial.print(angle, 1);
        Serial.println("}");
      }
    } else {
      belowSince = 0;
    }
  }

  // 텔레메트리(디버그)
  if (now - lastTelem >= TELEMETRY_MS) {
    lastTelem = now;
    Serial.print("{\"t\":");      Serial.print(now);
    Serial.print(",\"angle\":");  Serial.print(angle, 1);
    Serial.print(",\"state\":\""); Serial.print(danger ? "DANGER" : "NORMAL");
    Serial.println("\"}");
  }

  delay(10);
}
