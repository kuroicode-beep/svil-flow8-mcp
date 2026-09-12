# C:\Projects\svil-flow8-mcp\flow8core\__init__.py
# flow8core — Behringer FLOW 8 믹서를 USB MIDI로 조작하는 공용 코어. svil-flow8 MCP 서버와 audio-hotkeys가 함께 쓴다.
from .controller import Flow8Controller, Flow8Error
from .mapping import CHANNELS, BUSES, FX_SLOTS, SNAPSHOT_MAX

APP_VERSION = "0.3.0"
VERSION_HISTORY = [
    ("0.3.0", "2026-09-12", "폰 앱 경유 도구 — 현재 값 읽기(phone_readout)·본체 슬롯 저장(phone_save_slot), MCP 도구 17개"),
    ("0.2.0", "2026-09-10", "스냅샷 내용 기억(record)·불러올 때 섀도 복원, 채널 값 상대 조절(nudge) — 에코 단축키용"),
    ("0.1.0", "2026-09-10", "최초 — 스냅샷·채널·버스·FX·탭템포 MIDI 전송, 섀도 상태·별칭, 포트 점유 안내"),
]

__all__ = ["Flow8Controller", "Flow8Error", "CHANNELS", "BUSES", "FX_SLOTS", "SNAPSHOT_MAX", "APP_VERSION", "VERSION_HISTORY"]
