#!/usr/bin/env bash
# ESP32(MIDAS_ONSITE_SENSOR) 블루투스 연결 + 브리지 실행을 한 번에.
#
# 동작: unpair → pair → connect 풀 사이클로 BT SPP 를 깨끗이 붙인 뒤 브리지를 실행한다.
#   - 풀 사이클이 필요한 이유: 한 번 끊긴 뒤 `--connect` 만으로는 ACL 은 붙어도 SPP 가
#     재부착 안 돼 "포트는 열렸는데 데이터가 안 오는" 상태가 생긴다(특히 펌웨어 재플래시 후).
#   - 단, unpair 는 /dev/cu.* 포트 노드를 잠깐 없앤다. 재페어 후 노드가 다시 생기기 전에
#     브리지가 포트를 열면 "No such file" 로 크래시하므로, 포트 노드가 생길 때까지
#     wait_port 로 기다린 뒤 브리지를 실행한다.
#
# 사용:
#   ./connect_and_run.sh                # 실전(실제 POST)
#   ./connect_and_run.sh --monitor      # 수신만(POST 없음)
#   ./connect_and_run.sh --dry-run      # 페이로드만(POST 없음)
#   BT_ADDR=.. BT_PORT=.. PYTHON=.. ./connect_and_run.sh   # 주소/포트/파이썬 덮어쓰기
set -uo pipefail
cd "$(dirname "$0")"

ADDR="${BT_ADDR:-70:4B:CA:6F:5D:4A}"            # ESP32 MAC (config.yaml 의 serial.bt_address 와 동일)
PORT="${BT_PORT:-/dev/cu.MIDAS_ONSITE_SENSOR}"  # macOS BT 시리얼 포트 노드 (config.yaml 의 serial.port 와 동일)
PY="${PYTHON:-.venv/bin/python}"
[ -x "$PY" ] || PY="python3"                    # venv 없으면 시스템 python 으로 폴백

# 포트 노드($PORT)가 생길 때까지 최대 $1초 대기(0.5초 간격). 생기면 0.
wait_port() {
  local steps=$(( $1 * 2 )) i=0
  while [ "$i" -lt "$steps" ]; do
    [ -e "$PORT" ] && return 0
    sleep 0.5; i=$((i + 1))
  done
  [ -e "$PORT" ]
}

if command -v blueutil >/dev/null 2>&1; then
  echo "[BT] 풀 사이클: unpair -> pair -> connect ($ADDR)"
  blueutil --unpair  "$ADDR" 2>/dev/null || true
  blueutil --pair    "$ADDR" 2>/dev/null || true   # 0x02(No Connection)로 실패해도 무시 — connect 가 살린다
  blueutil --connect "$ADDR" 2>/dev/null || true
  if wait_port 10; then
    echo "[BT] 포트 노드 확인 ($PORT) — 브리지 실행"
  else
    echo "[BT] 포트 노드 미확인(10s) — 브리지 retry/자동 재연결에 맡기고 진행"
  fi
else
  echo "[BT] blueutil 미설치(brew install blueutil) — 브리지 자동 재연결만 시도"
fi

echo "[BRIDGE] 실행: $PY bridge.py --config config.yaml $*"
exec "$PY" bridge.py --config config.yaml "$@"
