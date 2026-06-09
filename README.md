# ESP32 지중경사계 온사이트 시연

모형 벽을 손으로 기울이면 → ESP32+자이로가 감지 → **블루투스로 연결된 노트북**이
신호를 받아 **온사이트 계측 수집 API**로 "3차 관리기준 초과" 데이터를 주입 →
옆에 띄워둔 **기존 온사이트 대시보드**가 `평시 → 위험시`로 바뀌는 라이브 데모.

> 온사이트 서비스는 **AWS에서 운영**되며 계측센서 데이터 수집용 HTTP API가 열려 있다.
> 노트북 게이트웨이는 그 수집 API로 HTTP POST를 보낸다. (별도 신규 서버·대시보드 없음)

## 시연 시나리오
1. 평상시: 대시보드는 평시(정상 범위) 상태.
2. 진행자가 모형의 한쪽 벽을 기울인다(지중경사계가 변위된 상황 모사).
3. MPU6050이 기울기를 감지, roll 임계 초과가 히스테리시스를 통과하면 ESP32가
   `STATE_CHANGED`(state=`TILTED`) 이벤트를 블루투스로 송신.
4. 노트북의 브리지가 이를 받아 **3차 관리기준(누적 3mm) 초과 위험 프로파일**을 수집 API로 POST.
   (대상 센서의 심도 그리드를 GET해 맞추고, 피크 변위만 범위 내 랜덤 스케일)
5. 대시보드가 위험시로 전환. 벽을 다시 세우면 `NORMAL` 이벤트 수신(평시 복귀 데이터는 기본 미전송).

## 확정된 설계 결정
| 항목 | 결정 |
|------|------|
| 통신 | ESP32 → **블루투스(Classic SPP)** → 노트북 게이트웨이 → **온사이트 수집 API** |
| 서버 | 온사이트 서비스는 **AWS에서 운영**, 계측 수집용 HTTP API로 POST |
| 벽 작동 | **수동 기울임** + 자이로 감지 (서보·모터 제어 없음) |
| 하드웨어 | **ESP32 DevKit + MPU6050**(I2C) + 부저·버튼·상태 LED |
| 대시보드 | **기존 온사이트 대시보드 사용** — 신규 제작 없음 |

> 왜 노트북 브리지인가? 수집 API 호출에는 인증/CORS가 얽혀 브라우저 직결보다
> 노트북 측 호출이 견고하고, 계측 데이터 전송·API 호출 로직을 한 곳에 둘 수 있다.
> 블루투스는 ESP32↔노트북 1:1 연결이라 현장 와이파이에 의존하지 않아 데모 안정성이 높다.

## 데이터 흐름
```
 [모형 벽: 수동 기울임]
        │ (기울기 변화)
        ▼
   [MPU6050] ──I2C── [ESP32 DevKit] ── 부저 / 버튼 / 상태 LED
                          │  Bluetooth SPP (줄단위 JSON)
                          │  {"event":"STATE_CHANGED","state":"TILTED",...}
                          ▼
                  [노트북: bridge.py]   ← 블루투스 포트를 시리얼처럼 연다
                          │  HTTP POST (피크 랜덤 위험 프로파일, 3차 초과)
                          ▼
              [온사이트 계측 수집 API]   ← AWS에서 운영
                          │
                          ▼
            [기존 온사이트 웹 대시보드]   평시 → 위험시
```

## 폴더 구조
```
esp32-inclinometer-demo/
├── README.md                          # 이 문서 (전략·아키텍처·실행법)
├── firmware/
│   └── esp32_inclinometer/
│       └── esp32_inclinometer.ino     # MPU6050 roll 감지 + 블루투스 + 부저/버튼/LED
├── bridge/
│   ├── bridge.py                      # BT(시리얼) 수신 → 위험 프로파일 POST (랜덤 피크·자동GET·에러 견고)
│   ├── payload.json                   # 기준 변위 프로파일(피크 스케일의 모양 / GET 폴백용)
│   ├── get_example.py                 # 온사이트 API GET 디버그 예제(토큰은 placeholder)
│   ├── config.example.yaml            # 설정 템플릿 (복사해서 config.yaml)
│   └── requirements.txt
└── docs/
    ├── wiring.md                      # 배선·핀맵·업로드·상태 판정 튜닝
    └── api-contract.md                # 온사이트 수집 API 명세 (확정)
```

## 신호 프로토콜 (블루투스 SPP, 줄단위 JSON)
ESP32는 줄 단위 JSON을 USB Serial과 블루투스로 동시에 출력한다. 브리지는 블루투스로 받는다.

| 종류 | 예시 | 브리지 처리 |
|------|------|------|
| 상태 변경 | `{"event":"STATE_CHANGED","state":"TILTED",...}` | 위험 주입 |
| 상태 변경 | `{"event":"STATE_CHANGED","state":"NORMAL",...}` | 평시 복귀 |
| 연결 알림 | `{"event":"BT_CONNECTED","deviceId":"..."}` | 무시 |
| BT 제어 | `{"event":"BT_RESTART_REQUESTED"}` / `BT_PAIRING_RESET_REQUESTED` | 무시 |

`STATE_CHANGED` 전체 필드: `deviceId`, `deviceName`, `bluetoothName`,
`previousState`, `state`, `reason`, `roll`, `pitch`, `gyroZ`, `moving`.

> 브리지는 구형 `{"event":"DANGER"}` / `{"event":"NORMAL"}` 형식도 하위호환으로 받는다
> (`bridge.py`의 `event_to_action()`).

