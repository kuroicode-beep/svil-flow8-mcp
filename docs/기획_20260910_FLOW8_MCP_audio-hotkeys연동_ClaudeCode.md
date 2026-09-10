# 기획안 — FLOW 8 믹서 채팅 제어(MCP) + audio-hotkeys 연동

- 작성: Claude Code · 2026-09-10 · 상태: 초안(소장님 컨펌 대기)
- 프로젝트: `svil-flow8-mcp`(신규, `C:\Projects\svil-flow8-mcp`) + `audio-hotkeys` v1.6.0 → v1.7.0
- 근거: FLOW 8 MIDI 매핑(오픈소스 flow-8-midi v1.1.0 소스 대조), 이 PC 실측(`FLOW 8 MIDI IN/OUT` 포트 존재, Python 3.13 + `mcp` 1.28.1 설치됨)

## 1. 배경·목표

- FLOW 8은 본체·폰 앱(FLOW Mix, 블루투스)으로만 설정을 바꿀 수 있고, PC용 공식 앱이 없다. 비공식 GUI 앱은 회색 저대비라 저시력에 쓰기 어렵다.
- 믹서는 **USB MIDI를 받기만** 한다. 즉 화면 없이 메시지만 보내면 전부 조작된다.
- 목표: **클로드 코드 채팅 한 줄로 믹서 전체 조작** + **audio-hotkeys 슬롯(Ctrl+Alt+NumPad)에 믹서 스냅샷을 묶어** PC 오디오 장치와 본체 설정이 한 키로 같이 바뀌게 한다.

## 2. 범위

**포함**
- MCP 서버 `svil-flow8`: 스냅샷·채널·버스·FX·탭템포 전부 (아래 §4 매핑 기준)
- 공용 코어 `flow8core`: MIDI 전송·값 변환·섀도 상태 — MCP와 audio-hotkeys가 같은 코드를 쓴다
- audio-hotkeys: 슬롯마다 "FLOW 8 스냅샷 번호" 필드 추가, 적용 시 함께 전송, 설정 화면·토스트·트레이 반영
- MCP에서 audio-hotkeys 슬롯 적용(`"기본 환경으로"` 한 마디로 PC 장치 + 믹서 동시 전환)

**비포함(믹서 규격상 불가)**
- 믹서 현재 상태 읽기(MIDI로 상태를 보내지 않음) → "마지막으로 보낸 값" 기억으로 대체
- 48V 팬텀, FX 뮤트(MIDI 규격 없음 — 본체에서만)
- 스냅샷 이름 읽기(BLE 필요, Windows에서 불안정) → 번호 + 사용자가 붙인 별칭으로 대체

## 3. 아키텍처

```
클로드 코드 채팅 ──stdio──▶ svil-flow8 MCP 서버 (py -3.13, FastMCP)
                                   │ import
audio-hotkeys 트레이 ──import──▶ flow8core (공용 패키지)
                                   │ python-rtmidi
                              FLOW 8 MIDI OUT (USB)
                                   │
                          %LOCALAPPDATA%\svil-flow8\state.json (섀도 상태·별칭)
```

- **포트 배타 규칙**: Windows MIDI OUT은 한 프로세스만 열 수 있다. 코어는 **보낼 때만 열고 즉시 닫는다**(open→send→close). 상주 점유 금지. 비공식 GUI 앱(flow-8-midi.exe)이 떠 있으면 포트를 잡고 있으므로 코어가 "다른 앱이 포트 사용 중"으로 안내한다.
- **섀도 상태**: 보낸 값을 `state.json`에 기록(스냅샷 번호, 채널/버스 마지막 값, 시각). `flow8_status`가 이걸 답한다. 본체 손조작·폰 앱 조작은 반영되지 않음을 응답에 명시.
- **별칭**: `aliases.json` — 스냅샷 번호↔이름(예: 3 = "노래방"), 채널 별칭(예: 1 = "RØDE 마이크"). 채팅에서 이름으로 부를 수 있게.

## 4. MIDI 매핑 (flow-8-midi 소스 대조, 0-기반 채널)

