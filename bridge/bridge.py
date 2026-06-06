#!/usr/bin/env python3
"""
온사이트 지중경사계 시연 브리지

흐름:
  ESP32(MPU6050) --USB 시리얼--> bridge.py --HTTP--> 온사이트 계측 API --> 기존 대시보드

동작:
  - ESP32가 보낸 줄 단위 JSON 이벤트를 수신
  - DANGER 이벤트 시: 3차 관리기준을 초과하는 랜덤 계측값을 생성해 온사이트 API로 POST
  - NORMAL 이벤트 시: (옵션) 평시 범위 값을 전송해 대시보드를 평시로 복귀

사용:
  python bridge.py --config config.yaml
  python bridge.py --config config.yaml --dry-run    # POST 없이 페이로드만 출력
  python bridge.py --config config.yaml --simulate   # 시리얼 없이 키보드(d/n)로 테스트
"""
import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone

import requests
import yaml

try:
    import serial  # pyserial
except ImportError:
    serial = None


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_payload(cfg, value, level):
    """온사이트 API 스키마에 맞춰 수정하세요. (docs/api-contract.md 참고)

    level: 0 = 평시, 3 = 3차 초과(위험)
    """
    m = cfg["measurement"]
    return {
        "sensor_id": m["sensor_id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "value": round(value, 2),
        "unit": m.get("unit", "mm"),
        "level": level,
    }


def post(cfg, payload, dry_run):
    api = cfg["api"]
    body = json.dumps(payload, ensure_ascii=False)
    if dry_run:
        print(f"[DRY-RUN] {api.get('method', 'POST')} {api['url']}  {body}")
        return
    r = requests.request(
        api.get("method", "POST"),
        api["url"],
        headers=api.get("headers", {}),
        json=payload,
        timeout=5,
    )
    print(f"[API] {r.status_code}  {body}")
    r.raise_for_status()


def send_danger(cfg, dry_run):
    """3차 초과 랜덤값 주입. burst_count > 1 이면 짧은 시계열로 주입."""
    m = cfg["measurement"]
    n = int(m.get("burst_count", 1))
    interval = float(m.get("burst_interval_s", 0.5))
    for i in range(n):
        value = random.uniform(float(m["level3"]) * 1.001, float(m["danger_max"]))
        post(cfg, build_payload(cfg, value, level=3), dry_run)
        if i < n - 1:
            time.sleep(interval)


def send_normal(cfg, dry_run):
    m = cfg["measurement"]
    if not m.get("reset_on_normal", True):
        return
    value = random.uniform(0, float(m["level1"]))
    post(cfg, build_payload(cfg, value, level=0), dry_run)


def handle_event(cfg, event, dry_run):
    if event == "DANGER":
        print(">> DANGER 수신 → 3차 초과 데이터 주입")
        send_danger(cfg, dry_run)
    elif event == "NORMAL":
        print(">> NORMAL 수신 → 평시 복귀")
        send_normal(cfg, dry_run)


def run_serial(cfg, dry_run):
    if serial is None:
        sys.exit("pyserial 미설치: pip install -r requirements.txt")
    sc = cfg["serial"]
    print(f"시리얼 연결: {sc['port']} @ {sc['baudrate']}  (Ctrl+C 종료)")
    with serial.Serial(sc["port"], int(sc["baudrate"]), timeout=1) as ser:
        while True:
            line = ser.readline().decode("utf-8", "ignore").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue  # 텔레메트리 깨짐/부분 수신 등은 무시
            if msg.get("event") in ("DANGER", "NORMAL"):
                handle_event(cfg, msg["event"], dry_run)


def run_simulate(cfg, dry_run):
    print("시뮬레이션 모드: d=위험 / n=평시 / q=종료  (한 글자 입력 후 Enter)")
    for line in sys.stdin:
        c = line.strip().lower()
        if c == "q":
            break
        elif c == "d":
            handle_event(cfg, "DANGER", dry_run)
        elif c == "n":
            handle_event(cfg, "NORMAL", dry_run)


def main():
    ap = argparse.ArgumentParser(description="온사이트 지중경사계 시연 브리지")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--dry-run", action="store_true", help="실제 POST 없이 페이로드만 출력")
    ap.add_argument("--simulate", action="store_true", help="시리얼 없이 키보드로 이벤트 입력")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.simulate:
        run_simulate(cfg, args.dry_run)
    else:
        run_serial(cfg, args.dry_run)


if __name__ == "__main__":
    main()
