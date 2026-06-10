# Specialist Agents

메인 세션 에이전트가 오케스트레이터다. 아래 도메인 작업은 **직접 하지 말고** 해당 전문 에이전트에 위임한다.
이 파일이 에이전트 라우팅의 단일 출처(SSOT)다. [CLAUDE.md](../CLAUDE.md)는 원칙만, [INDEX.md](./INDEX.md)는 지도, 라우팅은 여기.

## Routing

| 도메인 | 트리거 | 담당 에이전트 | 범위 |
|--------|--------|--------------|------|
| Firmware | `firmware/**`, `.ino`·`.c/.cpp/.h`, MCU·센서·I2C·Bluetooth 프로토콜 | `firmware-engineer` | 검수·개발·설계 |
| Docs(로컬 자동화) | `git push` 직전, 코드 변경 대비 README/docs 미갱신 | `doc-sync` | 문서 갱신·커밋(푸시 게이트) |

<!-- 전문가가 늘면 위 표에 행만 추가. 행마다 아래에 상세 블록. -->

## firmware-engineer

- **위치**: `~/.claude/agents/firmware-engineer.md` (글로벌)
- **모드**: 검수(Review) · 개발(Development) · 설계(Design)
- **진입 시**: `CLAUDE.md → 이 INDEX/agents → firmware/ → wiring·api-contract → bridge.py` 순으로 로딩 후 작업.
- **위임 원칙**: 펌웨어 코드를 **읽고·수정하고·설계하는** 작업은 전부 이 에이전트로. 메인은 요청 전달·결과 종합만 한다.

## doc-sync (로컬 자동화)

코드만 바뀌고 문서가 뒤처지는 걸 `git push` 시점에 막는 게이트 + 전용 문서 에이전트.

- **위치**: `.claude/agents/doc-sync.md` · 게이트 `.claude/hooks/docsync-gate.py` · 등록 `.claude/settings.json`
  (모두 **로컬** — `.gitignore`가 `.claude/`를 제외하므로 origin엔 안 따라간다. 동작은 이 머신 기준.)
- **발동**: PreToolUse(Bash) 훅이 `git push`를 가로채, `origin/<branch>..HEAD`에 코드(`firmware/`·`bridge/`)
  변경은 있는데 `README.md`/`docs/` 변경이 없으면 push를 차단(exit 2)하고 `doc-sync`를 호출하라고 지시한다.
- **범위**: `doc-sync`는 **문서만** 수정·커밋하고 **절대 push 하지 않는다**. 메인 루프가 커밋 후 같은 push를
  재시도 → 이번엔 문서가 포함돼 게이트 통과.
- **우회**: 문서 변경이 정말 불필요하면(내부 리팩터 등) push 명령에 `DOCS_SYNCED`를 넣거나, `doc-sync`가
  마지막 줄에 `NO_DOC_CHANGE`를 반환하면 메인이 그 우회로 푸시한다.
