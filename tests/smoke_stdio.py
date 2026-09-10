# C:\Projects\svil-flow8-mcp\tests\smoke_stdio.py — MCP 서버를 실제 stdio로 띄워 도구 목록과 flow8_status 호출을 확인한다 (믹서로 전송 없음)
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
PY = r"C:\Projects\audio-hotkeys\.venv\Scripts\python.exe"


async def main() -> int:
    params = StdioServerParameters(command=PY, args=[str(ROOT / "server.py")])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            names = sorted(t.name for t in tools.tools)
            print("도구", len(names), "개:", ", ".join(names))
            res = await s.call_tool("flow8_status", {})
            print("flow8_status →", res.content[0].text[:400])
            res = await s.call_tool("flow8_snapshot_load", {"snapshot": "16"})
            print("16번 차단 →", res.content[0].text)
            res = await s.call_tool("hotkeys_list_slots", {})
            print("hotkeys_list_slots →", res.content[0].text[:300])
            expected = {"flow8_status", "flow8_snapshot_load", "flow8_reset_factory", "flow8_mute", "flow8_solo",
                        "flow8_channel", "flow8_bus", "flow8_fx", "flow8_tap_tempo", "flow8_alias_set", "flow8_alias_list",
                        "hotkeys_apply_slot", "hotkeys_list_slots"}
            missing = expected - set(names)
            print("누락 도구:", missing or "없음")
            return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
