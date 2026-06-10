# 배선 & 펌웨어 업로드 가이드

## 핀 매핑 (펌웨어 `#define` 기준)

| 구성요소 | ESP32 핀 | 펌웨어 상수 | 비고 |
|----------|----------|-------------|------|
| MPU6050 SDA | GPIO21 | `SDA_PIN` | I2C 데이터 |
| MPU6050 SCL | GPIO22 | `SCL_PIN` | I2C 클럭 (50kHz) |
| 부저 + / S/IN | GPIO18 | `BUZZER_PIN` | 기울어짐 경고음 |
| 버튼 | GPIO23 | `BUTTON_PIN` | `INPUT_PULLUP` (눌림=LOW) |
| 상태 LED | GPIO2 | `STATUS_LED_PIN` | 보드 내장 LED |

## ESP32 DevKit ↔ MPU6050 (I2C)

| MPU6050 | ESP32 DevKit | 비고 |
|---------|--------------|------|
| VCC     | 3V3          | 5V 아님 주의 |
| GND     | GND          | |
| SDA     | GPIO21       | |
| SCL     | GPIO22       | |
| AD0     | GND          | I2C 주소 0x68 (3V3 연결 시 0x69) |
| XCL/XDA/INT | 미연결    | 사용 안 함 |

- 점퍼선을 길게(예: 50cm) 쓰면 I2C가 불안정해질 수 있어 펌웨어 I2C 클럭을 **50kHz**로 낮춰 둠(`Wire.setClock`).
- `WHO_AM_I`(0x75)는 부팅 시 로그로 출력만 한다(검증엔 사용 안 함). 일부 모듈은 `0x72`가 나오기도 하며 동작엔 무관.
- 모듈 핀이 안 보이면 I2C 스캐너로 주소(0x68/0x69)부터 확인.
- MPU6050은 **모형 벽에 단단히 고정**해야 함. 흔들리면 노이즈로 오탐 발생.

## 부저 / 버튼 / 상태 LED

- **부저**: `+`(또는 `S/IN`) → GPIO18, `-` → GND. 자체 발진하는 **능동 부저** 기준(`digitalWrite` HIGH/LOW로 on/off).
- **버튼**: 한쪽 → GPIO23, 다른 쪽 → GND. `INPUT_PULLUP`이라 외부 풀업저항 불필요(안 누름=HIGH, 눌림=LOW).
- **상태 LED**: 보드 내장 LED(GPIO2) 사용 — 추가 배선 없음.

### (참고) 브레드보드 J열 배선 예
ESP32를 브레드보드 I열에 꽂고 같은 줄의 J열을 외부 연결 포인트로 쓴 현장 배선:

| 신호 | ESP32 핀 | 연결 포인트 |
|------|----------|-------------|
| 3V3  | —        | J,-2 (+레일) |
| GND  | —        | J,-1 (-레일) |
| SDA  | GPIO21   | J,8 |
| SCL  | GPIO22   | J,11 |
| 부저 | GPIO18   | J,6 |
| 버튼 | GPIO23   | J,12 |

## Arduino IDE 업로드

1. **보드 매니저**: `esp32` (Espressif Systems) 설치
2. **보드 선택**: "ESP32 Dev Module" (대부분 DevKitC 호환)
3. **포트 선택**: 연결 후 나타나는 포트
   - macOS: `/dev/cu.usbserial-*` 또는 `/dev/cu.SLAB_USBtoUART` (CP210x 드라이버 필요할 수 있음)
   - Windows: 장치관리자의 `COM*`
4. `firmware/esp32_inclinometer/esp32_inclinometer.ino` 업로드.
   - `BluetoothSerial`은 ESP32 코어 내장이라 **추가 라이브러리 설치 불필요**.
   - 블루투스를 포함해 스케치가 크다. 업로드가 실패하면(`chip stopped responding` 등)
     업로드 속도를 115200으로 낮추고, 부저/버튼/센서를 잠시 떼어 ESP32 단독으로 올린 뒤 재연결.
5. **시리얼 모니터 115200**으로 부팅 배너 확인:
   - `MIDAS ONSITE SENSOR START` / `[MPU] ...` / `[BT] Started successfully` / `[SYSTEM] Ready`
   - **주의**: 센서·부저·이벤트는 **블루투스 클라이언트가 연결돼야 동작**한다.
     연결 전에는 `[SYSTEM]` 안내와 LED 느린 점멸만 보인다.
   - 노트북에서 `MIDAS_ONSITE_SENSOR` 페어링 후 **나가는(outgoing) 포트**를 열면
     (`bridge.py` 실행) `[BT] Client connected`가 뜨고, 그때부터 기울이면 `STATE_CHANGED` 출력.

## 블루투스 페어링 메모

- 페어링 ≠ 데이터 연결. Windows에서 페어링을 끝내도, 노트북이 **나가는 COM 포트**를
  열기 전까지 ESP32는 클라이언트를 인식하지 못한다(LED가 계속 점멸).
- 연결이 꼬이면 버튼으로 복구: 짧게=BT 재시작, 2초 이상 길게=ESP32 본딩 삭제 후 재시작.
- 그래도 안 되면 Windows 블루투스 설정에서 `MIDAS_ONSITE_SENSOR`를 제거하고 다시 페어링.

## 상태 판정 / 부저 튜닝 (`esp32_inclinometer.ino` 상단 상수)

- `TILTED_ROLL_THRESHOLD` (기본 **-100.0**): roll이 이 값 미만이면 기울어짐(위험)
- `NORMAL_ROLL_THRESHOLD` (기본 **-97.0**): roll이 이 값 초과면 정상 복귀
- 두 값 사이 구간에서는 직전 상태 유지(히스테리시스).
- `STATE_DWELL_MS` (기본 **1000**): 후보 상태가 이 시간(ms) 이상 연속 유지돼야 전이 확정. 1초 미만 떨림은 무시 → `STATE_CHANGED` 폭주 방지. 데모 반응이 굼뜨면 600~800으로 낮춘다.
- 임계는 **장착 자세에 따라 달라진다**(현재 장착 기준 정상 roll ≈ -93, 기울어짐 ≈ -113). 실 장착 후 측정해 보정.
- `MOVING_GYRO_THRESHOLD` (기본 5.0): 이벤트의 `moving` 판정 기준(deg/s).
- `BEEP_ON_MS`(1200) / `BEEP_OFF_MS`(800): 기울어짐 경고음 ON/OFF 길이. `MAX_BEEPS`(5): 기울어질 때마다 최대 울림 횟수(5회 후 멈춤, 정상 복귀 시 초기화).
- `DEBOUNCE_MS`(40) / `LONG_PRESS_MS`(2000): 버튼 디바운스·길게누름 기준.
