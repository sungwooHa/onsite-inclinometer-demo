#!/usr/bin/env python3
"""
온사이트 지중경사계 시연 브리지

흐름:
  ESP32(MPU6050) --블루투스(시리얼 포트)--> bridge.py --HTTP--> 온사이트 수집 API --> 기존 대시보드

동작:
  - ESP32가 보낸 줄 단위 JSON 이벤트를 수신 (STATE_CHANGED 등; event_to_action에서 매핑)
  - DANGER(=기울어짐) 시: 고정 계측 데이터(payload.json)를 온사이트 API로 POST
    → 대시보드가 3차 관리기준 초과(위험)로 전환
  - 보낼 때 measurement_date 만 매번 현재 시각으로 갱신(항상 최신), sensor_data 값은 예제와 동일
  - NORMAL(=정상 복귀) 시: 평시 복귀 데이터 미설정 — 무시(필요 시 따로 추가)

온사이트 API (docs/api-contract.md):
  POST {api.url}   # 센서ID는 URL 경로. 본문 = payload.json (measurement_date/unit/sensor_data)
  GET  {api.url}   # 현재 저장된 계측값 조회 (--check)

사용:
  python bridge.py --config config.yaml
  python bridge.py --config config.yaml --dry-run     # POST 없이 페이로드만 출력
  python bridge.py --config config.yaml --simulate    # 시리얼 없이 키보드(d=위험/n=평시)로 테스트
  python bridge.py --config config.yaml --monitor     # POST 없이 수신 데이터만 출력(BT 수신 확인용)
  python bridge.py --config config.yaml --check       # GET 으로 현재 계측값 조회 후 종료
"""
import argparse
import json
import os
import sys
from datetime import datetime

import requests
import yaml

try:
    import serial  # pyserial
except ImportError:
    serial = None

PAYLOAD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "payload.json")


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_payload():
    with open(PAYLOAD_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def post_danger(cfg, dry_run):
    """고정 계측 데이터를 전송. measurement_date 만 매번 현재 시각으로 갱신(항상 최신)."""
    api = cfg["api"]
    payload = load_payload()
    payload["measurement_date"] = datetime.now().replace(microsecond=0).isoformat()
    n = len(payload.get("sensor_data", []))
    if dry_run:
        print(f"[DRY-RUN] {api.get('method', 'POST')} {api['url']}  ({n}점, {payload['measurement_date']})")
        print(f"          {json.dumps(payload, ensure_ascii=False)}")
        return
    r = requests.request(
        api.get("method", "POST"),
        api["url"],
        headers=api.get("headers", {}),
        json=payload,
        timeout=5,
    )
    print(f"[API] {r.status_code}  ({n}점, {payload['measurement_date']})")
    print(r.text)
    r.raise_for_status()


def check(cfg):
    """GET 으로 현재 저장된 계측값 조회 (예제 inclinometer_get.py 와 동일)."""
    api = cfg["api"]
    r = requests.request("GET", api["url"], headers=api.get("headers", {}), timeout=5)
    print(f"[GET] {r.status_code}")
    print(r.text)


def handle_event(cfg, event, dry_run):
    if event == "DANGER":
        print(">> DANGER 수신 → 고정 계측 데이터 전송")
        post_danger(cfg, dry_run)
    elif event == "NORMAL":
        # 평시 복귀 데이터는 미설정. 필요 시 정상 범위 payload 를 따로 전송하도록 추가.
        print(">> NORMAL 수신 (평시 복귀 데이터 미설정 — 무시)")


def event_to_action(msg):
    """펌웨어가 보낸 JSON 메시지를 브리지 동작(DANGER/NORMAL)으로 변환.

    지원하는 두 가지 펌웨어 형식:
      - 구형(USB):  {"event": "DANGER"} / {"event": "NORMAL"}
      - 신형(BT) :  {"event": "STATE_CHANGED", "state": "TILTED"|"NORMAL"|"UNKNOWN", ...}
    해당 없으면(텔레메트리·BT_CONNECTED·UNKNOWN 등) None → 무시.
    """
    event = msg.get("event")
    if event in ("DANGER", "NORMAL"):
        return event
    if event == "STATE_CHANGED":
        if msg.get("state") == "TILTED":
            return "DANGER"
        if msg.get("state") == "NORMAL":
            return "NORMAL"
    return None


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
            action = event_to_action(msg)
            if action:
                handle_event(cfg, action, dry_run)


def run_monitor(cfg):
    """수신 확인용: 받은 모든 줄을 그대로 출력한다(POST 없음).

    연결되면 펌웨어가 즉시 {"event":"BT_CONNECTED",...}를 보내므로,
    그 줄이 찍히면 블루투스 수신이 정상이라는 뜻이다.
    """
    if serial is None:
        sys.exit("pyserial 미설치: pip install -r requirements.txt")
    sc = cfg["serial"]
    print(f"[MONITOR] 시리얼 연결: {sc['port']} @ {sc['baudrate']}  (Ctrl+C 종료)")
    print("[MONITOR] 수신되는 모든 줄을 출력합니다. POST는 하지 않습니다.")
    with serial.Serial(sc["port"], int(sc["baudrate"]), timeout=1) as ser:
        while True:
            line = ser.readline().decode("utf-8", "ignore").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                print(f"[RX:비JSON] {line}")
                continue
            action = event_to_action(msg)
            tag = f"  → action={action}" if action else ""
            print(f"[RX] {line}{tag}")


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
    ap.add_argument("--monitor", action="store_true", help="POST 없이 수신 데이터만 출력(BT 수신 확인용)")
    ap.add_argument("--check", action="store_true", help="GET 으로 현재 계측값 조회 후 종료")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.check:
        check(cfg)
    elif args.simulate:
        run_simulate(cfg, args.dry_run)
    elif args.monitor:
        run_monitor(cfg)
    else:
        run_serial(cfg, args.dry_run)


if __name__ == "__main__":
    main()
