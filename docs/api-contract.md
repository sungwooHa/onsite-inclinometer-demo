# 온사이트 계측 API 연동 명세 (확정)

브리지(`bridge/bridge.py`)가 DANGER 신호를 받으면 이 API로 심도별 변위 프로파일을
업로드한다. 아래는 실제 QA 예제 코드(`inclinometer_post.py` / `inclinometer_get.py`)에서
확정한 명세다.

## 1. 엔드포인트
- URL: `https://api.onsite.kr-qa-midasit.com/inclinometer/sensor/{sensor_id}`
  - 센서ID(`2100`)는 **URL 경로**에 들어간다(본문 아님).
- 메서드: `POST` = 계측값 업로드, `GET` = 조회
- 인증: `Authorization: Bearer <JWT>` (RS512, `sub=131` 계정)
  - 토큰은 `bridge/config.yaml`(gitignore)에만 둔다. **절대 커밋 금지.**

## 2. POST 본문 스키마 (JSON)
```json
{
  "measurement_date": "2025-04-05T00:00:00",
  "unit": {"depth": "mm", "displacement": "mm"},
  "sensor_data": [
    {"depth": 0,     "displacement": -0.08},
    {"depth": 500,   "displacement": 1.68},
    {"depth": 40000, "displacement": 0}
  ]
}
```
- `measurement_date`: ISO8601, **타임존 표기 없음**(예제는 `...T00:00:00`).
  브리지는 보낼 때 이 값만 현재 시각으로 갱신한다.
  - ⚠️ **단조증가 필수.** 이 날짜는 해당 센서의 **기존 최신 측정보다 반드시 더 나중**이어야 한다.
    같거나 이전 날짜로 POST 하면 서버가 (409 가 아니라) **`500 SYSTEM.UNEXPECTED`** 를 낸다.
    그래서 `post_example.py` 는 전송 직전 최신 `measurementTime` 을 GET 해 그보다 1초 뒤(또는 현재 시각 중
    더 나중)로 맞춘다. 미래 날짜를 한 번 넣으면 실제 시각이 그날을 지날 때까지 `now()` 전송이 막히니 주의.
- `sensor_data`: 심도(`depth`)–변위(`displacement`) 쌍의 배열.
  예제는 심도 0~40000mm, 500mm 간격(81점).

## 3. 위험 판정 위치 → (A) 서버측
본문에 `level`/`status`/`danger` 필드가 **없다.** 우리는 변위 프로파일만 보내고,
서버/대시보드가 관리기준과 비교해 위험을 띄운다.

## 4. 데이터 전송 방식 (이번 구현)
- DANGER 수신 시 **위험 프로파일을 POST**한다. 기준 프로파일의 *모양*은 유지하고
  **피크(최대 |변위|)만 랜덤 스케일**한다 → 매 전송마다 값이 조금씩 다르되 항상 3차(3mm) 초과.
  - 기준 프로파일: **대상 센서의 최신 측정을 GET**해 그 심도 그리드/모양을 자동으로 쓴다
    (`fetch_latest_profile`). 센서에 데이터가 없거나 GET 실패 시 번들 `bridge/payload.json`(81점)로 폴백.
  - 랜덤 피크 범위는 `bridge/bridge.py` 상단 `PEAK_DISPLACEMENT_MIN_MM`/`MAX_MM` 상수(기본 3.5~6.0mm).
  - `measurement_date` 는 전송 시각으로 갱신.
- 위험 판정 위치는 여전히 서버측: 우리는 변위 프로파일만 보내고 서버/대시보드가
  관리기준(누적 1/2/3mm)과 비교해 위험을 띄운다.

## 5. 검증 (GET)
`python bridge.py --config config.yaml --check` → 현재 저장된 계측값을 조회해 출력
(예제 `inclinometer_get.py` 와 동일 요청. 빠른 연결 점검은 `bridge/get_example.py`).

> **읽기↔쓰기 스키마 비대칭(주의).** GET 응답은
> `{ "results": [ { "measurementTime": "...", "data": [ {"depth","displacement"} ], "isReference", "isValid" } ], "page", ... }`
> 로, POST 본문의 `measurement_date`/`sensor_data` 와 **필드명이 다르다**. 같은 데이터인데 이름만 다른 것이니
> "포맷이 깨졌다"고 오해하지 말 것. 전송은 §2 본문 스키마 그대로 쓰면 200(검증 완료).

## 6. 확정된 운영 결정
- **평시 복귀**: 브리지는 NORMAL 이벤트를 무시한다. 평시 복귀는 **프로젝트에서 자체 처리**.
- **measurement_date**: 매 전송마다 **현재 시각**(`YYYY-MM-DDTHH:MM:SS`)으로 갱신 →
  같은 날 반복 전송해도 항상 최신값이라 서버가 최신 위험으로 인식.
