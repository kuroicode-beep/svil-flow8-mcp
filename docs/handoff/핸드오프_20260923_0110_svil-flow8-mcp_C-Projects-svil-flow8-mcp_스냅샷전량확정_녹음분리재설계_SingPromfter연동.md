## 대상

- 프로젝트: svil-flow8-mcp (flow8core 0.3.0 · MCP 17도구) · 연동 audio-hotkeys v1.12.0 · SingPromfterApp v5.17.0
- 작업 폴더: C:\Projects\svil-flow8-mcp · C:\Projects\audio-hotkeys · C:\Projects\SingPromfterApp
- 세션 시각: 2026-09-23 01:10 (KST)

## 세션 요약

09-22 체크포인트 이후 증분. 폰 앱이 믹서에 못 붙던 문제를 잡고, 본체 스냅샷 네 개를 확정 저장했다. 09-22에 넣은 레코딩 슬롯의 분리 방식이 실제로는 안 먹는다는 것을 측정으로 확인해 다른 방식으로 다시 설계했고, SingPromfter 녹음 입력을 거기에 맞췄다. 세 저장소 모두 코드 변경은 없다.

## 완료된 작업

1. **믹서 BLE 정지 복구** — 폰 앱이 「Connection to mixer FAILED」만 반복. logcat에 5초 스캔이 계속 도는데 아무것도 안 잡혔고, PC에서 BLE 20초 능동 스캔을 돌리자 주변 20개 중 FLOW 8만 없었다. 믹서가 광고를 끊은 상태로 판정 → 소장님이 전원 재기동 → 즉시 복구(rssi −34). 48V 팬텀은 재기동 후에도 유지된다.
2. **본체 스냅샷 1~4 전량 확정 저장** — 1 NORMAL · 2 TALK · 3 SING · 4 REC. 공통 게인 +30 dB · 컴프 57 · 로우컷 47 Hz · EQ 12 kHz +1 · FX1 ROOM 디케이 51 VOCAL · FX2 센드 0 · 48V ON. 마이크 레벨은 1번만 0, 나머지 70. MAIN은 1번 118(+2 dB), 2·3·4는 127(100 %).
3. **녹음 분리 재설계** — 09-22에 넣은 「BT/USB PLAY = PHONES ONLY」는 PC 소리가 16 dB밖에 안 줄어(−37.5 → −53.8 dBFS) 분리가 아니었다. `FROM PC USB 3/4 → MON OUT 1/2` + `헤드폰 소스 = MON 1/2` + `스테레오 링크 ON`으로 바꿔 스냅샷 4에 저장했다. 모니터 센드 90, MON 버스 110.
4. **라우팅이 스냅샷을 따라온다는 것을 확인** — 스냅샷 1로 되돌리자 라우팅도 원상 복구됐다. 폰 없이 슬롯 전환만으로 녹음 모드가 된다는 뜻이다.
5. **audio-hotkeys 슬롯 4 연결** — `%LOCALAPPDATA%\audio-hotkeys\config.json` 슬롯 4를 `flow8_snapshot = 4`, `flow8_main = 100`으로. `apply_slot`이 매번 `config.load_config()`를 부르므로 앱 재시작은 필요 없다(코드 확인).
6. **SingPromfter 녹음 입력 전환** — 입력 장치를 RØDE NT-USB Mini → `MAIN L/R(BEHRINGER FLOW 8 (Streaming))`, 반주 입력 비움(1채널), 입력 볼륨 1.0. 설정 파일은 `%APPDATA%\com.svil\singpromfter_app\shared_preferences.json`, 변경 전 백업 있음.

## 검증 (실측)

조용한 방, 마이크 켜진 실사용 상태, −18 dBFS 톤:

| 스냅샷 | 조용할 때 | PC를 3/4로 | PC를 1/2로 |
|-----|-----|-----|-----|
| 4 REC | −78.3 dBFS | −78.3 (기여 0) | −72.2 |
| 2 TALK | −74.7 dBFS | −78.3 (기여 0) | −38.2 (의도대로 섞임) |

마이크 경로를 전부 끊고 잰 전기적 누설은 REC에서 −84.3 dBFS(무음 바닥). SingPromfter가 쓰는 ffmpeg 인자 그대로 입력을 열어: 스냅샷 1에서 −96.7 dBFS(디지털 무음, 마이크 레벨 0이라 정상), 스냅샷 4에서 −89~−64 dBFS(살아 있음).

## 진행 중 / 미완료 작업

