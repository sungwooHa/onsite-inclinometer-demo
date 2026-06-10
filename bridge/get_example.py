#!/usr/bin/env python3
"""온사이트 계측 API GET 연결테스트.

실행:  python get_example.py   (requests 필요: pip install requests)
대상:  프로젝트 143 / 센서 2100 (IN-9A AUTO).  센서ID는 URL 경로에 들어간다.

토큰이 그 서버 키로 서명돼야 함:
  - 401 "UNAUTHENTICATED"         → 게이트웨이가 토큰 거부(인증 안 됨)
  - 401 "TOKEN_SIGNATURE_INVALID" → 서명 검증 실패 = 이 호스트용 토큰이 아님(다른 환경)
  - 200                           → 성공
"""
import base64
import requests

# ▼▼▼ 바꿔가며 테스트 ▼▼▼
HOST   = "https://api.onsite.kr-qa-midasit.com"   # 환경 다르면 호스트 교체 (dev/stage/prod 등)
TOKEN  = "eyJhbGciOiJSUzUxMiJ9.eyJzdWIiOiIxMzEifQ.IODsPJjxHbmfQtJxmAhi_OamPu4KlheuxDyyzkn4Mmbf97A09itHH510C-yShmYNWmATKuiw6X0YuIVcElNmTLUNvq3iLfuxnGHo5D6c9HVG6HQpCEEWe2fw30V45UYZrdqtV33wsCiIHEKPIaKaupWzmKQFIN9iIY_Dwf8gnNfQX6mNnTNorQxBOyiHLqve5G8-9ucIfcuBp9pGVL8mTqQgy5vUJ28sEJBV1t0HNMuDKJ3N1hwJo7qO-DA0WsKxeM0cxHWK2JLbpvHxyDGI_p4SSroJh2VbIvLR-ygxvrAHLUM-NyKc3_T7Om3xgySJ2AuTFPKj8v2tC4TdpHSkMQ"
SENSOR = 2100   # 프로젝트 143 / IN-9A AUTO
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
    get(f"{HOST}/inclinometer/sensor/{SENSOR}")
