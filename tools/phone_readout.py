# C:\Projects\svil-flow8-mcp\tools\phone_readout.py
# 폰의 FLOW Mix 앱을 ADB로 조작해 믹서 현재 값(채널 7개·FX 2개·버스 3개·라우팅)을 읽어 JSON으로 저장한다.
# 믹서는 USB MIDI로 상태를 돌려주지 않으므로, "지금 값이 뭐지?"는 이 경로가 유일하다.
# 전제: Galaxy Z Fold4 접힌 상태(커버 화면 displayId 0, 논리 2316x904), USB 디버깅, 잠금 해제, 블루투스 켜짐.
# 사용: py -3.13 phone_readout.py [--out 경로] [--keep-app]
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ADB = Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
PKG = "com.musicgroup.xairbt"
ACT = f"{PKG}/.Activities.ConnectionActivity"
DISPLAY = "0"                      # 접힌 상태 커버 화면 — input -d 0 필수 (x>904 탭 오작동 회피)
COVER_UNIQUE = "4630946213010294403"
OUT_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "svil-flow8" / "backups"

# 2026-09-10 실측 좌표(논리 프레임). 앱 레이아웃이 바뀌면 uiautomator dump로 다시 잰다.
TAP = {
    "continue_session": (1912, 390),
    "channel": {"1": (143, 221), "2": (430, 221), "3": (718, 221), "4": (1006, 221),
                "5/6": (1294, 221), "7/8": (1582, 221), "usb": (1870, 221)},
    "back": (83, 501),
    "bus_tab": {"FX1": (739, 65), "FX2": (1016, 65), "MON1": (1293, 65), "MON2": (1571, 65), "MAIN": (1849, 65)},
    "bus_detail": (2165, 65),
    "menu": (52, 65),
    "menu_routing": (223, 618),
    "settings_close": (366, 65),
}
EQ_LABELS = ["100 Hz", "500 Hz", "2000 Hz", "12000 Hz"]
BUS_EQ_LABELS = ["63", "125", "250", "500", "1000", "2000", "4000", "8000", "16000"]


def adb(*args: str, timeout: int = 30) -> str:
    r = subprocess.run([str(ADB), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def tap(xy: tuple[int, int], wait: float = 2.0) -> None:
    adb("shell", "input", "-d", DISPLAY, "tap", str(xy[0]), str(xy[1]))
    time.sleep(wait)


def top_activity() -> str:
    out = adb("shell", "dumpsys", "activity", "activities")
    m = re.search(r"topResumedActivity=ActivityRecord\{\S+ u0 (\S+)", out)
    return m.group(1).rsplit(".", 1)[-1] if m else ""


def dump_xml() -> str:
    adb("shell", "uiautomator", "dump", "/sdcard/ui.xml")
    return adb("shell", "cat", "/sdcard/ui.xml")


def nodes(xml: str) -> list[dict[str, str]]:
    """<node …> 속성을 dict로. resource-id는 ':id/' 뒤만 남긴다."""
    out = []
    for m in re.finditer(r"<node ([^>]*)/?>", xml):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(1)))
        rid = attrs.get("resource-id", "")
        attrs["id"] = rid.split(":id/", 1)[1] if ":id/" in rid else rid
        out.append(attrs)
    return out


def texts(xml: str, rid: str) -> list[str]:
    return [n.get("text", "") for n in nodes(xml) if n["id"] == rid]


def require_device() -> None:
    if not ADB.exists():
        sys.exit(f"adb를 찾지 못했어요: {ADB}")
    if not re.search(r"^\S+\tdevice$", adb("devices"), re.M):
        sys.exit("ADB 기기가 없어요. USB 디버깅 연결을 확인해 주세요.")
    if "isKeyguardShowing=true" in adb("shell", "dumpsys", "window"):
        sys.exit("폰이 잠겨 있어요. 잠금 해제 후 다시 실행해 주세요.")


def connect_app() -> None:
    """앱을 새로 띄워 믹서에 연결하고 메인 믹서 화면까지 간다."""
    adb("shell", "am", "force-stop", PKG)
    time.sleep(1)
    adb("shell", "am", "start", "-n", ACT)
    for _ in range(15):
        time.sleep(3)
        if top_activity() == "HomeActivity":
            break
    else:
        sys.exit(f"앱이 믹서에 연결되지 못했어요 (화면: {top_activity() or '없음'}). 블루투스·믹서 전원을 확인해 주세요.")
    tap(TAP["continue_session"], 4)
    if top_activity() != "MainActivity":
        sys.exit(f"메인 믹서 화면이 아니에요: {top_activity()}")