상태 전환은 히스테리시스로 안정화: `roll`이 `TILTED_ROLL_THRESHOLD`(-100°) 미만이면
기울어짐, `NORMAL_ROLL_THRESHOLD`(-97°) 초과면 정상, 그 사이는 직전 상태 유지.
임계는 **장착 자세에 따라 달라진다**(현재 장착 기준 정상 roll ≈ -93, 기울어짐 ≈ -113).
펌웨어 상단 상수로 조정.

## 현장 UX (펌웨어)
- **상태 LED**(보드 내장): BT 대기=느린 점멸, 연결=ON 고정, 재시작 중=빠른 3회, 페어링 초기화 중=빠른 8회.
- **부저**: BT 연결 + 기울어짐일 때만 장음(1200ms ON / 800ms OFF). 그 외엔 정지.
- **버튼**: 짧게 누름=BT 재시작 / 2초 이상 길게=ESP32 본딩(페어링) 삭제 후 재시작. (BT 미연결에도 동작)
- BT가 연결돼 있지 않으면 센서·부저는 정지하고 버튼·LED만 동작한다.

## 실행 방법

### 1) 펌웨어 업로드
- `docs/wiring.md` 따라 배선 후 Arduino IDE로 `esp32_inclinometer.ino` 업로드.
- 시리얼 모니터(115200)에서 부팅 배너를 확인. **단, 센서·이벤트는 블루투스 클라이언트가
  연결돼야 동작**하므로, 연결 전에는 `[SYSTEM]` 안내와 LED 느린 점멸만 보인다.

### 2) 블루투스 페어링
- 노트북 BT 설정에서 `MIDAS_ONSITE_SENSOR` 페어링.
- ★ 페어링만으로는 부족하다 — 노트북이 **나가는(outgoing) 포트**를 열어야 ESP32가
  연결로 인식(LED ON 고정)한다. 아래 `bridge.py`가 그 포트를 연다.
- **macOS**: 시스템설정의 수동 "연결"은 SPP 채널이 안 열려 실패하기 쉽다. `blueutil`이 안정적이다:
  ```bash
  brew install blueutil
  blueutil --paired                       # MIDAS_ONSITE_SENSOR 의 address 확인
  ADDR=70:4B:CA:6F:5D:4A                   # ← 위에서 확인한 주소로 교체
  blueutil --unpair $ADDR; blueutil --pair $ADDR; blueutil --connect $ADDR
  ```
  그 직후 `bridge.py`가 포트(`/dev/cu.MIDAS_ONSITE_SENSOR`)를 열게 한다.
  끊겨서 재연결할 때도 unpair→pair→connect 전체를 다시 돌려야 안정적이다.
  ⚠️ 보드 버튼은 누르지 말 것(짧게=BT 재시작 / 길게=페어링 삭제 → 연결 깨짐).
- **Windows**: 장치관리자에서 "나가는(outgoing)" COM 포트를 확인해 `config.yaml`의 `serial.port`에 넣는다.

### 3) 브리지 실행
```bash
cd bridge
python3 -m venv .venv && source .venv/bin/activate   # (선택)
pip install -r requirements.txt
cp config.example.yaml config.yaml   # serial.port(BT), api.url(센서ID), Bearer 토큰 채우기

# API 없이 페이로드 미리보기 (대상 센서 GET → 피크 랜덤 스케일)
python bridge.py --config config.yaml --dry-run

# 하드웨어 없이 키보드로 흐름 테스트 (d=위험, n=평시, q=종료)
python bridge.py --config config.yaml --simulate --dry-run

# 블루투스 수신만 확인(POST 없음): 기울이면 STATE_CHANGED 가 찍힌다
python bridge.py --config config.yaml --monitor

# 실전: 블루투스 연결 + 기울이면 실제 API POST(위험 프로파일)
python bridge.py --config config.yaml

# 저장된 계측값 확인
python bridge.py --config config.yaml --check
```
> 위험 시 보내는 변위의 **피크 랜덤 범위**(항상 3차=3mm 초과)는 `bridge/bridge.py` 상단
> `PEAK_DISPLACEMENT_MIN_MM` / `PEAK_DISPLACEMENT_MAX_MM` 상수로 조정한다. 기준 프로파일의
> 심도 그리드/모양은 **대상 센서에서 자동 GET**해 맞춘다(데이터 없으면 `payload.json` 폴백).

## 상태 — 데모 검증 완료 ✅
- [x] **펌웨어** — MPU6050 roll 감지 + BT(`STATE_CHANGED`) + 부저/버튼/상태 LED. 보드 플래시·동작 확인.
- [x] **블루투스 연결** — macOS `blueutil` 절차로 `BT_CONNECTED`·`STATE_CHANGED` 수신 검증.
- [x] **온사이트 API 연동** — 기울임 → 3차 초과 위험 프로파일 POST(200) → 대시보드 위험 전환 확인.
      평시값(1mm 미만)도 POST로 복귀 가능.
- [x] **브리지 견고화** — API 오류·BT 끊김에도 죽지 않고 재연결, `DANGER` 디바운스로 중복 POST 방지.

### 현장 적용 시 조정
- 모형 장착 자세에 맞춰 `esp32_inclinometer.ino`의 roll 임계(`TILTED/NORMAL_ROLL_THRESHOLD`) 튜닝.
- 위험 피크 범위(`bridge/bridge.py`의 `PEAK_DISPLACEMENT_MIN/MAX_MM`), 디바운스(`POST_MIN_INTERVAL_S`)는 데모 톤에 맞게.
- `config.yaml`에 대상 환경의 호스트·센서ID·Bearer 토큰 입력(토큰은 커밋 금지).
- 평시 복귀 동선(자동/수동) 결정.
