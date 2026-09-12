# C:\Projects\svil-flow8-mcp\server.py
# svil-flow8 MCP 서버 — 클로드 코드 채팅으로 Behringer FLOW 8 믹서를 USB MIDI로 조작한다 (stdio).
# 등록: C:\Projects\audio-hotkeys\.venv\Scripts\python.exe C:\Projects\svil-flow8-mcp\server.py
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, r"C:\Projects\audio-hotkeys")  # audio_hotkeys 패키지 (슬롯 연동)

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as FastMCP  # noqa: E402
except ModuleNotFoundError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP  # noqa: E402

from flow8core import APP_VERSION, Flow8Controller, Flow8Error  # noqa: E402
from flow8core.midi import Flow8PortError  # noqa: E402

mcp = FastMCP("svil-flow8")
_ctl = Flow8Controller()


# 컨트롤러 호출을 감싸 사용자 오류·포트 오류를 안내문으로 돌려준다
def _run(fn, *a, **kw) -> str:
    try:
        return fn(*a, **kw)
    except (Flow8Error, Flow8PortError) as exc:
        return f"실패: {exc}"
    except Exception as exc:  # noqa: BLE001
        return f"예상치 못한 오류: {type(exc).__name__}: {exc}"


@mcp.tool()
def flow8_status() -> str:
    """FLOW 8 상태 요약 — 이 PC에서 마지막으로 보낸 값 기준(믹서는 상태를 돌려주지 않음). 포트 연결 여부 포함."""
    d = _ctl.status()
    d["포트"] = _ctl.port_check()
    d["코어_버전"] = APP_VERSION
    return json.dumps(d, ensure_ascii=False, indent=1)


@mcp.tool()
def flow8_snapshot_load(snapshot: str) -> str:
    """믹서 본체에 저장된 스냅샷을 불러온다. snapshot: 1~15 번호 또는 등록한 별칭. 16번(공장초기화)은 거부."""
    return _run(_ctl.load_snapshot, snapshot)


@mcp.tool()
def flow8_snapshot_record(snapshot: str) -> str:
    """지금 이 PC가 마지막으로 보낸 값들을 스냅샷 번호의 내용으로 기억한다(믹서 전송 없음). 본체·앱에서 슬롯에 저장한 직후 호출하면, 이후 그 스냅샷을 불러올 때 상태 요약과 상대 조절(nudge)의 기준값이 맞는다."""
    return _run(_ctl.record_snapshot, snapshot)


@mcp.tool()
def flow8_nudge(channel: str, field: str, delta: int) -> str:
    """채널 숫자 항목을 delta만큼 상대 조절(0~127 고정). field: level·gain·send_fx1·send_fx2·send_mon1·send_mon2·eq_*·comp·lowcut·balance. 예: 에코 한 단계 = send_fx1 +8."""
    def go() -> str:
        v = _ctl.nudge(channel, field, delta)
        return f"{channel} {field} → {v} ({round(v * 100 / 127)}%)"
    return _run(go)


@mcp.tool()
def flow8_reset_factory(confirm: str = "") -> str:
    """믹서 공장초기화(PC16). confirm에 정확히 '초기화'를 넣어야만 실행. 되돌릴 수 없으니 사용자 확인 후에만."""
    return _run(_ctl.reset_factory, confirm)


@mcp.tool()
def flow8_mute(channel: str, on: bool = True) -> str:
    """입력 채널 뮤트 켜기/끄기. channel: 1·2·3·4·5/6·7/8·usb 또는 별칭."""
    return _run(_ctl.mute, channel, on)


@mcp.tool()
def flow8_solo(channel: str, on: bool = True) -> str:
    """입력 채널 솔로 켜기/끄기."""
    return _run(_ctl.solo, channel, on)


@mcp.tool()
def flow8_channel(
    channel: str,
    level: str | None = None, gain: str | None = None, balance: str | None = None,
    lowcut: str | None = None, comp: str | None = None,
    eq_low: str | None = None, eq_lowmid: str | None = None, eq_himid: str | None = None, eq_hi: str | None = None,
    send_mon1: str | None = None, send_mon2: str | None = None, send_fx1: str | None = None, send_fx2: str | None = None,
    mute: bool | None = None, solo: bool | None = None,
) -> str:
    """입력 채널 여러 값을 한 번에. 값은 0~127 또는 '60%' 형식. USB/BT 채널은 gain·comp·lowcut 없음."""
    return _run(_ctl.set_channel, channel, level=level, gain=gain, balance=balance, lowcut=lowcut, comp=comp,
                eq_low=eq_low, eq_lowmid=eq_lowmid, eq_himid=eq_himid, eq_hi=eq_hi,
                send_mon1=send_mon1, send_mon2=send_mon2, send_fx1=send_fx1, send_fx2=send_fx2,
                mute=mute, solo=solo)


@mcp.tool()
def flow8_bus(bus: str, level: str | None = None, balance: str | None = None, limiter: str | None = None,
              eq: list[str] | None = None) -> str:
    """버스(main·mon1·mon2·fx1·fx2) 레벨·밸런스·리미터·9밴드 EQ(값 9개 리스트)."""
    return _run(_ctl.set_bus, bus, eq=eq, level=level, balance=balance, limiter=limiter)