def read_channel(key: str) -> dict:
    tap(TAP["channel"][key], 3)
    xml = dump_xml()
    ns = nodes(xml)
    center = [n["text"] for n in ns if n["id"] == "centerTextView"]
    d: dict = {}
    # 화면 순서: 게인, 컴프, 로우컷, 레벨 (USB/BT는 레벨만)
    if key == "usb":
        d["level"] = center[0] if center else None
    else:
        keys = ["gain", "comp", "lowcut", "level"]
        d.update({k: (center[i] if i < len(center) else None) for i, k in enumerate(keys)})
        # 48V 버튼은 checked 속성이 없어 상태를 못 읽는다 — 색으로만 보임(캡처 참고)
        d["phantom48v"] = "확인 불가(캡처 색으로 판단)"
    # eqValueTextView0~3 만 — 같은 접두의 빈 노드가 하나 더 잡혀 100 Hz 값이 비던 결함(2026-09-12 실기기) 회피
    d["eq"] = {label: next((n["text"] for n in ns if n["id"] == f"eqValueTextView{i}"), None)
               for i, label in enumerate(EQ_LABELS)}
    for btn in ("muteButton", "soloButton"):
        d[btn.replace("Button", "")] = "표시만(selected 속성 없음)"
    tap(TAP["back"], 2)
    return d


def read_bus(name: str) -> dict:
    tap(TAP["bus_tab"][name], 2)
    tap(TAP["bus_detail"], 3)
    xml = dump_xml()
    ns = nodes(xml)
    d: dict = {}
    if name.startswith("FX"):
        d["control"] = [n["text"] for n in ns if n["id"] in ("centerTextView", "control1TextView")]
        d["mode"] = [n["text"] for n in ns if n["id"].startswith("parameter2Option") and n.get("selected") == "true"]
        # 선택된 효과는 selected 속성이 없어 이름만 나열된다 — 캡처에서 보라색 칸이 현재 효과
        d["effects"] = [n["text"] for n in ns if n["id"] == "topTextView"]
        d["effect_note"] = "선택 효과는 캡처의 보라색 칸으로 판단"
    else:
        center = [n["text"] for n in ns if n["id"] == "centerTextView"]
        d["level"] = center[0] if center else None
        d["limiter"] = center[-1] if len(center) >= 2 else None
        if name == "MAIN" and len(center) >= 3:
            d["balance"] = center[1]
        d["eq9"] = dict(zip(BUS_EQ_LABELS, [n["text"] for n in ns if n["id"].startswith("eqValueTextView")]))
    screenshot(f"bus_{name}")
    if top_activity() != "MainActivity":
        tap(TAP["back"], 2)
        if top_activity() != "MainActivity":
            adb("shell", "input", "keyevent", "KEYCODE_BACK")
            time.sleep(2)
    tap(TAP["bus_tab"]["MAIN"], 1)
    return d


def read_routing() -> dict:
    tap(TAP["menu"], 2)
    tap(TAP["menu_routing"], 3)
    ns = nodes(dump_xml())
    radios = {n["id"]: n.get("checked") for n in ns if n["id"].endswith("RadioButton")}
    d = {
        "phones_source": "MAIN" if radios.get("phonesSourceMainRadioButton") == "true" else "MON 1/2",
        "phones_split": "PRE" if radios.get("phonesSplitPreRadioButton") == "true" else "POST",
        "monitor_source": "PRE" if radios.get("monitorSourcePreRadioButton") == "true" else "POST",
        "stereo_link": any(n["id"] == "stereoLinkCheckBox" and n.get("checked") == "true" for n in ns),
        "usb_mode": "RECORDING/STREAMING 은 캡처(노란 버튼)로 판단",
    }
    screenshot("routing")
    tap(TAP["settings_close"], 1)
    return d


_shots: dict[str, str] = {}


def screenshot(name: str) -> None:
    path = OUT_DIR / f"{STAMP}_readout_{name}.png"
    with path.open("wb") as fh:
        subprocess.run([str(ADB), "exec-out", "screencap", "-d", COVER_UNIQUE, "-p"], stdout=fh, timeout=30)
    _shots[name] = str(path)


STAMP = datetime.now().strftime("%Y%m%d_%H%M")


def main() -> int:
    ap = argparse.ArgumentParser(description="FLOW Mix 앱을 ADB로 읽어 믹서 값을 JSON으로 저장")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--keep-app", action="store_true", help="끝나고 앱을 종료하지 않음")
    a = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    require_device()
    connect_app()
    data: dict = {"read_at": datetime.now().isoformat(timespec="seconds"), "channels": {}, "fx": {}, "buses": {}}
    screenshot("main")
    for key in ("1", "2", "3", "4", "5/6", "7/8", "usb"):
        data["channels"][key] = read_channel(key)
        print(f"채널 {key}: {data['channels'][key].get('level')}")
    for name in ("FX1", "FX2"):
        data["fx"][name] = read_bus(name)
    for name in ("MAIN", "MON1", "MON2"):
        data["buses"][name] = read_bus(name)
        print(f"{name}: 레벨 {data['buses'][name].get('level')}")
    data["routing"] = read_routing()
    data["screenshots"] = _shots
    if not a.keep_app:
        adb("shell", "am", "force-stop", PKG)
    out = a.out or (OUT_DIR / f"{STAMP}_readout.json")
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
