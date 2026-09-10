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
    """보낸 값 기록. 채널·버스·FX·스냅샷·최근 이력."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = _load(STATE_PATH, {
            "last_snapshot": None, "channels": {}, "buses": {}, "fx": {},
            "updated_at": None, "history": [],
            "snapshots": {},   # 본체 스냅샷 번호별로 기억해 둔 채널·버스·FX 값 — 불러올 때 섀도에 복원
        })

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
        _save(STATE_PATH, self.data)


class Aliases:
    """스냅샷 번호·채널의 사용자 별칭."""

    def __init__(self) -> None:
        self.data: dict[str, dict[str, str]] = _load(ALIAS_PATH, {"snapshots": {}, "channels": {}})

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

    def set_channel(self, channel_key: str, name: str) -> None:
        self.data.setdefault("channels", {})[channel_key] = name.strip()

    def save(self) -> None:
        _save(ALIAS_PATH, self.data)