@mcp.tool()
def flow8_fx(slot: str, preset: int | None = None, param1: str | None = None, param2: str | None = None) -> str:
    """FX 슬롯(1·2) 프리셋 번호와 파라미터 2개."""
    return _run(_ctl.set_fx, slot, preset=preset, param1=param1, param2=param2)


@mcp.tool()
def flow8_tap_tempo() -> str:
    """탭 템포 1회(딜레이 FX 템포)."""
    return _run(_ctl.tap_tempo)


@mcp.tool()
def flow8_alias_set(kind: str, key: str, name: str) -> str:
    """별칭 등록. kind='snapshot'이면 key=1~15 번호, kind='channel'이면 key=1·2·3·4·5/6·7/8·usb."""
    k = kind.strip().lower()
    if k == "snapshot":
        try:
            n = int(key)
        except ValueError:
            return "실패: 스냅샷 별칭의 key는 1~15 번호예요"
        if not 1 <= n <= 15:
            return "실패: 스냅샷 번호는 1~15"
        _ctl.aliases.set_snapshot(n, name)
    elif k == "channel":
        _ctl.aliases.set_channel(key.strip().lower(), name)
    else:
        return "실패: kind는 snapshot 또는 channel"
    _ctl.aliases.save()
    return f"별칭 등록: {k} {key} = {name}"


@mcp.tool()
def flow8_alias_list() -> str:
    """등록된 스냅샷·채널 별칭 목록."""
    return json.dumps(_ctl.aliases.data, ensure_ascii=False, indent=1)


# ── 폰 앱 경유(ADB) — MIDI로 안 되는 것: 현재 값 읽기, 본체 슬롯에 저장 ──
def _phone_tool(script: str, *args: str, timeout: int = 420) -> str:
    import subprocess
    cmd = [sys.executable, str(HERE / "tools" / script), *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    except subprocess.TimeoutExpired:
        return f"실패: {script} 가 {timeout}초 안에 끝나지 않았어요"
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    return out if r.returncode == 0 else f"실패(exit {r.returncode}): {out}\n{err}".strip()


@mcp.tool()
def flow8_phone_readout() -> str:
    """폰(USB 디버깅·잠금 해제·블루투스 켜짐)의 FLOW Mix 앱을 ADB로 조작해 믹서 현재 값(채널·FX·버스·라우팅)을 읽어 JSON·캡처로 저장한다. 약 2분."""
    return _phone_tool("phone_readout.py")


@mcp.tool()
def flow8_phone_save_slot(slot: int, name: str) -> str:
    """믹서의 지금 상태를 본체 슬롯(1~15)에 저장하고 이름을 붙인다(폰 앱 경유, 약 1분). 저장 뒤 PC 기억값도 갱신. name은 영문·숫자 12자 이내."""
    return _phone_tool("phone_save_slot.py", str(int(slot)), name)


# ── audio-hotkeys 연동 ──
def _hotkeys():
    from audio_hotkeys import audio, config  # noqa: WPS433
    return audio, config


@mcp.tool()
def hotkeys_list_slots() -> str:
    """audio-hotkeys 슬롯 목록(이름·출력·입력·FLOW 8 스냅샷)."""
    try:
        _, config = _hotkeys()
        snaps = config.load_config()["snapshots"]
    except Exception as exc:  # noqa: BLE001
        return f"실패: audio-hotkeys 설정을 읽지 못했어요: {exc}"
    rows = []
    for key, s in snaps.items():
        if not (s.get("output_id") or s.get("input_id")):
            continue
        rows.append({"slot": key, "name": s.get("name"), "출력": s.get("output_name"), "입력": s.get("input_name"),
                     "flow8_snapshot": s.get("flow8_snapshot")})
    return json.dumps(rows, ensure_ascii=False, indent=1)


@mcp.tool()
def hotkeys_apply_slot(slot: str) -> str:
    """audio-hotkeys 슬롯을 적용한다(PC 출력·입력·볼륨·카카오 + 슬롯에 FLOW 8 스냅샷이 있으면 함께). slot: 0~9 번호 또는 슬롯 이름."""
    try:
        audio, config = _hotkeys()
        snaps = config.load_config()["snapshots"]
    except Exception as exc:  # noqa: BLE001
        return f"실패: audio-hotkeys를 불러오지 못했어요: {exc}"
    key = slot.strip()
    if key not in snaps:
        match = [k for k, s in snaps.items() if (s.get("name") or "").strip().lower() == key.lower()]
        if not match:
            return f"실패: 슬롯을 모르겠어요: {slot}"
        key = match[0]
    snap = snaps[key]
    try:
        result = audio.apply_snapshot(snap)
    except Exception as exc:  # noqa: BLE001
        return f"실패: 슬롯 적용 중 오류: {exc}"
    out: dict[str, Any] = {"결과": result.summary, "경고": result.warnings}
    f8 = snap.get("flow8_snapshot")
    if f8:
        out["flow8"] = _run(_ctl.load_snapshot, f8)
    return json.dumps(out, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    mcp.run()
