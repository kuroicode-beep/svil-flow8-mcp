## 대상
- 프로젝트: svil-flow8-mcp (flow8core 0.3.0 + MCP 서버) · 연동 audio-hotkeys v1.10.1
- 작업 폴더: C:\Projects\svil-flow8-mcp · C:\Projects\audio-hotkeys
- 세션 시각: 2026-09-12 14:00 (KST)

## 세션 요약
- Behringer FLOW 8 믹서를 클로드 코드 채팅(MCP 도구 17개)과 audio-hotkeys 단축키로 조작하는 체계를 09-10~12 사이에 완성했다. 원인 진단(48V 팬텀 꺼짐), 본체 슬롯 1·2·3 저장, 헤드셋/블루투스 스피커 자동 전환, 에코 단축키, 폰 앱 경유 읽기·저장 스크립트까지.

## 완료된 작업
- svil-flow8-mcp (공개, main 최신 d441595): flow8core 0.3.0, `server.py` 도구 17개, `tools/phone_readout.py`·`tools/phone_save_slot.py` 실기기 검증(09-12), README, 완료보고서 `docs/reports/report_20260912_FLOW8_MCP_audio-hotkeys연동_완료보고_ClaudeCode.md`.
- audio-hotkeys (main 최신 5481f1e): v1.7.0 FLOW 8 스냅샷 연동 → 1.8.0 헤드셋 우선+자동 전환 → 1.9.0 Ctrl+Alt+NumPad +/− 에코 → 1.10.0 우선 스피커 → 1.10.1 동글 신뢰 규칙. `dist\audio-hotkeys.exe` v1.10.1 실행 중, 바탕화면·시작프로그램 바로가기 유효, 랜딩 https://audio-hotkeys.svil.dev/ 와 GitHub Release v1.10.1 반영.
- 슬롯: NumPad 0 평소 음악감상(F8:1, 헤드폰(miracle) 연결 시 스피커 자동·해제 시 FLOW 8 스피커) · 1 방송 일반(F8:2) · 2 방송 노래(F8:3) · 3 레이저 헤드셋 수동. 설정 `%LOCALAPPDATA%\audio-hotkeys\config.json`(백업 `config.backup-20260910-v180.json`).
- 본체 스냅샷 1 NORMAL(레벨 OFF·센드 0) · 2 TALK(55 %·8 %) · 3 SING(55 %·35 %), FX1 ROOM 디케이 40 % **VOCAL**, 48V 켜짐, MAIN +2 dB. PC 기억값(`%LOCALAPPDATA%\svil-flow8\state.json`)도 동일.
- MCP 등록 `~/.claude.json` → `svil-flow8` (audio-hotkeys venv 파이썬, `server.py`). 별칭: 마이크=1번, 피씨=USB, 평소/방송일반/방송노래=1/2/3.
- 백업: 폰 FLOW Mix 라이브러리 `backup-20260910-current` + 기존 3건. 메타·읽기 결과 `%LOCALAPPDATA%\svil-flow8\backups\`.
- 문서: Outline 정본 `/doc/flow-8-behringer-mcp-T91YN4i9vH`(§11 갱신 이력까지), audio-hotkeys 위키 09-10 회차, 작업로그_2026-09 09/10~09/12, 메모리 `flow8-backup-status`·`adb-fold4-cover-display-tap`·`dongle-headset-always-active`·`bash-tool-heredoc-backslash-collapse`.

## 진행 중 / 미완료 작업
- `.syx` SysEx 백업: 본체 Snapshots > MIDI Dump 수동 실행이 유일한 경로(LED 조작 필요). 리스너 `tools/backup_capture.py --label <라벨> --seconds 300` 켜 두고 누르면 `.syx`+`.json` 저장. 그 뒤 flow8_backup_* 도구 착수.
- 방송 실전에서 마이크 55 %·리버브 35 % 확정 → `flow8_phone_save_slot(2 또는 3, 이름)`로 재저장(폰 USB 디버깅·잠금 해제·BT 필요).

## 주요 결정사항 / 규칙
- 레이저 2.4GHz 동글은 헤드셋을 꺼도 Windows에 ACTIVE·잭 연결됨으로 남아(속성·PnP·HID까지 차이 0) 자동 전환 불가 → NumPad 3 수동 고정. 슬롯 0은 miracle만 감시.
- FX 프리셋(PC)을 보내면 FX1 모드가 INSTRUMENT로 초기화된다. CC2 ≥64 = VOCAL, 프리셋 뒤에 param2=127을 다시 보낸다(레시피 `%LOCALAPPDATA%\svil-flow8\recipes\노래방송_카카오보이스룸.json`).
- 방송 중 본체 노브: 헤드폰 노브만. 마스터를 내리면 헤드폰(PRE)엔 들리고 USB 송출만 줄어든다. 물리 슬라이더는 모터가 없어 건드리면 그 위치로 튄다.
- MIDI 조작(PC16 제외)은 저장 슬롯을 덮어쓰지 않는다. 슬롯 저장·48V·라우팅·현재 값 읽기는 폰 앱(ADB) 경로만.
- 폰 조작: 접힌 Fold4 커버 화면은 `input -d 0 tap` 필수, SAVE/RENAME 대화상자는 기존 이름이 채워져 있어 끝으로 가서 지운 뒤 입력.

## 참고 정보
- Outline 정본: /doc/flow-8-behringer-mcp-T91YN4i9vH · audio-hotkeys 위키: /doc/audio-hotkeys-NkvmCKQF5h
- 기획서: C:\Projects\svil-flow8-mcp\docs\기획_20260910_FLOW8_MCP_audio-hotkeys연동_ClaudeCode.md (§5-1 백업 실측)
- 저장소: https://github.com/kuroicode-beep/svil-flow8-mcp · https://github.com/kuroicode-beep/audio-hotkeys
- 테스트: svil-flow8-mcp `tests/test_core.py`(16) · `tests/smoke_stdio.py`(도구 17) · audio-hotkeys `tests/test_pref.py`(10)
- 빌드: audio-hotkeys `build.ps1`(작업 폴더 %TEMP%, dist exe 실행 중이면 먼저 종료) → `publish_site.ps1` → `gh release create`

## 다음 세션 시작 시 할 일
1. 새 클로드 코드 세션에서 `svil-flow8` 도구 17개가 보이는지 확인(이 세션은 등록 전에 시작돼 직접 못 봤다).
2. 소장님 방송 뒤 값 확정 요청이 오면 `flow8_channel`/`flow8_nudge`로 맞추고 `flow8_phone_save_slot`로 재저장 + `flow8_snapshot_record`.
3. LED 조작이 가능해지면 `.syx` 백업 1회 확보 후 flow8_backup_* 도구 착수.