| 대상 | MIDI 채널 | 메시지 |
|---|---|---|
| 입력 채널 1·2·3·4·5/6·7/8·USB/BT | 0~6 | CC1~4 EQ(Low/LowMid/HiMid/Hi) · CC5 뮤트(**127=켜짐=소리남, 0=뮤트**) · CC6 솔로(동일 반전) · CC7 레벨 · CC8 게인 · CC9 로우컷 · CC10 밸런스 · CC11 컴프 · CC14/15 Mon1/Mon2 센드 · CC16/17 FX1/FX2 센드 |
| 버스 Main·Mon1·Mon2·FX1·FX2 | 7·8·9·10·11 | CC7 레벨 · CC10 밸런스 · CC8 리미터 · CC11~19 9밴드 EQ |
| FX1·FX2 컨트롤 | 13·14 | PC(프리셋+1) · CC1/CC2 파라미터 |
| 글로벌 | 15 | **PC 1~15 스냅샷** · PC 16 공장초기화 · NoteOn 0 vel127 탭템포 |

- 값 범위 0~127. 도구는 `%`(0~100)도 받아 127 스케일로 변환.
- USB/BT 채널(6)은 게인·컴프·로우컷 없음(코어에서 거부).

## 5. MCP 도구 목록 (초안)

| 도구 | 인자 | 비고 |
|---|---|---|
| `flow8_status` | – | 포트 연결 여부, 마지막 스냅샷, 채널/버스 섀도 값, 갱신 시각 |
| `flow8_snapshot_load` | `n`(1~15) 또는 별칭 | 16 거부 |
| `flow8_reset_factory` | `confirm="초기화"` | 문자열 불일치 시 거부 (2단계 안전장치) |
| `flow8_mute` / `flow8_solo` | `channel`, `on` | 채널은 번호·"5/6"·"usb"·별칭 |
| `flow8_channel` | `channel` + 선택 인자 level/gain/balance/lowcut/comp/eq_low/eq_lowmid/eq_himid/eq_hi/send_mon1/send_mon2/send_fx1/send_fx2 | 한 호출에 여러 값 |
| `flow8_bus` | `bus`(main/mon1/mon2/fx1/fx2) + level/balance/limiter/eq[9] | |
| `flow8_fx` | `slot`(1/2), preset/param1/param2 | |
| `flow8_tap_tempo` | – | |
| `flow8_alias_set` / `flow8_alias_list` | 스냅샷·채널 별칭 관리 | |
| `hotkeys_apply_slot` | `slot`(0~9 또는 슬롯 이름) | audio-hotkeys 슬롯 적용(PC 장치 + 카카오 + FLOW 8 스냅샷) |
| `hotkeys_list_slots` | – | 슬롯 이름·장치·FLOW 8 번호 요약 |

응답은 전부 한국어 한 줄 요약 + 보낸 바이트(디버그용). 실패는 원인 문장으로(포트 없음/다른 앱 점유/범위 초과).

## 5-1. 본체 스냅샷 백업·복원 (소장님 지정 2026-09-10 — **최우선**)

- 사실: FLOW 8은 **가장 최근에 저장한 스냅샷을 기동 기본값**으로 쓴다. 손댈 일이 생기기 전에 이 상태를 PC에 떠 둔다.
- 경로: 믹서는 MIDI로 상태를 보내지 않지만 **SysEx 상태 덤프(약 3,068바이트)**를 내보낼 수 있다(펌웨어 v11739+). **USB MIDI로는 요청이 불가**(오픈소스 쪽에서 프로브 전부 실패 확인). 트리거는 ① 본체 Snapshots 메뉴의 MIDI Dump(수동) ② BLE `0x4B` 덤프 명령(폰 앱과 같은 방식; PC에선 `bleak`로 시도, Windows BLE 불안정 시 ①로 대체). 어느 쪽이든 덤프 자체는 `FLOW 8 MIDI IN`(USB)으로 들어온다. FLOW 8은 BLE 연결을 하나만 받으므로 백업 중 폰 앱은 끊어 둔다. 헤더 `F0 00 20 32 21`(Behringer·FLOW 8), 채널 레벨/게인/팬/컴프/EQ/센드·버스·스냅샷 이름(0x0554부터 0x1E 간격) 오프셋이 오픈소스 파서에 정리돼 있다.
- 도구
  - `flow8_backup_capture(seconds=30, label)` — MIDI IN을 열고 덤프를 기다린다. 받으면 `%LOCALAPPDATA%\svil-flow8\backups\YYYYMMDD_HHmm_<label>.syx`(원본) + `.json`(파싱값, 사람이 읽는 형태)으로 저장. 못 받으면 "본체 Snapshots 메뉴에서 MIDI Dump를 눌러 주세요" 안내.
  - `flow8_backup_list` — 백업 목록·시각·라벨·파싱 요약(채널 레벨 등)
  - `flow8_backup_restore(name, confirm="복원")` — 파싱값을 **CC로 재전송해 되살린다**(레벨·게인·밸런스·로우컷·컴프·4밴드 EQ·센드·버스 레벨/밸런스/리미터/9밴드 EQ). SysEx 되보내기는 믹서가 받지 않으므로 이 방식만 가능. 복원 불가 항목은 응답에 명시: 48V, FX 뮤트, 스냅샷 이름, 뮤트/솔로 상태(덤프 파싱 범위 확인 후 확정).
  - 복원 후 본체에 다시 저장(Snapshots → Save)하는 것은 본체 조작 — 안내만.
