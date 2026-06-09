#include <Wire.h>
#include <math.h>

#define MPU_ADDR 0x68

#define REG_PWR_MGMT_1 0x6B
#define REG_ACCEL_XOUT_H 0x3B
#define REG_GYRO_XOUT_H  0x43
#define REG_WHO_AM_I     0x75

// 기본 스케일 가정
// Accelerometer ±2g: 16384 LSB/g
// Gyroscope ±250 deg/s: 131 LSB/(deg/s)
const float ACCEL_SCALE = 16384.0;
const float GYRO_SCALE = 131.0;

int16_t read16(uint8_t reg) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);

  Wire.requestFrom(MPU_ADDR, 2);

  if (Wire.available() < 2) {
    return 0;
  }

  int16_t value = (Wire.read() << 8) | Wire.read();
  return value;
}

void setup() {
  Serial.begin(115200);
  delay(2000);

  Wire.begin(21, 22);      // SDA = D21, SCL = D22
  Wire.setClock(100000);

  Serial.println();
  Serial.println("MPU raw to angle test");

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
    Serial.println("Sensor wake up success");
  } else {
    Serial.print("Sensor wake up failed. I2C error: ");
    Serial.println(error);
  }

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

  // 가속도 기반 기울기 계산
  float roll  = atan2(ay, az) * 180.0 / PI;
  float pitch = atan2(-ax, sqrt(ay * ay + az * az)) * 180.0 / PI;

  Serial.print("Accel(g) X:");
  Serial.print(ax, 3);
  Serial.print(" Y:");
  Serial.print(ay, 3);
  Serial.print(" Z:");
  Serial.print(az, 3);

  Serial.print(" || Gyro(deg/s) X:");
  Serial.print(gx, 2);
  Serial.print(" Y:");
  Serial.print(gy, 2);
  Serial.print(" Z:");
  Serial.print(gz, 2);

  Serial.print(" || Roll:");
  Serial.print(roll, 1);
  Serial.print(" Pitch:");
  Serial.print(pitch, 1);

  Serial.println();

  delay(300);
}
