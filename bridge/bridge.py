#!/usr/bin/env python3
"""
온사이트 지중경사계 시연 브리지

흐름:
  ESP32(MPU6050) --블루투스(시리얼 포트)--> bridge.py --HTTP--> 온사이트 수집 API --> 기존 대시보드

동작:
  - ESP32가 보낸 줄 단위 JSON 이벤트를 수신 (STATE_CHANGED 등; event_to_action에서 매핑)
  - DANGER(=기울어짐) 시: 대상 센서의 최신 프로파일을 GET해 그 심도 그리드/모양을 쓰고,
    피크 변위를 상수 범위(PEAK_DISPLACEMENT_MIN/MAX_MM)에서 랜덤 스케일해 POST
    → 대시보드가 3차 관리기준 초과(위험)로 전환. GET 실패 시 번들 payload.json 사용.
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
import random
import shutil
import subprocess
import sys
import time
from datetime import datetime

import requests
import yaml

try:
    import serial  # pyserial
except ImportError:
    serial = None

PAYLOAD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "payload.json")

# === 위험(DANGER) 시 보낼 변위 프로파일의 피크(최대 |변위|) 랜덤 범위 (mm) ===
# 관리기준 3차(누적 3mm)를 항상 초과하도록 하한을 3mm 위로 둔다. 데모 톤에 맞게 조정.
PEAK_DISPLACEMENT_MIN_MM = 3.5
PEAK_DISPLACEMENT_MAX_MM = 6.0

# 같은 위험을 연속으로 쏘지 않도록 최소 간격(초). 채터링/같은-초 중복 POST(서버 500) 방지.
POST_MIN_INTERVAL_S = 3.0


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_payload():
    with open(PAYLOAD_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_latest_profile(cfg):
    """대상 센서의 최신 측정 프로파일(심도-변위 배열)을 GET으로 가져온다.
    실패하거나 데이터가 없으면 None → 호출부에서 번들 payload.json로 폴백."""
    api = cfg["api"]
    try:
        r = requests.get(api["url"], headers=api.get("headers", {}), timeout=5)
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return None
        data = results[0].get("data", [])
        return [{"depth": p["depth"], "displacement": p["displacement"]} for p in data] or None
    except Exception as e:
        print(f"[WARN] 센서 프로파일 GET 실패({e}) → 번들 payload.json 사용")
        return None


def build_random_payload(cfg):
    """기준 프로파일의 '모양'은 유지하고 피크 |변위|만 랜덤 스케일한 POST 페이로드를 만든다.

    기준 프로파일: 대상 센서의 최신 측정(GET) → 심도 그리드/모양 자동 일치.
                   GET 실패 시 번들 payload.json.
    피크: 매 호출마다 [PEAK_DISPLACEMENT_MIN_MM, PEAK_DISPLACEMENT_MAX_MM]에서 랜덤.
    """
    base = fetch_latest_profile(cfg)
    source = "GET(센서)"
    if base is None:
        base = load_payload().get("sensor_data", [])
        source = "payload.json"
    base_peak = max((abs(p["displacement"]) for p in base), default=0)
    target_peak = random.uniform(PEAK_DISPLACEMENT_MIN_MM, PEAK_DISPLACEMENT_MAX_MM)
    scale = (target_peak / base_peak) if base_peak else 1.0
    sensor_data = [
        {"depth": p["depth"], "displacement": round(p["displacement"] * scale, 2)}
        for p in base
    ]
    payload = {
        "measurement_date": datetime.now().replace(microsecond=0).isoformat(),
        "unit": {"depth": "mm", "displacement": "mm"},
        "sensor_data": sensor_data,
    }
    return payload, target_peak, source


def post_danger(cfg, dry_run):
    """기준 프로파일을 피크 랜덤 스케일해 전송. measurement_date 는 전송 시각."""
    api = cfg["api"]
    payload, peak, source = build_random_payload(cfg)
    n = len(payload["sensor_data"])
    if dry_run:
        print(f"[DRY-RUN] {api.get('method', 'POST')} {api['url']}  "
              f"({n}점, 기준={source}, peak≈{peak:.2f}mm, {payload['measurement_date']})")
        print(f"          {json.dumps(payload, ensure_ascii=False)}")
        return
    try:
        r = requests.request(
            api.get("method", "POST"),
            api["url"],
            headers=api.get("headers", {}),
            json=payload,
            timeout=5,
        )
    except Exception as e:
        print(f"[API-ERR] 전송 실패: {e}  (브리지는 계속 동작)")
        return
    if r.ok:
        print(f"[API] {r.status_code}  ({n}점, 기준={source}, peak≈{peak:.2f}mm, {payload['measurement_date']})")
    else:
        print(f"[API-ERR] {r.status_code}  {r.text[:160]}  (브리지는 계속 동작)")


def check(cfg):
    """GET 으로 현재 저장된 계측값 조회 (예제 inclinometer_get.py 와 동일)."""
    api = cfg["api"]
    r = requests.request("GET", api["url"], headers=api.get("headers", {}), timeout=5)
    print(f"[GET] {r.status_code}")
    print(r.text)


def handle_event(cfg, event, dry_run):
    if event == "DANGER":
        print(">> DANGER 수신 → 위험 프로파일 전송(피크 랜덤 스케일)")
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


BT_SETTLE_S = 1.5  # blueutil --connect 성공 후 SPP가 붙을 시간(이후 포트 open)


def bt_reconnect(sc):
    """(macOS) 포트를 열기 전에 끊긴 BT SPP 링크를 blueutil --connect 로 되살린다(best-effort).

    serial.bt_address(MAC)가 설정돼 있고 blueutil 이 설치된 경우에만 동작.
    USB 직결(주소 없음)이거나 blueutil 이 없으면 조용히 건너뛴다.
    connect 가 실패해도 예외를 던지지 않는다 — 포트 열기를 그대로 시도하고, 안 되면
    바깥 루프가 3초 뒤 다시 부른다. 페어링 자체가 어긋난 깊은 복구는 수동(아래 안내).
    """
    addr = sc.get("bt_address")
    if not addr:
        return
    if shutil.which("blueutil") is None:
        print("[BT] blueutil 미설치 — 자동 재연결 건너뜀(brew install blueutil). 포트 열기만 시도.")
        return
    try:
        r = subprocess.run(
            ["blueutil", "--connect", addr],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as e:
        print(f"[BT] blueutil 호출 오류: {e} → 포트 열기 시도")
        return
    if r.returncode == 0:
        print(f"[BT] blueutil --connect {addr} OK → {BT_SETTLE_S}s 후 포트 열기")
        time.sleep(BT_SETTLE_S)
    else:
        msg = (r.stderr or r.stdout).strip()
        print(f"[BT] blueutil --connect 실패: {msg} → 포트 열기 시도. "
              f"계속 안 붙으면 수동 복구: blueutil --unpair {addr} && blueutil --pair {addr}")


def run_serial(cfg, dry_run):
    if serial is None:
        sys.exit("pyserial 미설치: pip install -r requirements.txt")
    sc = cfg["serial"]
    last_danger = 0.0
    while True:  # 시리얼/BT가 끊겨도 죽지 않고 재연결 시도(데모 중 끊김 방어)
        bt_reconnect(sc)  # (macOS) 포트 열기 전 BT 링크부터 살린다(blueutil --connect)
        try:
            with serial.Serial(sc["port"], int(sc["baudrate"]), timeout=1) as ser:
                print(f"시리얼 연결: {sc['port']} @ {sc['baudrate']}  (Ctrl+C 종료)")
                while True:
                    line = ser.readline().decode("utf-8", "ignore").strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # 텔레메트리 깨짐/부분 수신 등은 무시
                    action = event_to_action(msg)
                    if action == "DANGER":
                        now = time.monotonic()
                        if now - last_danger < POST_MIN_INTERVAL_S:
                            continue  # 디바운스: 짧은 시간 내 중복 DANGER 무시
                        last_danger = now
                        handle_event(cfg, "DANGER", dry_run)
                    elif action == "NORMAL":
                        handle_event(cfg, "NORMAL", dry_run)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"[SERIAL] 연결 끊김/오류: {e} → 3초 후 재연결 시도")
            time.sleep(3)


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
    bt_reconnect(sc)  # (macOS) BT 링크부터 살리고 포트를 연다
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
