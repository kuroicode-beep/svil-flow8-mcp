# svil-flow8-mcp

Behringer **FLOW 8** 믹서를 클로드 코드 채팅(MCP)과 [audio-hotkeys](https://github.com/kuroicode-beep/audio-hotkeys) 단축키로 조작하는 코어. USB MIDI 한 방향 제어이며, 믹서가 상태를 돌려주지 않으므로 "마지막으로 보낸 값"을 섀도 상태로 기록한다.

- 코어 `flow8core` 0.2.0 · MCP 서버 `server.py` (도구 15개) · 기획서 `docs/`
- MIDI 매핑은 오픈소스 [flow-8-midi](https://github.com/abelroes/flow-8-midi) v1.1.0을 대조해 옮겼다.

## 설치·등록

```powershell
py -3.13 -m pip install -e C:\Projects\svil-flow8-mcp   # python-rtmidi, mcp 포함
```

`~/.claude.json`의 `mcpServers`에 `svil-flow8`을 stdio로 등록한다(명령: 파이썬, 인자: `server.py`). 새 클로드 코드 세션에서 도구가 보인다.

## 도구

| 도구 | 하는 일 |
|-----|-----|
| `flow8_status` | 마지막으로 보낸 값·포트 상태 |
| `flow8_snapshot_load` | 본체 스냅샷 1~15 불러오기(번호 또는 별칭). 16번 공장초기화는 거부 |
| `flow8_snapshot_record` | 지금 섀도 값을 스냅샷 번호의 내용으로 기억(본체에 저장한 직후) |
| `flow8_reset_factory` | 공장초기화 — confirm에 정확히 `초기화` |
| `flow8_channel` / `flow8_mute` / `flow8_solo` | 입력 채널 레벨·게인·EQ·컴프·로우컷·센드·뮤트·솔로 |
| `flow8_nudge` | 채널 숫자 항목 상대 조절(0~127 고정) — 에코 단축키가 쓴다 |
| `flow8_bus` | main·mon1·mon2·fx1·fx2 레벨·리미터·밸런스·9밴드 EQ |
| `flow8_fx` | FX 슬롯 프리셋·파라미터 |
| `flow8_tap_tempo` | 탭 템포 |
| `flow8_alias_set` / `flow8_alias_list` | 채널·스냅샷 별칭 |
| `hotkeys_list_slots` / `hotkeys_apply_slot` | audio-hotkeys 슬롯 조회·적용 |
| `flow8_phone_readout` / `flow8_phone_save_slot` | 폰 FLOW Mix 앱을 ADB로 조작해 현재 값 읽기 · 본체 슬롯에 저장(MIDI로 안 되는 둘) |

값은 0~127 또는 `"60%"`. 뮤트·솔로는 믹서 규격대로 반전 전송(127=해제).

## MIDI로 안 되는 것

48V 팬텀, 라우팅, 본체 슬롯에 저장, 현재 값 읽기. 이건 폰 앱(FLOW Mix) 또는 본체 메뉴로만 된다. `tools/phone_readout.py`(현재 값 → JSON·캡처)와 `tools/phone_save_slot.py`(지금 상태를 슬롯 N에 이름 붙여 저장)가 ADB로 폰 앱을 대신 조작한다(Fold4 커버 화면 기준 좌표, 2026-09-12 실기기 검증). FX1 모드는 CC2 ≥64 = VOCAL이며 프리셋 PC를 보내면 INSTRUMENT로 초기화되므로 프리셋 뒤에 다시 보낸다.

## 상태 파일

`%LOCALAPPDATA%\svil-flow8\` — `state.json`(섀도·스냅샷 기억), `aliases.json`, `backups\`, `recipes\`. 테스트는 `SVIL_FLOW8_DIR`로 격리한다.

## 테스트

```powershell
python -m pytest tests\test_core.py -q     # 스텁 포트, 믹서 불필요
python tests\smoke_stdio.py                # MCP stdio로 도구 목록 확인
```

`tools/ble_*.py`는 Windows BLE로 SysEx 덤프를 받으려던 실험 기록이다(실패 — CCCD 없음·Write Not Permitted). `tools/backup_capture.py`는 본체 Snapshots > MIDI Dump를 눌렀을 때 USB MIDI IN으로 오는 덤프를 `.syx`로 저장한다.

## 라이선스

MIT
