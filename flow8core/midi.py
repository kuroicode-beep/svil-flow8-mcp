# C:\Projects\svil-flow8-mcp\flow8core\midi.py
# MIDI 전송 계층 — Windows MIDI OUT은 한 프로세스만 열 수 있으므로 보낼 때만 열고 즉시 닫는다.
from __future__ import annotations

import subprocess
from typing import Protocol

PORT_KEYWORD = "FLOW 8"
KNOWN_PORT_HOLDERS = ("flow-8-midi.exe",)   # 포트를 상주 점유하는 것으로 알려진 앱


class Flow8PortError(RuntimeError):
    pass


class MidiSink(Protocol):
    """전송 대상 인터페이스 — 실제 포트 또는 테스트용 스텁."""

    def send(self, message: bytes) -> None: ...


class StubSink:
    """테스트용: 보낸 바이트를 기록만 한다."""

    def __init__(self) -> None:
        self.sent: list[bytes] = []

    def send(self, message: bytes) -> None:
        self.sent.append(bytes(message))


def _port_holder_hint() -> str:
    """포트를 잡고 있을 법한 프로세스가 떠 있으면 이름을 알려준다."""
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout.lower()
    except Exception:  # noqa: BLE001
        return ""
    found = [p for p in KNOWN_PORT_HOLDERS if p in out]
    return f" (실행 중: {', '.join(found)} — 이 앱을 닫아 주세요)" if found else ""


def find_out_port() -> int:
    import rtmidi

    out = rtmidi.MidiOut()
    for i, name in enumerate(out.get_ports()):
        if PORT_KEYWORD.upper() in name.upper():
            return i
    raise Flow8PortError("FLOW 8 MIDI OUT 포트가 없어요. USB 연결과 믹서 전원을 확인해 주세요.")


class RtmidiSink:
    """실제 FLOW 8 MIDI OUT — 컨텍스트 안에서만 열려 있다."""

    def __init__(self) -> None:
        self._out = None

    def __enter__(self) -> "RtmidiSink":
        import rtmidi

        idx = find_out_port()
        out = rtmidi.MidiOut()
        try:
            out.open_port(idx)
        except Exception as exc:  # noqa: BLE001  rtmidi.SystemError 등
            raise Flow8PortError(f"FLOW 8 MIDI OUT 포트를 열지 못했어요 — 다른 앱이 사용 중일 수 있어요{_port_holder_hint()}: {exc}") from exc
        self._out = out
        return self

    def send(self, message: bytes) -> None:
        assert self._out is not None
        self._out.send_message(list(message))

    def __exit__(self, *exc) -> None:
        if self._out is not None:
            try:
                self._out.close_port()
            finally:
                self._out = None


def cc(channel: int, control: int, value: int) -> bytes:
    return bytes([0xB0 | channel, control & 0x7F, value & 0x7F])


def program_change(channel: int, program: int) -> bytes:
    return bytes([0xC0 | channel, program & 0x7F])


def note_on(channel: int, note: int, velocity: int) -> bytes:
    return bytes([0x90 | channel, note & 0x7F, velocity & 0x7F])
