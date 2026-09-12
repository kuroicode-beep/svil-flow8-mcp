# 완료보고서 — FLOW 8 믹서 채팅 제어(MCP) + audio-hotkeys 연동

- 기간: 2026-09-10 ~ 2026-09-12 (KST)
- 작업자: Claude Code (유미)
- 프로젝트: `C:\Projects\svil-flow8-mcp` (flow8core 0.3.0, MCP 서버) · `C:\Projects\audio-hotkeys` (v1.7.0 → v1.10.1)
- 정본 위키: Outline 「FLOW 8 (Behringer 오디오 인터페이스) — 채팅 제어 MCP · 백업 · 방송 세팅」 `/doc/flow-8-behringer-mcp-T91YN4i9vH`

## 1. 발단과 결론

"오인페 설정이 갑자기 이상해졌다"에서 시작했다. 실제 원인은 **1번 채널(콘덴서 마이크) 48V 팬텀이 전날 실수로 꺼진 것**이었고, 팬텀은 스냅샷 복원에 포함되지 않아 스냅샷을 불러와도 돌아오지 않았다. 폰 앱(FLOW Mix)에서 다시 켰다. 이 과정에서 소장님 요청대로 믹서를 채팅과 단축키로 조작하는 체계를 만들었다.

## 2. 만든 것

### svil-flow8-mcp (공개 저장소, 0.3.0)
- `flow8core`: USB MIDI 한 방향 제어 코어. 매핑은 오픈소스 flow-8-midi v1.1.0 대조. 믹서가 상태를 돌려주지 않으므로 "마지막으로 보낸 값"을 섀도 상태로 기록하고, 본체 스냅샷별 내용을 기억(record)해 불러올 때 복원한다.
- MCP 서버 도구 17개: 상태·스냅샷 불러오기/기억·채널·뮤트·솔로·버스·FX·탭템포·상대 조절(nudge)·별칭·공장초기화(확인어 필수)·audio-hotkeys 슬롯 조회/적용·폰 경유 읽기/저장.
- `tools/phone_readout.py`: ADB로 폰 FLOW Mix를 조작해 채널 7·FX 2·버스 3·라우팅을 JSON·캡처로 읽는다(실기기 검증 09-12, 약 2분).
- `tools/phone_save_slot.py`: 믹서 현재 상태를 본체 슬롯 N에 이름 붙여 저장하고 PC 기억값을 갱신한다(실기기 검증 09-12).
- 별칭: 채널 `마이크`=1번·`피씨`=USB, 스냅샷 1=`평소`·2=`방송일반`·3=`방송노래`.
- 테스트 16건(스텁 포트), stdio 스모크(도구 17개).

### audio-hotkeys (v1.7.0 → v1.10.1)
| 버전 | 내용 |
|-----|-----|
| 1.7.0 | 슬롯에 FLOW 8 스냅샷 번호를 묶어 Ctrl+Alt+NumPad 한 번에 PC 장치 + 믹서 전환 |
| 1.8.0 | 헤드셋 우선 장치(연결돼 있을 때만) + 자동 전환 감시(3초) |
| 1.9.0 | Ctrl+Alt+NumPad + / − 로 1번 마이크 에코(FX1 센드) 단계 조절, OSD 표시 |
| 1.10.0 | 2순위 우선 스피커(출력만) |
| 1.10.1 | 동글형 헤드셋은 전이를 본 뒤에만 신뢰(레이저 2.4GHz가 꺼도 ACTIVE로 남는 함정) |

슬롯 배정: 0 평소 음악감상(miracle 블루투스 연결 시 스피커 자동, 해제 시 FLOW 8 스피커) · 1 방송 일반(F8:2) · 2 방송 노래(F8:3) · 3 레이저 헤드셋 수동. 랜딩 https://audio-hotkeys.svil.dev/ 와 GitHub Release는 v1.10.1.

### 본체 스냅샷 (2026-09-12 재저장)
| 슬롯 | 이름 | 마이크 레벨 | FX1 센드 |
|-----|-----|-----|-----|
| 1 | NORMAL | OFF | 0 |
| 2 | TALK | 55 % (−26 dB) | 8 % |
| 3 | SING | 55 % (−26 dB) | 35 % |

공통: 게인 +30 dB, 컴프 45 %, 로우컷 약 100 Hz, EQ 12 kHz +1 dB, FX1 ROOM 디케이 40 % **VOCAL**, USB −23 dB, MAIN +2 dB(소장님 노브값), 48V 켜짐.

## 3. 검증 (실제 실행 기준)
- MIDI 전송 → 폰 앱 표시 대조: 컴프 57 %·로우컷 47 Hz·레벨 OFF/−26 dB가 그대로 비춤. 스냅샷 1→3→2→1 순서 불러오기 확인.
- 단축키 등록: RegisterHotKey 점유 검사로 NumPad 0·+·− 확인. 에코 키는 실믹서 MIDI로 0→8→0 확인.
- 헤드셋 자동 전환: 슬롯 0 적용 시 기본 출력이 헤드폰(miracle)로 바뀜을 실측.
- 09-12 재읽기: FX1 VOCAL, 슬롯 이름 NORMAL/TALK/SING, 1번 레벨 OFF.

## 4. 발견한 함정 (메모리에 기록)
- 레이저 2.4GHz 동글은 켜짐/꺼짐에서 Windows 보고값(상태·속성 145개·잭·PnP·마이크 잡음·HID)이 전혀 다르지 않다 → 자동 전환 불가, NumPad 3 수동.
- FX 프리셋(PC)을 보내면 FX1 모드가 INSTRUMENT로 초기화된다. CC2 ≥64 = VOCAL, 프리셋 뒤에 다시 보낸다.
- 폰 앱 SAVE 대화상자는 기존 이름이 채워져 있어 `input text`가 덧붙는다(NORMALNORMAL) → 끝으로 가서 지운 뒤 입력.
- Fold4 접힌 상태 `input tap`은 x>904에서 오작동 → `input -d 0 tap`.
- Windows BLE로는 FLOW 8 SysEx 덤프 트리거 불가, 폰 앱 동기화도 USB로 SysEx를 내보내지 않는다.
- 클로드 Bash 도구가 이중 백슬래시를 하나로 접는다(히어독 파이썬 리터럴이 제어문자로). `python3`은 스토어 스텁이라 무한 대기.
- PyInstaller `--clean`이 `build\localpycs` 삭제에서 WinError 5 → 작업 폴더를 %TEMP%로.
- NumLock이 꺼지면 NumPad 단축키가 전부 안 먹는다.

## 5. 남은 것
- `.syx` SysEx 백업: 본체 Snapshots > MIDI Dump 수동 실행이 유일한 경로(LED 조작 필요). PC 리스너 `tools/backup_capture.py` 준비돼 있음.
- 방송 실전에서 마이크 55 %·리버브 35 % 확정 후 `flow8_phone_save_slot`로 재저장.
- flow8_backup_* 도구는 덤프 경로가 생긴 뒤.

## 6. 커밋
- svil-flow8-mcp: fe959b5 → 7c3a4f8 (0.3.0)
- audio-hotkeys: 416e0bb(1.7.0) · 71c53bc(1.8.0) · c593af9(1.9.0) · 69f26e0(1.10.0) · 84322dd(1.10.1) · 이후 랜딩·README
