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
- `sensor_data`: 심도(`depth`)–변위(`displacement`) 쌍의 배열.
  예제는 심도 0~40000mm, 500mm 간격(81점).

## 3. 위험 판정 위치 → (A) 서버측
본문에 `level`/`status`/`danger` 필드가 **없다.** 우리는 변위 프로파일만 보내고,
서버/대시보드가 관리기준과 비교해 위험을 띄운다.

## 4. 데이터 전송 방식 (이번 구현)
- DANGER 수신 시 **고정 계측 데이터(`bridge/payload.json`)를 그대로 POST**한다.
  - 이 데이터는 예제 `inclinometer_post.py` 의 `sensor_data` 와 동일(81점).
  - `measurement_date` 만 전송 시각으로 갱신, 변위 값은 손대지 않는다.
- 별도 데이터 합성·랜덤 생성·관리기준 비교는 하지 않는다(서버가 판정).

## 5. 검증 (GET)
`python bridge.py --config config.yaml --check` → 현재 저장된 계측값을 조회해 출력
(예제 `inclinometer_get.py` 와 동일 요청).

## 6. 확정된 운영 결정
- **평시 복귀**: 브리지는 NORMAL 이벤트를 무시한다. 평시 복귀는 **프로젝트에서 자체 처리**.
- **measurement_date**: 매 전송마다 **현재 시각**(`YYYY-MM-DDTHH:MM:SS`)으로 갱신 →
  같은 날 반복 전송해도 항상 최신값이라 서버가 최신 위험으로 인식.
