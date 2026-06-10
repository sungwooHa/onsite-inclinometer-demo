#!/usr/bin/env bash
# ESP32(MIDAS_ONSITE_SENSOR) 블루투스 연결 복구 + 브리지 실행을 한 번에.
#
# 왜 풀 사이클인가:
#   브리지를 껐다 켜거나(예: --monitor ↔ --dry-run 전환) 연결이 한 번 끊기면
#   SPP 채널이 깨지고, `blueutil --connect`(브리지 자동 재연결)만으로는 ACL은 붙어도
#   SPP가 안 붙어 데이터가 안 온다(포트는 열려 "시리얼 연결:"까지만 찍히고 조용히 멈춤).
#   그래서 매 실행마다 unpair→pair→connect 전체를 돌린 "직후" 포트를 여는 게 안정적이다.
#
# 사용:
#   ./connect_and_run.sh                # 실전(실제 POST)
#   ./connect_and_run.sh --monitor      # 수신만(POST 없음)
#   ./connect_and_run.sh --dry-run      # 페이로드만(POST 없음)
#   BT_ADDR=xx:xx:... PYTHON=python ./connect_and_run.sh   # 주소/파이썬 덮어쓰기
set -uo pipefail
cd "$(dirname "$0")"

ADDR="${BT_ADDR:-70:4B:CA:6F:5D:4A}"   # ESP32 MAC (config.yaml 의 serial.bt_address 와 동일)
PY="${PYTHON:-.venv/bin/python}"
[ -x "$PY" ] || PY="python3"           # venv 없으면 시스템 python 으로 폴백

if command -v blueutil >/dev/null 2>&1; then
  echo "[BT] 풀 사이클 복구: unpair -> pair -> connect ($ADDR)"
  blueutil --unpair  "$ADDR" 2>/dev/null || true
  blueutil --pair    "$ADDR" 2>/dev/null || true   # 0x02(No Connection)로 실패해도 무시 — connect 가 살린다
  blueutil --connect "$ADDR" 2>/dev/null || true
  if blueutil --info "$ADDR" 2>/dev/null | grep -q "connected"; then
    echo "[BT] connected OK"
  else
    echo "[BT] connect 미확정 — 브리지 자동 재연결(bt_address)에 맡기고 진행"
  fi
else
  echo "[BT] blueutil 미설치(brew install blueutil) — 브리지 자동 재연결만 시도"
fi

echo "[BRIDGE] 실행: $PY bridge.py --config config.yaml $*"
exec "$PY" bridge.py --config config.yaml "$@"
