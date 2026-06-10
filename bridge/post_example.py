#!/usr/bin/env python3
"""온사이트 계측 API POST 전송 예제.

payload.json 의 변위 프로파일(06-11 위험 모양)을 센서 2100(프로젝트 143 / IN-9A AUTO)으로
1건 전송한다. URL/토큰은 config.yaml 의 api 블록을 그대로 쓴다.

본문 스키마(쓰기): measurement_date / unit / sensor_data
  ※ GET 응답(읽기) 스키마는 measurementTime / data 로 필드명이 다르다 — 헷갈리지 말 것.

[중요] 이 API 는 measurement_date 가 **센서의 기존 최신 측정보다 더 나중**이어야 한다.
같은/이전 날짜로 보내면 서버가 500(SYSTEM.UNEXPECTED)을 낸다(409 아님). 그래서 전송 직전
최신 measurementTime 을 GET 해 그보다 1초 뒤(또는 현재 시각 중 더 나중)로 맞춘다.

실행:  python post_example.py --config config.yaml --dry-run   # 전송 없이 본문만 출력
       python post_example.py --config config.yaml             # 실제 전송(1건)
"""
import argparse
import json
import os
from datetime import datetime, timedelta

import requests
import yaml

PAYLOAD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "payload.json")
FMT = "%Y-%m-%dT%H:%M:%S"


def next_measurement_date(api):
    """기존 최신 측정보다 확실히 나중인 measurement_date(현재 시각 이상)를 만든다.
    이 API 는 최신보다 이르면 500 을 내므로, 보내기 직전 최신값을 GET 해 그 위로 맞춘다."""
    now = datetime.now().replace(microsecond=0)
    try:
        r = requests.get(api["url"], headers=api.get("headers", {}), timeout=5)
        r.raise_for_status()
        results = r.json().get("results", [])
        if results:
            latest = datetime.strptime(results[0]["measurementTime"], FMT)
            return max(now, latest + timedelta(seconds=1)).strftime(FMT)
    except Exception as e:
        print(f"[WARN] 최신 측정 GET 실패({e}) → 현재 시각 사용")
    return now.strftime(FMT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--dry-run", action="store_true", help="전송 없이 본문만 출력")
    args = ap.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        api = yaml.safe_load(f)["api"]
    with open(PAYLOAD_PATH, "r", encoding="utf-8") as f:
        base = json.load(f)

    payload = {
        "measurement_date": next_measurement_date(api),
        "unit": base["unit"],
        "sensor_data": base["sensor_data"],
    }
    n = len(payload["sensor_data"])
    if args.dry_run:
        print(f"[DRY-RUN] {api.get('method', 'POST')} {api['url']}  "
              f"{payload['measurement_date']}  ({n}점)")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    r = requests.request(
        api.get("method", "POST"),
        api["url"],
        headers=api.get("headers", {}),
        json=payload,
        timeout=5,
    )
    print(f"[{r.status_code}] {payload['measurement_date']}  "
          f"{'OK' if r.ok else r.text[:200]}")


if __name__ == "__main__":
    main()
