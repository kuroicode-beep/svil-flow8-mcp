# C:\Projects\svil-flow8-mcp\flow8core\mapping.py
# FLOW 8 MIDI 매핑 정본 — 오픈소스 flow-8-midi v1.1.0 midi_mapper.rs 대조 (2026-09-10). 채널 번호는 0-기반.
from __future__ import annotations

from dataclasses import dataclass

SNAPSHOT_MAX = 15
GLOBAL_CH = 15          # 스냅샷·초기화·탭템포 (1-기반 16번)
FX_CTRL_BASE = 13       # FX1 컨트롤 13, FX2 컨트롤 14
RESET_PROGRAM = 16      # 공장초기화 — 반드시 별도 확인 절차 뒤에만


@dataclass(frozen=True)
class Channel:
    idx: int            # MIDI 채널 (0~6)
    label: str          # 사람 표기
    aliases: tuple[str, ...]
    has_gain: bool = True   # USB/BT 채널은 게인·컴프·로우컷 없음


CHANNELS: tuple[Channel, ...] = (
    Channel(0, "Ch1 XLR", ("1", "ch1", "1번", "채널1")),
    Channel(1, "Ch2 XLR", ("2", "ch2", "2번", "채널2")),
    Channel(2, "Ch3 Combo", ("3", "ch3", "3번", "채널3")),
    Channel(3, "Ch4 Combo", ("4", "ch4", "4번", "채널4")),
    Channel(4, "Ch5/6 Line", ("5", "5/6", "56", "ch5", "ch5/6", "5번", "채널5")),
    Channel(5, "Ch7/8 Line", ("6", "7/8", "78", "ch7", "ch7/8", "7번", "채널7")),
    Channel(6, "USB/BT", ("usb", "bt", "usb/bt", "7", "유에스비", "블루투스"), has_gain=False),
)

# 입력 채널 CC — 값 0~127. 뮤트·솔로는 반전(127=켜져서 소리남, 0=뮤트/솔로 해제 아님 주의: solo도 127=off)
CHANNEL_CC = {
    "eq_low": 1, "eq_lowmid": 2, "eq_himid": 3, "eq_hi": 4,
    "mute": 5, "solo": 6,
    "level": 7, "gain": 8, "lowcut": 9, "balance": 10, "comp": 11,
    "send_mon1": 14, "send_mon2": 15, "send_fx1": 16, "send_fx2": 17,
}
GAIN_ONLY_FIELDS = ("gain", "comp", "lowcut")   # USB/BT 채널에서 거부

# 버스 — MIDI 채널 7~11
BUSES = {
    "main": (7, "Main", ("메인", "master", "마스터")),
    "mon1": (8, "Mon1", ("모니터1", "monitor1", "모니1")),
    "mon2": (9, "Mon2", ("모니터2", "monitor2", "모니2")),
    "fx1": (10, "FX1 Bus", ("fx1버스", "이펙트1")),
    "fx2": (11, "FX2 Bus", ("fx2버스", "이펙트2")),
}
BUS_CC = {"level": 7, "limiter": 8, "balance": 10}
BUS_EQ_BASE_CC = 11     # 9밴드 EQ: CC 11~19 (band 0~8)
BUS_EQ_BANDS = 9

FX_SLOTS = {"fx1": 0, "fx2": 1, "1": 0, "2": 1}
FX_PARAM_CC = {"param1": 1, "param2": 2}


def resolve_channel(name: str | int, aliases: dict[str, str] | None = None) -> Channel:
    """사용자 표현(번호·별칭·사용자 별칭)을 채널로 바꾼다. 없으면 KeyError."""
    key = str(name).strip().lower()
    if aliases:
        for ch_key, alias in aliases.items():
            if alias.strip().lower() == key:
                key = ch_key.strip().lower()
                break
    for ch in CHANNELS:  # 0-기반 MIDI 인덱스는 사용자에게 노출하지 않는다 — 별칭·표기로만 찾는다
        if key in ch.aliases or key == ch.label.lower():
            return ch
    raise KeyError(f"채널을 모르겠어요: {name} (1·2·3·4·5/6·7/8·usb 중 하나로 불러 주세요)")


def resolve_bus(name: str) -> tuple[str, int, str]:
    key = str(name).strip().lower()
    for bus_key, (midi_ch, label, aliases) in BUSES.items():
        if key == bus_key or key in aliases or key == label.lower():
            return bus_key, midi_ch, label
    raise KeyError(f"버스를 모르겠어요: {name} (main·mon1·mon2·fx1·fx2)")


def to_cc(value: int | float | str) -> int:
    """0~127 원값 또는 '60%' 문자열을 CC 값으로 바꾼다. 범위를 벗어나면 ValueError."""
    if isinstance(value, str):
        s = value.strip()
        if s.endswith("%"):
            pct = float(s[:-1])
            if not 0 <= pct <= 100:
                raise ValueError(f"퍼센트는 0~100 사이여야 해요: {value}")
            return round(pct * 127 / 100)
        value = float(s)
    v = int(round(float(value)))
    if not 0 <= v <= 127:
        raise ValueError(f"값은 0~127(또는 0~100%) 사이여야 해요: {value}")
    return v
