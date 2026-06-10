#!/usr/bin/env python3
"""온사이트 계측 API GET 디버그 예제.

실행:  python get_example.py
아래 ▼변수만 바꿔가며 디버깅하세요. (requests 필요: pip install requests)

핵심: 토큰이 그 서버 키로 서명돼야 함.
  - 401 "UNAUTHENTICATED"        → 게이트웨이가 토큰 거부(인증 안 됨)
  - 401 "TOKEN_SIGNATURE_INVALID"→ 서명 검증 실패 = 이 호스트용 토큰이 아님(=다른 환경)
  - 200                          → 성공
"""
import base64
import json
import requests

# ▼▼▼ 바꿔가며 테스트 ▼▼▼
HOST    = "https://api.onsite.kr-qa-midasit.com"   # 환경 다르면 호스트 교체 (dev/stage/prod 등)
TOKEN   = "eyJhbGciOiJSUzUxMiJ9.eyJzdWIiOiIxMzEifQ.IODsPJjxHbmfQtJxmAhi_OamPu4KlheuxDyyzkn4Mmbf97A09itHH510C-yShmYNWmATKuiw6X0YuIVcElNmTLUNvq3iLfuxnGHo5D6c9HVG6HQpCEEWe2fw30V45UYZrdqtV33wsCiIHEKPIaKaupWzmKQFIN9iIY_Dwf8gnNfQX6mNnTNorQxBOyiHLqve5G8-9ucIfcuBp9pGVL8mTqQgy5vUJ28sEJBV1t0HNMuDKJ3N1hwJo7qO-DA0WsKxeM0cxHWK2JLbpvHxyDGI_p4SSroJh2VbIvLR-ygxvrAHLUM-NyKc3_T7Om3xgySJ2AuTFPKj8v2tC4TdpHSkMQ"
PROJECT = 143
SENSOR  = 2100
# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

def show_jwt(tok):
    try:
        h, p, _sig = tok.split(".")
        pad = lambda s: s + "=" * (-len(s) % 4)
        print("JWT header :", base64.urlsafe_b64decode(pad(h)).decode())
        print("JWT payload:", base64.urlsafe_b64decode(pad(p)).decode())
    except Exception as e:
        print("JWT decode 실패:", e)

def get(url):
    try:
        r = requests.get(url, headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        }, timeout=5)
        print(f"\n[GET {r.status_code}] {url}")
        print("  ", r.text[:500])
        return r.status_code
    except Exception as e:
        print(f"\n[GET ERR] {url}\n   {e}")
        return None

if __name__ == "__main__":
    show_jwt(TOKEN)
    # 1) 센서 경로(표준)
    get(f"{HOST}/inclinometer/sensor/{SENSOR}")
    # 2) 프로젝트 경로 변형들 — 필요하면 주석 해제해서 비교
    # get(f"{HOST}/inclinometer/project/{PROJECT}/sensor/{SENSOR}")
    # get(f"{HOST}/project/{PROJECT}/inclinometer/sensor/{SENSOR}")