- 슬롯 4에서 헤드폰으로 반주와 자기 목소리가 들리는지 **소장님 귀 확인 대기**. 모니터 경로라 측정 불가.
- SingPromfter **녹음 지연 보정 재조정**. 입력 경로가 USB 마이크 → 믹서로 바뀌었다. 지금 0. 한 곡 받아 보고 보컬이 늦으면 올리고 앞서면 내린다(설정 > 녹음, 5 ms 단위, ±300 범위).
- 마이크 슬라이더 실전 위치 확정 → 폰 연결해 `flow8_phone_save_slot 2 TALK` · `3 SING` · `4 REC` 재저장. 저장값 55 %는 낮은 편이다.
- `.syx` 백업(본체 MIDI Dump)·flow8_backup 도구 보류 그대로.
- 2번 채널 XLR 헤드셋 도착 시 게인 약 +45 dB · 로우컷 · 컴프를 말하기용으로 잡고 TALK 재저장.

## 주요 결정사항 / 규칙

- 녹음 분리는 **USB 3/4 + MON 모니터링** 방식으로 확정. PHONES ONLY 단독은 쓰지 않는다.
- SingPromfter 녹음 입력은 **MAIN L/R 1채널**로 확정. 반주는 앱이 원본 파일에서 잘라 합친다.
- 마이크 볼륨은 1번 슬라이더 수동(09-15 유지). 방송·녹음 슬롯 MAIN 100 % 고정(09-21 유지).
- Outline FLOW 8 정본은 덧붙이지 말고 해당 절을 고친다.

## 함정 (다음 세션이 꼭 알아야 할 것)

- **FLOW 8이 PC에 내주는 녹음 입력은 `MAIN L/R` 하나뿐이다.** dshow 열거 실측: RØDE NT-USB Mini · Razer Barracuda X 2.4 · MAIN L/R. USB Out 3/4는 출력 엔드포인트라 ffmpeg로 못 잡는다 — 반주를 따로 캡처하는 2채널 녹음은 이 장비로 불가능하다.
- **SingPromfter 설정은 슬롯 4에서만 맞다.** 슬롯 1·2·3은 USB 1/2가 메인 믹스로 들어가 반주가 보컬 트랙에 섞인다(−38 dBFS). 앱은 Windows 기본 출력으로 반주를 내므로 슬롯을 먼저 누르고 앱을 켜는 순서가 안전하다.
- **평소 스냅샷에서 MAIN L/R은 디지털 무음(−96.7 dBFS)이다.** 「입력 장치가 죽었다」가 뜨면 장치가 아니라 스냅샷을 먼저 의심한다(앱의 죽은 장치 기준 −85).
- **믹서가 BLE 광고를 스스로 끊는다.** PC에서 BLE 스캔해 `FLOW 8 LE`가 안 잡히면 전원 재기동이 유일한 복구다.
- **오디오 측정은 마이크가 오염시킨다.** 마이크가 켜져 있으면 테스트음을 공기로 주워 담아 전기적 누설처럼 보인다. 전기 경로만 보려면 레벨 0 · FX 센드 0 · 뮤트로 마이크를 끊고 잰다.
- 폰 긴 작업 전 `settings put global stay_on_while_plugged_in 3`, 끝나면 0. 잠금은 ADB로 못 푼다.

## 참고 정보

- 정본 위키: /doc/flow-8-behringer-mcp-T91YN4i9vH (§5 녹음 원리 · §6 SingPromfter 신설)
- 완료보고서: svil-flow8-mcp `docs/reports/report_20260923_스냅샷전량확정_녹음분리재설계_SingPromfter연동_ClaudeCode.md` (커밋 8323696)
- 직전 핸드오프: 핸드오프_20260922_0530_audio-hotkeys_C-Projects-audio-hotkeys_NumLock무관_슬롯별메인레벨_레코딩슬롯
- 바로가기 확인됨: FLOW 8 컨트롤러 · SingPromfter(바탕화면) · audio-hotkeys(시작프로그램). 대상 exe 모두 존재.
- `.claude/worktrees/overlay-shortcuts-skill-svil-9fd8a5`(08-01 세션 잔재)는 이 세션 것이 아니라 건드리지 않았다.

## 다음 세션 시작 시 할 일

1. 소장님께 슬롯 4 헤드폰 확인 결과와 녹음 지연 보정 체감을 묻는다.
2. 마이크 슬라이더 위치가 정해졌으면 폰 연결해 스냅샷 2·3·4 재저장 → 정본 §4 표 갱신.
3. SingPromfter에 「입력이 MAIN L/R인데 믹서가 REC 스냅샷이 아니면 녹음 시작 때 경고」 안전장치를 넣을지 판단. 반주 섞인 테이크는 들어 보기 전엔 모른다.
