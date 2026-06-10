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
│   ├── run.ps1                        # (Windows) outgoing COM 자동 탐지 후 브리지 실행
│   ├── connect_and_run.sh             # BT 풀 사이클 복구 + 브리지 실행 한 번에(껐다 켤 때마다 안전)
│   ├── RUNBOOK.md                     # 현장 운영자용 가이드(시작·복구 단계·금지사항)
│   ├── payload.json                   # 기준 변위 프로파일(피크 스케일의 모양 / GET 폴백용)
│   ├── get_example.py                 # 온사이트 API GET 디버그 예제(토큰은 placeholder)
│   ├── config.example.yaml            # 설정 템플릿
│   ├── config.yaml                    # 실제 설정(센서ID·bt_address·토큰) — 추적됨, push 주의
│   └── requirements.txt
└── docs/
    ├── wiring.md                      # 배선·핀맵·업로드·상태 판정 튜닝
    └── api-contract.md                # 온사이트 수집 API 명세 (확정)
```

## 신호 프로토콜 (블루투스 SPP, 줄단위 JSON)
ESP32는 줄 단위 JSON을 USB Serial과 블루투스로 동시에 출력한다. 브리지는 블루투스로 받는다.

| 종류 | 예시 | 브리지 처리 |
|------|------|------|
| 상태 변경 | `{"event":"STATE_CHANGED","state":"TILTED",...}` | 위험 주입(엣지 트리거: 정상→기울어짐 전이 1회만) |
| 상태 변경 | `{"event":"STATE_CHANGED","state":"NORMAL",...}` | 평시 복귀 |
| 연결 알림 | `{"event":"BT_CONNECTED","deviceId":"..."}` | 무시 |
| BT 제어 | `{"event":"BT_RESTART_REQUESTED"}` / `BT_PAIRING_RESET_REQUESTED` | 무시 |

`STATE_CHANGED` 전체 필드: `deviceId`, `deviceName`, `bluetoothName`,
`previousState`, `state`, `reason`, `roll`, `pitch`, `gyroZ`, `moving`.

> 브리지는 구형 `{"event":"DANGER"}` / `{"event":"NORMAL"}` 형식도 하위호환으로 받는다
> (`bridge.py`의 `event_to_action()`).

상태 전환은 **히스테리시스 + dwell(유지시간)**로 이중 안정화한다. `roll`이
`TILTED_ROLL_THRESHOLD`(-100°) 미만이면 기울어짐 후보, `NORMAL_ROLL_THRESHOLD`(-97°)
초과면 정상 후보, 그 사이는 직전 상태 유지(히스테리시스). 그리고 후보 상태가
`STATE_DWELL_MS`(**1초**) 이상 연속 유지돼야 전이를 확정해 `STATE_CHANGED`를 보낸다 —
1초 미만의 손떨림은 무시되어 이벤트가 폭주하지 않는다(경계에서 NORMAL↔TILTED 채터링 방지).
임계는 **장착 자세에 따라 달라진다**(현재 장착 기준 정상 roll ≈ -93, 기울어짐 ≈ -113).
펌웨어 상단 상수로 조정.

## 현장 UX (펌웨어)
- **상태 LED**(보드 내장): BT 대기=느린 점멸, 연결=ON 고정, 재시작 중=빠른 3회, 페어링 초기화 중=빠른 8회.
- **부저**: BT 연결 + 기울어짐 전이 시 장음(1200ms ON / 800ms OFF)을 **최대 5회** 울리고 멈춤. 정상 복귀 후 다시 기울어지면 5회 초기화. 그 외엔 정지.
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
  그 **직후** `bridge.py`가 포트(`/dev/cu.MIDAS_ONSITE_SENSOR`)를 열게 한다(갓 pair한 직후 open이 핵심).
  - macOS는 연결마다 포트 노드 끝에 `-1`/`-2` 접미사를 붙일 수 있다 — 브리지가 `serial.port`를
    **접두사**로 보고 매칭되는 실제 노드(가장 최근 생성)를 자동으로 골라 연다(정전·재페어 후에도 그대로).
    Windows의 `run.ps1`(MAC으로 outgoing COM 탐지)에 대응하는 macOS 쪽 자동탐지다.
  - `pair`가 `0x02 (No Connection)`로 실패해도 무시 — 곧이은 `connect`/브리지가 SPP를 살린다.
  - ⚠️ **브리지를 껐다 켤 때마다**(예: `--monitor`↔`--dry-run` 전환) SPP가 깨진다. 이때
    `blueutil --connect`(브리지 자동 재연결)만으로는 ACL은 붙어도 SPP가 안 붙어 포트는
    열려 "시리얼 연결:"까지만 찍히고 데이터가 조용히 안 온다. **매번 위 unpair→pair→connect
    풀 사이클을 다시 돌린 직후** 브리지를 열어야 안정적이다 → 이 절차를 한 번에 묶은
    **`bridge/connect_and_run.sh`** 를 쓰면 편하다(아래 3) 참고).
  - `config.yaml`의 `serial.bt_address`(ESP32 MAC)가 있으면 브리지가 포트 열기 전
    `blueutil --connect`로 무인 복구를 시도한다(전원만 껐다 켠 정도는 자동 회복).
  - ⚠️ 보드 버튼은 누르지 말 것(짧게=BT 재시작 / 길게=페어링 삭제 → 연결 깨짐).
- **Windows**: 블루투스는 반드시 **"나가는(outgoing)" COM 포트**를 열어야 ESP32 가 연결로 인식한다.
  ⚠️ 이 COM 번호는 **페어링/연결마다 Windows 가 다시 배정**해 자주 바뀐다(박아둔 번호로 열면
  `FileNotFoundError`). 그래서 번호를 직접 넣는 대신 **`bridge/run.ps1`** 을 쓰면 `config.yaml` 의
  `serial.bt_address`(ESP32 MAC)가 박힌 outgoing 포트를 **실행 직전에 자동 탐지**해 띄운다:
  ```powershell
  cd bridge
  .\run.ps1            # 실전(실제 POST).  --monitor / --check / --dry-run 인자 그대로 전달
  ```
  COM 번호가 또 바뀌어도 `.\run.ps1` 만 다시 실행하면 된다(스크립트가 `config.local.yaml` 을 자동 생성).

### 3) 브리지 실행
```bash
cd bridge
python3 -m venv .venv && source .venv/bin/activate   # (최초 1회)
pip install -r requirements.txt
# config.yaml 은 이미 채워져 추적된다(센서ID·bt_address·Bearer 토큰).
# ⚠️ `cp config.example.yaml config.yaml` 을 다시 실행하면 토큰이 <YOUR_TOKEN> placeholder 로
#    덮여 인증이 401(UNAUTHENTICATED)로 깨진다. 토큰 교체가 필요할 때만 config.yaml 을 직접 편집.

