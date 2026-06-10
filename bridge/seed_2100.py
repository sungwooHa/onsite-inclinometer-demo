#!/usr/bin/env python3
"""센서 2100(IN-9A AUTO, 프로젝트 143)에 시연용 이력 데이터를 삽입한다.

평시 2건(06-03·06-04, 동일 프로파일) + 위험 1건(06-11)을 순서대로 POST 해
대시보드에 "평시 → 위험" 추세를 만든다. URL/토큰은 config.yaml 의 api 블록을 그대로 쓴다.

사용:
  python seed_2100.py --config config.yaml --dry-run   # POST 없이 페이로드만 출력
  python seed_2100.py --config config.yaml             # 실제 POST(3건)

주의: 실제 POST 다. config.yaml 의 url 이 sensor/2100 인지 먼저 확인할 것.
"""
import argparse
import json
import time

import requests
import yaml

# 심도(mm). 0 다음은 1000, 이후 2000 간격(엑셀 원본 그대로 11점).
DEPTHS = [0, 1000, 3000, 5000, 7000, 9000, 11000, 13000, 15000, 17000, 19000]

# (측정일, 심도별 변위[mm]). 평시 2건은 동일, 위험 1건은 피크 |18.68|mm 로 3차 관리기준 초과.
MEASUREMENTS = [
    ("2026-06-03T00:00:00", [2.09, 1.05, 1.05, -0.70, -6.29, -7.68, -9.77, -5.93, -5.93, -0.70, 0.0]),
    ("2026-06-04T00:00:00", [2.09, 1.05, 1.05, -0.70, -6.29, -7.68, -9.77, -5.93, -5.93, -0.70, 0.0]),
    ("2026-06-11T00:00:00", [-2.91, -3.95, -3.95, -5.70, -17.29, -18.68, -16.77, -10.93, -8.93, -3.70, 0.0]),
]

# 같은-초 중복/서버 500 방지 (bridge.py POST_MIN_INTERVAL_S 와 동일 취지).
POST_INTERVAL_S = 3.0


def build_payload(date, displacements):
    return {
        "measurement_date": date,
        "unit": {"depth": "mm", "displacement": "mm"},
        "sensor_data": [
            {"depth": d, "displacement": v} for d, v in zip(DEPTHS, displacements)
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--dry-run", action="store_true", help="실제 POST 없이 페이로드만 출력")
    args = ap.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        api = yaml.safe_load(f)["api"]

    for i, (date, displacements) in enumerate(MEASUREMENTS):
        payload = build_payload(date, displacements)
        if args.dry_run:
            print(f"[DRY-RUN] {api.get('method', 'POST')} {api['url']}  {date}  ({len(DEPTHS)}점)")
            print(f"          {json.dumps(payload, ensure_ascii=False)}")
            continue
        try:
            r = requests.request(
                api.get("method", "POST"),
                api["url"],
                headers=api.get("headers", {}),
                json=payload,
                timeout=5,
            )
        except Exception as e:
            print(f"[ERR] {date} 전송 실패: {e}")
            return
        print(f"[{r.status_code}] {date}  {'OK' if r.ok else r.text[:160]}")
        if i < len(MEASUREMENTS) - 1:
            time.sleep(POST_INTERVAL_S)


if __name__ == "__main__":
    main()
