# C:\Projects\svil-flow8-mcp\flow8core\state.py
# 섀도 상태·별칭 저장 — 믹서는 상태를 돌려주지 않으므로 "마지막으로 보낸 값"만 기록한다.
from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

# SVIL_FLOW8_DIR 환경변수로 저장 위치를 바꿀 수 있다(테스트 격리용)
STATE_DIR = Path(os.environ.get("SVIL_FLOW8_DIR") or (Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "svil-flow8"))
STATE_PATH = STATE_DIR / "state.json"
ALIAS_PATH = STATE_DIR / "aliases.json"
HISTORY_MAX = 200


def _load(path: Path, default: dict) -> dict:
    if not path.exists():
        return dict(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(default)


def _save(path: Path, data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


class ShadowState:
    """보낸 값 기록. 채널·버스·FX·스냅샷·최근 이력.

    🔴 **이 파일은 여러 프로세스가 같이 쓴다** — MCP 서버(`server.py`는 모듈 수준에서
    컨트롤러를 하나 만들어 계속 들고 있다)·audio-hotkeys·일회성 스크립트. 각자 만들 때
    파일을 읽어 두고 [save]에서 통째로 덮어쓰면, 나중에 저장하는 쪽이 그 사이 다른
    프로세스가 적어 둔 내용을 **조용히 지운다.**

    2026-09-23에 실제로 그랬다. 스크립트가 스냅샷 1~4를 기억시켜 뒀는데, 세션 시작 때
    떠 있던 MCP 서버가 나중에 스냅샷을 한 번 불러오면서 자기 메모리(09-22 상태)를
    통째로 썼고 스냅샷 4의 기억값과 그날 이력이 전부 사라졌다. 파일은 멀쩡해 보였고
    에러도 없어서, 「기억된 값 없음」이 뜨기 전까지 알 수가 없었다.

    그래서 [save]는 **쓰기 직전에 디스크를 다시 읽어 합친다.** 이 프로세스가 실제로
    건드린 것만 이기고, 손대지 않은 항목은 디스크 쪽을 남긴다.
    """

    def __init__(self) -> None:
        self.data: dict[str, Any] = _load(STATE_PATH, {
            "last_snapshot": None, "channels": {}, "buses": {}, "fx": {},
            "updated_at": None, "history": [],
            "snapshots": {},   # 본체 스냅샷 번호별로 기억해 둔 채널·버스·FX 값 — 불러올 때 섀도에 복원
        })
        # 합쳐 쓰기용 — 이 프로세스가 기억시킨 스냅샷 번호와, 읽어 온 이력의 길이.
        self._recorded: set[str] = set()
        self._history_base = len(self.data.get("history", []))

    def get_channel(self, idx: int, field: str) -> Any:
        return self.data.get("channels", {}).get(str(idx), {}).get(field)

    def snapshot_values(self, n: int) -> dict | None:
        return self.data.get("snapshots", {}).get(str(n))

    def record_snapshot(self, n: int) -> None:
        """지금 섀도 값(채널·버스·FX)을 스냅샷 n의 내용으로 기억한다."""
        self.data.setdefault("snapshots", {})[str(n)] = {
            "channels": deepcopy(self.data.get("channels", {})),
            "buses": deepcopy(self.data.get("buses", {})),
            "fx": deepcopy(self.data.get("fx", {})),
        }
        self._recorded.add(str(n))

    def restore_snapshot(self, n: int) -> bool:
        """스냅샷 n의 기억값이 있으면 섀도로 되돌린다. 없으면 False."""
        vals = self.snapshot_values(n)
        if not vals:
            return False
        for key in ("channels", "buses", "fx"):
            self.data[key] = deepcopy(vals.get(key, {}))
        return True

    def note(self, summary: str) -> None:
        self.data["updated_at"] = datetime.now().isoformat(timespec="seconds")
        hist = self.data.setdefault("history", [])
        hist.append({"at": self.data["updated_at"], "what": summary})
        del hist[:-HISTORY_MAX]

    def set_channel(self, idx: int, field: str, value: Any) -> None:
        self.data.setdefault("channels", {}).setdefault(str(idx), {})[field] = value

    def set_bus(self, key: str, field: str, value: Any) -> None:
        self.data.setdefault("buses", {}).setdefault(key, {})[field] = value

    def set_fx(self, slot: str, field: str, value: Any) -> None:
        self.data.setdefault("fx", {}).setdefault(slot, {})[field] = value

    def save(self) -> None:
        """디스크를 다시 읽어 합친 뒤 쓴다(클래스 설명의 유실 사고 참고).

        이기는 것: 방금 MIDI로 보낸 값(channels·buses·fx·last_snapshot)과 이 프로세스가
        [record_snapshot]으로 기억시킨 스냅샷. 그 외에는 디스크 쪽을 남긴다.
        이력은 디스크 것 뒤에 이번에 새로 적은 줄만 붙인다.
        """
        disk = _load(STATE_PATH, {})
        merged = dict(disk)

        for key in ("last_snapshot", "channels", "buses", "fx", "updated_at"):
            merged[key] = self.data.get(key)

        # 스냅샷은 번호 단위로 합친다 — 내가 기억시킨 번호만 덮고 나머지는 디스크 것.
        snapshots = dict(disk.get("snapshots") or {})
        mine = self.data.get("snapshots") or {}
        for n in self._recorded:
            if n in mine:
                snapshots[n] = mine[n]
        merged["snapshots"] = snapshots

        history = list(disk.get("history") or [])
        history.extend(self.data.get("history", [])[self._history_base:])
        del history[:-HISTORY_MAX]
        merged["history"] = history

        _save(STATE_PATH, merged)
        # 합친 결과를 이 프로세스의 기준으로 삼는다 — 다음 save가 같은 줄을 또 붙이지 않게.
        self.data["snapshots"] = snapshots
        self.data["history"] = history
        self._history_base = len(history)
        self._recorded.clear()


class Aliases:
    """스냅샷 번호·채널의 사용자 별칭.

    [ShadowState]와 같은 이유로 저장할 때 디스크와 합친다 — 별칭은 자주 바뀌지 않지만,
    한 번 지워지면 다른 세션이 붙여 둔 이름이 말없이 사라진다.
    """

    def __init__(self) -> None:
        self.data: dict[str, dict[str, str]] = _load(ALIAS_PATH, {"snapshots": {}, "channels": {}})
        self._touched: set[tuple[str, str]] = set()   # (구역, 키) — 이번 프로세스가 바꾼 것

    def snapshot_name(self, n: int) -> str | None:
        return self.data.get("snapshots", {}).get(str(n))

    def snapshot_by_name(self, name: str) -> int | None:
        key = name.strip().lower()
        for n, alias in self.data.get("snapshots", {}).items():
            if alias.strip().lower() == key:
                return int(n)
        return None

    def channel_aliases(self) -> dict[str, str]:
        return dict(self.data.get("channels", {}))

    def set_snapshot(self, n: int, name: str) -> None:
        self.data.setdefault("snapshots", {})[str(n)] = name.strip()
        self._touched.add(("snapshots", str(n)))

    def set_channel(self, channel_key: str, name: str) -> None:
        self.data.setdefault("channels", {})[channel_key] = name.strip()
        self._touched.add(("channels", channel_key))

    def save(self) -> None:
        """디스크를 다시 읽어, 이 프로세스가 바꾼 별칭만 덮어쓴다."""
        disk = _load(ALIAS_PATH, {"snapshots": {}, "channels": {}})
        merged = {
            "snapshots": dict(disk.get("snapshots") or {}),
            "channels": dict(disk.get("channels") or {}),
        }
        for section, key in self._touched:
            value = (self.data.get(section) or {}).get(key)
            if value is None:
                merged[section].pop(key, None)
            else:
                merged[section][key] = value
        _save(ALIAS_PATH, merged)
        self.data = merged
        self._touched.clear()
