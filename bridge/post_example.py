#!/usr/bin/env python3
"""온사이트 계측 API POST 전송 예제.

payload.json(가장 최근 측정 = 2026-06-11 위험 프로파일)을 센서 2100
(프로젝트 143 / IN-9A AUTO)으로 1건 전송한다. URL/토큰은 config.yaml 의 api 블록을 그대로 쓴다.

본문 스키마(쓰기): measurement_date / unit / sensor_data
  ※ GET 응답(읽기) 스키마는 measurementTime / data 로 필드명이 다르다 — 헷갈리지 말 것.

실행:  python post_example.py --config config.yaml --dry-run   # 전송 없이 본문만 출력
       python post_example.py --config config.yaml             # 실제 전송(1건)
"""
import argparse
import json
import os

import requests
import yaml

PAYLOAD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "payload.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--dry-run", action="store_true", help="전송 없이 본문만 출력")
    args = ap.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        api = yaml.safe_load(f)["api"]
    with open(PAYLOAD_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

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
