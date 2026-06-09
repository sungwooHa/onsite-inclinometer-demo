# experiments — 개발 중 테스트/실험 스케치 보관소

실제 시연에 쓰는 **최종 펌웨어는 상위 폴더 `firmware/esp32_inclinometer/`** 다.
여기 있는 건 그 과정에서 만든 테스트·실험 스케치이며 **시연에 사용하지 않는다.**

| 폴더 | 내용 | 비고 |
|------|------|------|
| `esp32_bluetooth/sketch_jun7a/` | 블루투스 버전 작업본 | 최종(`esp32_inclinometer`)과 **내용 동일**한 Arduino IDE 원본 작업폴더(6/7). 사실상 중복본 |
| `esp32_sensor_test/` | MPU6050 센서 점검(WHO_AM_I·원시값 출력) | 배선/센서 동작 확인용 |
| `esp32_tilt_buzzer/` | 기울기 감지 + 부저 알림 샘플 | JSON 프로토콜 아님, 사람이 읽는 로그만 |
