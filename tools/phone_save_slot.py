# C:\Projects\svil-flow8-mcp\tools\phone_save_slot.py
# 폰 FLOW Mix 앱을 ADB로 조작해 믹서의 "지금 상태"를 본체 슬롯 N에 저장하고 이름을 붙인 뒤, PC 섀도에 기억시킨다.
# MIDI로는 슬롯 저장이 안 되므로(믹서 규격) 이 경로가 유일하다. 전제·좌표는 phone_readout.py와 같다.
# 사용: py -3.13 phone_save_slot.py <슬롯 1~15> <이름(영문·숫자)> [--keep-app]
from __future__ import annotations

import argparse
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from phone_readout import TAP, adb, connect_app, dump_xml, nodes, require_device, tap, tap_el, top_activity  # noqa: E402

PKG = "com.musicgroup.xairbt"
SLOT_XY = {n: (503 + 350 * ((n - 1) % 4) + 160, 188 + 172 * ((n - 1) // 4) + 35) for n in range(1, 16)}
EDIT_BTN, SAVE_BTN, RENAME_BTN, CLOSE_EDIT = (2185, 65), (1647, 65), (2093, 65), (2250, 65)
NAME_FIELD = (1200, 487)


def _button(xml: str, rid: str) -> tuple[int, int] | None:
    for n in nodes(xml):
        if n["id"] == rid:
            m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", n.get("bounds", ""))
            if m:
                x1, y1, x2, y2 = map(int, m.groups())
                return (x1 + x2) // 2, (y1 + y2) // 2
    return None


def _type_name(name: str) -> None:
    """대화상자 이름 칸은 기존 이름이 채워져 있어 덧붙는다 — 끝으로 가서 지운 뒤 입력한다."""
    tap(NAME_FIELD, 1)
    adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    for _ in range(24):
        adb("shell", "input", "keyevent", "KEYCODE_DEL")
    adb("shell", "input", "text", name)
    time.sleep(0.5)
    adb("shell", "input", "keyevent", "KEYCODE_BACK")   # 소프트 키보드 닫기
    time.sleep(1)


def _confirm() -> bool:
    xml = dump_xml()
    xy = _button(xml, "button1")
    if not xy:
        return False
    tap(xy, 3)
    return True


def slot_names() -> dict[int, str]:
    xml = dump_xml()
    ns = [n for n in nodes(xml) if n["id"] == "nameTextView"]
    names = [n.get("text", "") for n in ns][:15]
    return {i + 1: t for i, t in enumerate(names)}


def main() -> int:
    ap = argparse.ArgumentParser(description="믹서 현재 상태를 본체 슬롯에 저장(폰 앱 경유)")
    ap.add_argument("slot", type=int)
    ap.add_argument("name")
    ap.add_argument("--keep-app", action="store_true")
    a = ap.parse_args()
    if not 1 <= a.slot <= 15:
        sys.exit("슬롯은 1~15")
    if not re.fullmatch(r"[A-Za-z0-9 _-]{1,12}", a.name):
        sys.exit("이름은 영문·숫자·공백 12자 이내(앱 입력이 한글을 못 받아요)")
    require_device()
    connect_app()
    # 메뉴 → MIXER SNAPSHOTS → EDIT (요소 id로 찾고, 없으면 2026-09-10 실측 좌표)
    tap(TAP["menu"], 2)
    tap_el(rid="menuDeviceSnapshotsLinearLayout", fallback=(223, 402), wait=3)
    tap_el(rid="editButton", fallback=EDIT_BTN, wait=2)
    if "RENAME" not in dump_xml():
        sys.exit("EDIT 모드에 들어가지 못했어요")
    slot_label = f"{a.slot:02d}"
    # 슬롯 선택 → SAVE → 이름 → 확인
    tap_el(rid="indexTextView", text=slot_label, fallback=SLOT_XY[a.slot], wait=2)
    tap_el(rid="saveButton", fallback=SAVE_BTN, wait=2)
    _type_name(a.name)
    if not _confirm():
        sys.exit("SAVE 대화상자를 찾지 못했어요")
    # 이름이 겹쳐 들어갔으면 RENAME으로 한 번 더 정리
    names = slot_names()
    if names.get(a.slot) != a.name:
        tap_el(rid="indexTextView", text=slot_label, fallback=SLOT_XY[a.slot], wait=2)
        tap_el(rid="renameButton", fallback=RENAME_BTN, wait=2)
        _type_name(a.name)
        _confirm()
        names = slot_names()
    ok = names.get(a.slot) == a.name
    print(f"슬롯 {a.slot}: {names.get(a.slot)!r} {'저장·이름 확인' if ok else '이름 불일치'}")
    tap(CLOSE_EDIT, 1)   # EDIT 모드 닫기(X)는 id 없음
    tap_el(rid="closeButton", fallback=TAP["settings_close"], wait=1)
    if not a.keep_app:
        adb("shell", "am", "force-stop", PKG)
    # PC 섀도에 기억 — 이후 이 슬롯을 불러올 때 상태 요약·에코 단축키 기준값이 맞는다
    sys.path.insert(0, "C:/Projects/svil-flow8-mcp")
    from flow8core import Flow8Controller
    print(Flow8Controller().record_snapshot(a.slot))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
