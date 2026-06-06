# ESP32 지중경사계 온사이트 시연

모형 벽을 손으로 기울이면 → ESP32+자이로가 감지 → 컴퓨터가 신호를 받아
**온사이트 계측 API**로 "3차 관리기준 초과" 데이터를 주입 → 옆에 띄워둔
**기존 온사이트 대시보드**가 `평시 → 위험시`로 바뀌는 라이브 데모.

## 시연 시나리오
1. 평상시: 대시보드는 평시(정상 범위) 상태.
2. 진행자가 모형의 한쪽 벽을 기울인다(지중경사계가 변위된 상황 모사).
3. MPU6050이 기울기를 감지, 임계각 초과가 잠깐 지속되면 ESP32가 `DANGER` 신호 송신.
4. 컴퓨터의 브리지가 신호를 받아 3차 기준을 초과하는 랜덤 계측값을 API로 전송.
5. 대시보드가 위험시로 전환. 벽을 다시 세우면 `NORMAL` → 평시로 복귀(옵션).

## 확정된 설계 결정
| 항목 | 결정 |
|------|------|
| 통신 | ESP32 → **USB 시리얼** → 컴퓨터 브리지 → **온사이트 API**(기존) |
| 벽 작동 | **수동 기울임** + 자이로 감지 (서보·버튼 제어 없음) |
| 하드웨어 | **ESP32 DevKit + MPU6050** (I2C, GPIO21/22) |
| 대시보드 | **기존 온사이트 대시보드 사용** — 신규 제작 없음 |

> 왜 컴퓨터 브리지인가? 온사이트 API 호출에는 인증/CORS가 얽혀 브라우저 직결보다
> 서버 측 호출이 견고하고, 랜덤 데이터 생성·관리기준 로직을 한 곳에 둘 수 있다.
> USB 시리얼은 현장 와이파이에 의존하지 않아 데모 안정성이 가장 높다.

## 데이터 흐름
```
 [모형 벽: 수동 기울임]
        │ (기울기 변화)
        ▼
   [MPU6050] ──I2C── [ESP32 DevKit]
                          │  USB Serial (줄단위 JSON, 115200)
                          │  {"event":"DANGER","angle":7.8}
                          ▼
                  [컴퓨터: bridge.py]
                          │  HTTP POST (3차 초과 랜덤 계측값)
                          ▼
                 [온사이트 계측 API]  ← 기존 시스템
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
│       └── esp32_inclinometer.ino     # MPU6050 기울기 감지 + 시리얼 신호 (의존성 없음)
├── bridge/
│   ├── bridge.py                      # 시리얼 수신 → 온사이트 API 호출
│   ├── config.example.yaml            # 설정 템플릿 (복사해서 config.yaml)
│   └── requirements.txt
└── docs/
    ├── wiring.md                      # 배선·핀맵·업로드·임계값 튜닝
    └── api-contract.md                # ★ 온사이트 API 명세 (채워야 함)
```

## 신호 프로토콜 (시리얼, 줄단위 JSON)
| 종류 | 예시 | 의미 |
|------|------|------|
| 이벤트 | `{"event":"DANGER","angle":7.8}` | 임계 초과 → 위험 주입 |
| 이벤트 | `{"event":"NORMAL","angle":1.2}` | 평시 복귀 |
| 텔레메트리 | `{"t":12345,"angle":3.2,"state":"NORMAL"}` | 디버그용(브리지 무시) |
| 부팅 | `{"event":"BASELINE_SET"}` | 영점 캡처 완료 |

상태 전환은 히스테리시스로 안정화: `TRIGGER_DEG`(5°) 초과가 `SUSTAIN_MS`(400ms)
지속되면 DANGER, `RESET_DEG`(2°) 미만이 지속되면 NORMAL. (펌웨어 상단 상수로 조정)

## 실행 방법

### 1) 펌웨어 업로드
- `docs/wiring.md` 따라 배선 후 Arduino IDE로 `esp32_inclinometer.ino` 업로드.
- 시리얼 모니터(115200)에서 기울일 때 `DANGER` 이벤트가 뜨는지 먼저 확인.

### 2) 브리지 실행
```bash
cd bridge
python3 -m venv .venv && source .venv/bin/activate   # (선택)
pip install -r requirements.txt
cp config.example.yaml config.yaml                   # 값 채우기 (시리얼 포트, API)

# API 없이 페이로드 형식만 확인
python bridge.py --config config.yaml --dry-run

# ESP32 없이 키보드로 흐름 테스트 (d=위험, n=평시, q=종료)
python bridge.py --config config.yaml --simulate --dry-run

# 실전: ESP32 연결 + 실제 API 전송
python bridge.py --config config.yaml
```

## 남은 작업 / 필요한 정보
- [ ] **온사이트 API 명세 확정** — `docs/api-contract.md`의 체크리스트.
      (엔드포인트/인증/페이로드 스키마, 위험 판정이 서버측인지 우리가 level을 보내는지,
      단일 포인트 vs 시계열, 평시 복귀 방법, 실제 1/2/3차 관리기준값)
- [ ] 확정 후 `config.yaml` + `build_payload()` 정합.
- [ ] 실 하드웨어로 임계각/유지시간 튜닝, 모형에 MPU6050 견고 고정.
- [ ] (선택) 위험 후 자동/수동 복귀 동선 결정, 리허설.

## 마일스톤
1. **HW 검증** — 배선 후 시리얼에서 기울기 각도/이벤트 확인 *(코드 준비됨)*
2. **API 연동** — 명세 받아 `--dry-run`으로 페이로드 맞춤 → 실전송
3. **통합 리허설** — 벽 기울임→대시보드 위험 전환 end-to-end, 임계값 튜닝
4. **현장 시연** — 복귀 동선 포함 최종 점검
