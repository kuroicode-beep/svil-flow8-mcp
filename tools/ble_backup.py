# C:\Projects\svil-flow8-mcp\tools\ble_backup.py
# FLOW 8 상태 백업 — PC 블루투스(BLE)로 덤프 명령을 보내고, 믹서가 USB MIDI로 내보내는 SysEx 덤프를 저장한다.
# 본체 버튼 조작 불필요. 믹서 설정을 바꾸는 명령은 보내지 않는다(인증·세션시작·이름요청·덤프요청만).
# 사용: py -3.13 ble_backup.py [--label 이름] [--wait 25]
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import rtmidi
from bleak import BleakClient, BleakScanner

sys.stdout.reconfigure(encoding="utf-8")

APP_VERSION = "0.1.0"
BACKUP_DIR = Path(os.environ["LOCALAPPDATA"]) / "svil-flow8" / "backups"
PORT_KEYWORD = "FLOW 8"
SERVICE_UUID = "14839ad4-8d7e-415c-9a42-167340cf2339"
CHAR_UUID = "0034594a-a8e7-4b1a-a6b1-cd5243059a57"
# 오픈소스 flow-8-midi가 HCI 스누프로 확인한 고정 패킷들 (마지막 바이트 = 앞 바이트 합 mod 256)
AUTH_PACKET = bytes.fromhex("3901fd062b0639f17fe7b7278b8f355a495c2a")
SESSION_START = bytes([0x37, 0x01, 0x38])
CONFIG_REQUEST = bytes([0x07, 0x01, 0x08])
DUMP_TRIGGER = bytes([0x4B, 0x01, 0x4C])
SYSEX_HEADER = bytes([0xF0, 0x00, 0x20, 0x32, 0x21])
MIN_DUMP = 100


# 패킷 체크섬(앞 바이트 합 mod 256)이 맞는지 확인한다 — 규격 자기검증용
def checksum_ok(p: bytes) -> bool:
    return len(p) >= 2 and (sum(p[:-1]) & 0xFF) == p[-1]


# 0x27 스냅샷 이름 응답을 파싱한다: 27 01 [len][name]... [chk]
def parse_snapshot_names(data: bytes) -> list[str]:
    names: list[str] = []
    if len(data) < 3 or data[0] != 0x27:
        return names
    payload = data[2:-1]
    pos = 0
    while pos < len(payload):
        n = payload[pos]
        pos += 1
        if n == 0 or pos + n > len(payload):
            break
        names.append(payload[pos:pos + n].decode("utf-8", errors="replace").strip())
        pos += n
    return names


# FLOW 8 MIDI IN 포트를 열어 SysEx 수신을 준비한다
def open_midi_in() -> rtmidi.MidiIn:
    midi_in = rtmidi.MidiIn()
    idx = next((i for i, n in enumerate(midi_in.get_ports()) if PORT_KEYWORD.upper() in n.upper()), None)
    if idx is None:
        raise SystemExit("FLOW 8 MIDI IN 포트를 찾지 못했어요. USB 연결과 전원을 확인해 주세요.")
    midi_in.open_port(idx)
    midi_in.ignore_types(sysex=False, timing=True, active_sense=True)
    return midi_in


# MIDI IN에서 FLOW 8 SysEx 덤프를 기다린다
def wait_for_dump(midi_in: rtmidi.MidiIn, seconds: float) -> bytes | None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        msg = midi_in.get_message()
        if msg:
            raw = bytes(msg[0])
            if raw.startswith(SYSEX_HEADER) and len(raw) >= MIN_DUMP:
                return raw
        time.sleep(0.02)
    return None