- **실측 결과(2026-09-10 10:20)**: ① Windows BLE는 CCCD 없음·Write Not Permitted·첫 쓰기 0.25초 뒤 끊김으로 `0x4B` 트리거 불가(bleak·WinRT 모두). ② 폰 FLOW Mix 앱을 ADB로 조작해 믹서에 연결한 뒤 재연결 동기화를 두 번 돌렸지만 USB MIDI IN에 SysEx는 오지 않음(600초 대기) — 앱 동기화는 USB 덤프를 유발하지 않는다. ③ 대신 앱 `SETUP > SNAPSHOT LIBRARY > NEW`로 믹서 현재 상태를 폰에 `backup-20260910-current`(10:15:48)로 저장 — 기존 항목 2026-03-24·03-22·2025-12-31도 그대로 있음. 앱 내부 저장소(targetSdk 35, run-as·adb backup 불가)라 파일은 PC로 못 꺼냄. 메타는 `%LOCALAPPDATA%\svil-flow8ackups60910_1015_phone-library_*.json`. `.syx` 백업은 본체 Snapshots > MIDI Dump 수동 실행이 유일한 경로로 남음(소장님 LED 조작 불가 → 보류).
- ADB 조작 요령(Fold4 커버 화면): 논리 프레임 2316x904(회전 1). `input tap`은 x>904에서 엉뚱한 곳을 누르므로 반드시 `input -d 0 tap x y`. 좌표는 `uiautomator dump` bounds 그대로. Git Bash에선 `MSYS_NO_PATHCONV=1`.
- 착수 순서상 **0단계**: 코어의 MIDI IN 수신부만 먼저 만들어 백업 1회를 확보한 뒤 나머지 개발을 진행한다.

## 6. audio-hotkeys 연동 상세 (v1.7.0, MINOR)

- **스키마**: 스냅샷에 `flow8_snapshot: int|null` 추가(`config.py` EMPTY_SNAPSHOT·_normalize). 기존 config는 null로 정규화 → 하위 호환.
- **적용 순서**(`audio.apply_snapshot` 끝에 추가): PC 출력/입력 → 볼륨 → 카카오 → **FLOW 8 스냅샷**(값 있을 때만). 코어가 실패해도 다른 항목은 그대로(기존 "필드 하나 실패해도 전체 중단 안 함" 원칙 유지). 결과 요약에 `FLOW8: 3` 표기.
- **저장(Shift+슬롯)**: 믹서 상태를 읽을 수 없으므로 `flow8_snapshot`은 자동 캡처하지 않고 **기존 값을 유지**한다(덮어쓰기 금지). 설정 화면에서만 바꾼다.
- **설정 화면**(`settings.py`, tkinter): 슬롯 카드마다 "FLOW 8 스냅샷" 콤보(없음·1~15, 별칭 있으면 "3 · 노래방"). 라벨·콤보 18px, 터치타겟 50px, 고대비 — 기존 카드 규격 그대로.
- **토스트·트레이**: 적용 토스트에 FLOW 8 번호 한 줄 추가. 트레이 메뉴 슬롯 항목에 `(F8: 3)` 꼬리표.
- **토글(Ctrl+Alt+.)**: 기존 두 슬롯 핑퐁 그대로 — 슬롯에 FLOW 8 값이 있으면 같이 왕복.
- **의존성**: `python-rtmidi`를 audio-hotkeys venv에 추가, `flow8core`는 별도 저장소 대신 **audio-hotkeys 내부 패키지로 두고 MCP가 그 경로를 import** → 정본 한 곳.
- **i18n**: 5개 언어 키 추가(`flow8_field`, `flow8_applied`, `flow8_port_busy`, `flow8_port_missing`).
- **버전/히스토리**: `version.py` 1.7.0 항목 추가.

## 7. 안전장치