# ★ 권장: BT 풀 사이클 복구 + 브리지 실행을 한 번에 (껐다 켤 때마다 SPP 재확보)
./connect_and_run.sh            # 실전(실제 POST)
./connect_and_run.sh --monitor  # 블루투스 수신만(POST 없음)
./connect_and_run.sh --dry-run  # POST 없이 페이로드만
# 스크립트는 unpair 후 /dev/cu 포트 노드가 생길 때까지 기다린 뒤 연다("No such file" 크래시 방지).
# 안 붙거나 데이터가 안 오면 같은 명령 재실행 — 단계별 복구·금지사항은 bridge/RUNBOOK.md 참고.

# ── 또는 수동으로 직접(브리지를 껐다 켤 땐 위 풀 사이클을 먼저 돌릴 것) ──
python bridge.py --config config.yaml --dry-run            # API 없이 페이로드 미리보기
python bridge.py --config config.yaml --simulate --dry-run # 하드웨어 없이 키보드(d=위험, n=평시, q=종료)
python bridge.py --config config.yaml --monitor            # 블루투스 수신만(POST 없음)
python bridge.py --config config.yaml                      # 실전(실제 POST)
python bridge.py --config config.yaml --check              # 저장된 계측값 확인(인증 200 점검)
```
> 위험 시 보내는 변위의 **피크 랜덤 범위**(항상 3차=3mm 초과)는 `bridge/bridge.py` 상단
> `PEAK_DISPLACEMENT_MIN_MM` / `PEAK_DISPLACEMENT_MAX_MM` 상수로 조정한다. 기준 프로파일의
> 심도 그리드/모양은 **대상 센서에서 자동 GET**해 맞춘다(데이터 없으면 `payload.json` 폴백).

## 상태 — 데모 검증 완료 ✅
- [x] **펌웨어** — MPU6050 roll 감지 + BT(`STATE_CHANGED`) + 부저/버튼/상태 LED. 보드 플래시·동작 확인.
- [x] **블루투스 연결** — macOS `blueutil` 절차로 `BT_CONNECTED`·`STATE_CHANGED` 수신 검증.
- [x] **온사이트 API 연동** — 기울임 → 3차 초과 위험 프로파일 POST(200) → 대시보드 위험 전환 확인.
      평시값(1mm 미만)도 POST로 복귀 가능.
- [x] **상태 전환 안정화** — 펌웨어 dwell(후보 상태 1초 유지 후 전이 확정)로 손떨림 채터링 제거 + 브리지 엣지 래치(정상→기울어짐 1회만 POST)로 "기울임 1회 = POST 1회" 보장. 라이브 검증 완료.
- [x] **브리지 견고화** — API 오류·BT 끊김에도 죽지 않고 재연결(끊기면 `blueutil --connect`로 무인 복구 — `config.yaml`의 `bt_address`), 엣지 래치로 중복 POST 방지.

### 현장 적용 시 조정
- 모형 장착 자세에 맞춰 `esp32_inclinometer.ino`의 roll 임계(`TILTED/NORMAL_ROLL_THRESHOLD`) 튜닝.
- 위험 피크 범위(`bridge/bridge.py`의 `PEAK_DISPLACEMENT_MIN/MAX_MM`), 디바운스(`POST_MIN_INTERVAL_S`)는 데모 톤에 맞게.
- `config.yaml`에 대상 환경의 호스트·센서ID·Bearer 토큰 입력(데모 편의상 추적됨 — **원격 push 시 토큰 노출 주의**, push 전 토큰 제거/교체).
- 평시 복귀 동선(자동/수동) 결정.