async def run(label: str, wait: float) -> int:
    midi_in = open_midi_in()
    print("MIDI IN 준비 완료. BLE 스캔 중(12초)…")
    dev = await BleakScanner.find_device_by_filter(
        lambda d, ad: ("FLOW" in (d.name or "").upper()) or (SERVICE_UUID in [u.lower() for u in (ad.service_uuids or [])]),
        timeout=12.0,
    )
    if dev is None:
        midi_in.close_port()
        print("FLOW 8 LE를 못 찾았어요. 믹서 블루투스가 켜져 있는지, 폰 FLOW Mix 앱이 연결을 잡고 있지 않은지 확인해 주세요.")
        return 2
    print(f"발견: {dev.name} [{dev.address}] — 연결 중…")

    notes: list[bytes] = []
    got_ack = asyncio.Event()
    snapshot_names: list[str] = []

    def on_notify(_h, data: bytearray) -> None:
        b = bytes(data)
        notes.append(b)
        if b[:3] == bytes([0x36, 0x01, 0x37]):
            got_ack.set()
        if b and b[0] == 0x27:
            snapshot_names[:] = parse_snapshot_names(b)

    async with BleakClient(dev, timeout=15.0) as client:
        print("연결됨. 알림 구독 시도…")
        subscribed = True
        try:
            await client.start_notify(CHAR_UUID, on_notify)
        except Exception as exc:  # Windows에서 구독이 실패해도 덤프(USB)는 진행한다
            subscribed = False
            print(f"알림 구독 실패(이름 읽기만 불가, 덤프는 진행): {exc}")

        await client.write_gatt_char(CHAR_UUID, AUTH_PACKET, response=True)
        print("인증 키 전송")
        if subscribed:
            try:
                await asyncio.wait_for(got_ack.wait(), timeout=3.0)
                print("인증 확인(0x36) 수신")
            except asyncio.TimeoutError:
                print("인증 확인 응답 없음 — 계속 진행")
        await asyncio.sleep(0.2)
        await client.write_gatt_char(CHAR_UUID, SESSION_START, response=True)
        print("세션 시작 전송")
        await asyncio.sleep(1.0)
        if subscribed:
            await client.write_gatt_char(CHAR_UUID, CONFIG_REQUEST, response=True)
            await asyncio.sleep(1.5)
            if snapshot_names:
                print("스냅샷 이름:", ", ".join(f"{i + 1}={n or '(빈칸)'}" for i, n in enumerate(snapshot_names)))
        await client.write_gatt_char(CHAR_UUID, DUMP_TRIGGER, response=True)
        print(f"덤프 요청(0x4B) 전송 — USB MIDI IN에서 최대 {wait:.0f}초 대기…")
        dump = await asyncio.get_event_loop().run_in_executor(None, wait_for_dump, midi_in, wait)
        if subscribed:
            try:
                await client.stop_notify(CHAR_UUID)
            except Exception:
                pass
    midi_in.close_port()

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    base = BACKUP_DIR / f"{stamp}_{label}"
    meta = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "label": label,
        "device": {"name": dev.name, "address": dev.address},
        "snapshot_names": snapshot_names,
        "ble_notifications": [n.hex(" ") for n in notes],
        "sysex": None,
    }
    if dump is None:
        (base.with_suffix(".json")).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print("USB로 덤프가 오지 않았어요. BLE 알림 기록만 저장:", base.with_suffix(".json"))
        return 1
    base.with_suffix(".syx").write_bytes(dump)
    meta["sysex"] = {
        "size": len(dump),
        "header_hex": dump[:12].hex(" "),
        "valid_header": dump.startswith(SYSEX_HEADER),
        "ends_with_f7": dump[-1] == 0xF7,
    }
    base.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 완료: {base.with_suffix('.syx')} ({len(dump)} bytes)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="latest")
    ap.add_argument("--wait", type=float, default=25.0)
    a = ap.parse_args()
    for p in (AUTH_PACKET, SESSION_START, CONFIG_REQUEST, DUMP_TRIGGER):
        if not checksum_ok(p):
            raise SystemExit(f"패킷 체크섬 불일치: {p.hex(' ')}")
    return asyncio.run(run(a.label, a.wait))


if __name__ == "__main__":
    sys.exit(main())