- 공장초기화(PC 16)는 `flow8_reset_factory`에서만, 확인 문자열 필수. 스냅샷 도구는 1~15 외 전부 거부.
- 값 클램프 0~127, 채널·버스 이름 검증, USB 채널 미지원 항목 거부.
- 포트 점유 충돌 시 재시도 없이 즉시 원인 안내(누가 잡고 있는지 프로세스명 포함).
- 로그에 개인정보 없음(바이트·시각만).

## 8. 단계 계획

0. **백업 먼저** — `python-rtmidi` 설치 → MIDI IN 수신 스크립트로 본체 덤프 1회 확보(소장님이 본체에서 MIDI Dump 실행) → `.syx`+`.json` 저장 확인. 이게 끝나기 전에는 믹서로 어떤 메시지도 보내지 않는다.
1. **코어 + MCP** — `flow8core`(전송·변환·섀도·별칭) → FastMCP 서버 → 스텁 포트 단위테스트 → `~/.claude.json` 등록 → 실기 검증(탭템포·뮤트 왕복)
2. **audio-hotkeys 연동** — 스키마·적용·설정 UI·토스트·i18n·버전 → 기존 4슬롯에 FLOW 8 번호 채우기(소장님 지정) → exe 재빌드·배포
3. **MCP→hotkeys 브리지** — `hotkeys_apply_slot`·`hotkeys_list_slots`
4. **문서·위키·핸드오프** — svil-work-wrapup 루틴

## 9. 완료 조건 (기계 판정, 전부 통과가 정상)

- [ ] `py -3.13 server.py` 기동 후 `tools/list`에 §5 도구 전부 노출
- [ ] `rtmidi`로 `FLOW 8 MIDI OUT` 포트 열림·닫힘 왕복 OK(점유 잔존 0)
- [ ] 단위테스트: 도구별 전송 바이트가 §4 매핑표와 1:1 일치(스텁 포트), 스냅샷 0·16·별칭 오타 거부, 리셋 확인 문자열 불일치 거부, `%`→127 변환 경계(0·50·100)
- [ ] `state.json` 갱신·재기동 후 복원
- [ ] `~/.claude.json` 등록 후 새 세션에서 `svil-flow8` 도구 호출 성공
- [ ] audio-hotkeys: 기존 config 로드 시 `flow8_snapshot` null 정규화, 슬롯 적용 결과 문자열에 `FLOW8:` 포함, i18n 5개 언어 키 수 일치, exe 빌드 성공·실행 확인
- [ ] 비공식 GUI 앱 실행 중일 때 "포트 점유" 안내가 나오는지
- [ ] 백업: 수신한 `.syx`가 `F0 00 20 32 21`로 시작하고 `F7`로 끝나며 100바이트 이상, `.json` 파싱값이 채널 7개·버스 5개를 모두 채움, 목록 도구가 그 파일을 보여줌
- [ ] 복원: 백업 `.json`을 스텁 포트로 재전송했을 때 CC 메시지 집합이 파싱값과 1:1 대응(값 손실 0), 확인 문자열 없으면 거부

## 10. 사용자 확인 필요 (완료 조건과 분리)

- **본체에서 MIDI Dump 실행**(Snapshots 메뉴) — `.syx` 백업은 이 조작이 있어야 시작된다. 2026-09-10 현재 폰 앱 라이브러리 백업으로 대체해 두었고, 이 항목은 LED 조작이 가능해질 때까지 보류
- 실제 믹서 반응: 뮤트 켜고 끄기 1회, 스냅샷 1회 (귀·본체 표시로 확인)
- 각 슬롯에 넣을 FLOW 8 스냅샷 번호(기본 환경·노래방송·헤드셋)
- 스냅샷 별칭 이름

## 11. 열린 결정

1. 스냅샷 별칭 초기값 — 폰 앱의 이름을 그대로 옮길지, 새로 지을지
2. 슬롯 저장(Shift) 시 FLOW 8 값 유지 원칙에 동의하는지(자동 캡처 불가 때문)
3. 비공식 GUI 앱 유지 여부 — 포트 충돌 원인이라 시작프로그램에는 두지 않는 쪽 권장

## 12. 리스크

- MIDI OUT 배타 점유(Windows) — §3 규칙으로 회피하되, 다른 DAW/앱이 잡고 있으면 안내만 가능
- 믹서 펌웨어 차이로 CC 응답이 다를 수 있음 — 실기 검증 1회 필수(현재 펌웨어 미확인)
- 상태 미반영: 본체 손조작과 섀도 값이 어긋나면 "마지막 보낸 값"이 사실과 다를 수 있음 → 응답에 항상 "보낸 값 기준" 표기
