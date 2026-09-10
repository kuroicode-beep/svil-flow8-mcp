# C:\Projects\svil-flow8-mcp\tools\backup_capture.py
# FLOW 8 SysEx 상태 덤프 수신기 — 본체(Snapshots 메뉴 → MIDI Dump)가 보내는 덤프를 USB MIDI IN에서 받아 저장한다.
# 믹서로는 아무것도 보내지 않는다(수신 전용). 사용: py -3.13 backup_capture.py [--label 이름] [--seconds 120]
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import rtmidi

sys.stdout.reconfigure(encoding="utf-8")

APP_VERSION = "0.1.0"
BACKUP_DIR = Path(os.environ["LOCALAPPDATA"]) / "svil-flow8" / "backups"
PORT_KEYWORD = "FLOW 8"
HEADER = bytes([0xF0, 0x00, 0x20, 0x32, 0x21])  # Behringer(00 20 32) + FLOW 8(21)
MIN_DUMP = 100  # 오픈소스 파서의 최소 크기 기준


# FLOW 8 MIDI IN 포트 인덱스를 찾는다 (없으면 None)
def find_port(midi_in: rtmidi.MidiIn) -> int | None:
    for i, name in enumerate(midi_in.get_ports()):
        if PORT_KEYWORD.upper() in name.upper():
            return i
    return None


# 수신한 덤프를 .syx(원본)와 .json(메타)으로 저장하고 경로를 돌려준다
def save_dump(data: bytes, label: str) -> tuple[Path, Path]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    base = BACKUP_DIR / f"{stamp}_{label}"
    syx = base.with_suffix(".syx")
    meta = base.with_suffix(".json")
    syx.write_bytes(data)
    info = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "label": label,
        "size": len(data),
        "header_hex": data[:12].hex(" "),
        "valid_header": data.startswith(HEADER),
        "ends_with_f7": data[-1] == 0xF7,
        "note": "파싱값(.json 상세)은 flow8core 파서 구현 후 채운다",
    }
    meta.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return syx, meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="latest")
    ap.add_argument("--seconds", type=int, default=120)
    a = ap.parse_args()

    midi_in = rtmidi.MidiIn()
    idx = find_port(midi_in)
    if idx is None:
        print("FLOW 8 MIDI IN 포트를 찾지 못했어요. USB 연결과 전원을 확인해 주세요.")
        return 2
    try:
        midi_in.open_port(idx)
    except rtmidi.SystemError as exc:  # 다른 앱이 포트를 잡고 있을 때
        print(f"포트를 열지 못했어요(다른 앱이 사용 중일 수 있어요): {exc}")
        return 3
    midi_in.ignore_types(sysex=False, timing=True, active_sense=True)

    print(f"수신 대기 중 ({a.seconds}초). 본체 Snapshots 메뉴에서 MIDI Dump를 실행해 주세요.")
    deadline = time.time() + a.seconds
    got: list[bytes] = []
    while time.time() < deadline:
        msg = midi_in.get_message()
        if msg:
            raw = bytes(msg[0])
            if raw and raw[0] == 0xF0:
                got.append(raw)
                print(f"SysEx 수신: {len(raw)} bytes, 헤더 {raw[:6].hex(' ')}")
                if raw.startswith(HEADER) and len(raw) >= MIN_DUMP:
                    break
        time.sleep(0.02)
    midi_in.close_port()

    dumps = [g for g in got if g.startswith(HEADER) and len(g) >= MIN_DUMP]
    if not dumps:
        print("덤프를 받지 못했어요." + (f" (다른 SysEx {len(got)}건 수신)" if got else ""))
        return 1
    syx, meta = save_dump(dumps[-1], a.label)
    print(f"저장 완료: {syx}  ({len(dumps[-1])} bytes)")
    print(f"메타: {meta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
