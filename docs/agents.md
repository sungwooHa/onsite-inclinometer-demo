# Specialist Agents

메인 세션 에이전트가 오케스트레이터다. 아래 도메인 작업은 **직접 하지 말고** 해당 전문 에이전트에 위임한다.
이 파일이 에이전트 라우팅의 단일 출처(SSOT)다. [CLAUDE.md](../CLAUDE.md)는 원칙만, [INDEX.md](./INDEX.md)는 지도, 라우팅은 여기.

## Routing

| 도메인 | 트리거 | 담당 에이전트 | 범위 |
|--------|--------|--------------|------|
| Firmware | `firmware/**`, `.ino`·`.c/.cpp/.h`, MCU·센서·I2C·Bluetooth 프로토콜 | `firmware-engineer` | 검수·개발·설계 |

<!-- 전문가가 늘면 위 표에 행만 추가. 행마다 아래에 상세 블록. -->

## firmware-engineer

- **위치**: `~/.claude/agents/firmware-engineer.md` (글로벌)
- **모드**: 검수(Review) · 개발(Development) · 설계(Design)
- **진입 시**: `CLAUDE.md → 이 INDEX/agents → firmware/ → wiring·api-contract → bridge.py` 순으로 로딩 후 작업.
- **위임 원칙**: 펌웨어 코드를 **읽고·수정하고·설계하는** 작업은 전부 이 에이전트로. 메인은 요청 전달·결과 종합만 한다.
