# 배선 & 펌웨어 업로드 가이드

## ESP32 DevKit ↔ MPU6050 (I2C)

| MPU6050 | ESP32 DevKit | 비고 |
|---------|--------------|------|
| VCC     | 3V3          | 5V 아님 주의 |
| GND     | GND          | |
| SDA     | GPIO21       | 펌웨어 `SDA_PIN` |
| SCL     | GPIO22       | 펌웨어 `SCL_PIN` |
| AD0     | GND          | I2C 주소 0x68 (3V3 연결 시 0x69) |
| XCL/XDA/INT | 미연결    | 사용 안 함 |

- 모듈 핀이 안 보이면 `Wire.begin()` 후 I2C 스캐너로 주소(0x68/0x69) 먼저 확인.
- MPU6050은 **모형 벽에 단단히 고정**해야 함. 흔들리면 노이즈로 오탐 발생.

## Arduino IDE 업로드

1. **보드 매니저**: `esp32` (Espressif Systems) 설치
2. **보드 선택**: "ESP32 Dev Module" (대부분 DevKitC 호환)
3. **포트 선택**: 연결 후 나타나는 포트
   - macOS: `/dev/cu.usbserial-*` 또는 `/dev/cu.SLAB_USBtoUART` (CP210x 드라이버 필요할 수 있음)
   - Windows: 장치관리자의 `COM*`
4. `firmware/esp32_inclinometer/esp32_inclinometer.ino` 업로드
5. **시리얼 모니터 115200**으로 열어 JSON 출력 확인:
   - 부팅 시 `{"event":"BASELINE_SET"}`
   - 평시 텔레메트리 `{"t":...,"angle":1.x,"state":"NORMAL"}`
   - 벽을 5° 이상 기울이면 `{"event":"DANGER","angle":...}`

> 라이브러리 의존성 없음(Wire 직접 사용). Adafruit MPU6050 라이브러리로 바꾸고 싶으면
> `readAccel()`만 라이브러리 호출로 교체하면 됨.

## 영점(baseline) 재설정
- 부팅 시 자동으로 현재 자세를 평지(0°)로 캡처.
- 시연 중 다시 잡으려면 시리얼 모니터에서 `z` 전송.

## 임계값 튜닝 (`esp32_inclinometer.ino`)
- `TRIGGER_DEG` (기본 5°): 위험 판정 각도
- `RESET_DEG` (기본 2°): 평시 복귀 각도
- `SUSTAIN_MS` (기본 400ms): 채터링 방지 유지 시간
