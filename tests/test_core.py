# C:\Projects\svil-flow8-mcp\tests\test_core.py — 스텁 포트로 전송 바이트를 매핑표와 1:1 대조 (믹서 불필요)
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["SVIL_FLOW8_DIR"] = tempfile.mkdtemp(prefix="flow8test_")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from flow8core.controller import Flow8Controller, Flow8Error  # noqa: E402
from flow8core.midi import StubSink  # noqa: E402


@pytest.fixture
def ctl():
    sink = StubSink()
    c = Flow8Controller(sink=sink)
    return c, sink


def test_snapshot_bytes(ctl):
    c, s = ctl
    c.load_snapshot(3)
    assert s.sent == [bytes([0xCF, 3])]
    c.load_snapshot("15")
    assert s.sent[-1] == bytes([0xCF, 15])
    assert c.state.data["last_snapshot"] == 15


@pytest.mark.parametrize("bad", [0, 16, 99, -1])
def test_snapshot_rejects_out_of_range(ctl, bad):
    c, s = ctl
    with pytest.raises(Flow8Error):
        c.load_snapshot(bad)
    assert s.sent == []


def test_snapshot_alias(ctl):
    c, s = ctl
    c.aliases.set_snapshot(3, "노래방")
    c.load_snapshot("노래방")
    assert s.sent == [bytes([0xCF, 3])]
    with pytest.raises(Flow8Error):
        c.load_snapshot("없는이름")


def test_reset_requires_confirm(ctl):
    c, s = ctl
    with pytest.raises(Flow8Error):
        c.reset_factory("")
    with pytest.raises(Flow8Error):
        c.reset_factory("reset")
    assert s.sent == []
    c.reset_factory("초기화")
    assert s.sent == [bytes([0xCF, 16])]


def test_mute_solo_inverted(ctl):
    c, s = ctl
    c.mute("1", True)
    c.mute("1", False)
    c.solo("5/6", True)
    assert s.sent == [bytes([0xB0, 5, 0]), bytes([0xB0, 5, 127]), bytes([0xB4, 6, 0])]


def test_channel_values_and_percent(ctl):
    c, s = ctl
    c.set_channel("2", level="60%", gain=40, balance="50%")
    assert s.sent == [bytes([0xB1, 7, 76]), bytes([0xB1, 8, 40]), bytes([0xB1, 10, 64])]


def test_channel_rejects(ctl):
    c, s = ctl
    with pytest.raises(Flow8Error):
        c.set_channel("usb", gain=10)          # USB/BT 채널엔 게인 없음
    with pytest.raises(Flow8Error):
        c.set_channel("1", level=128)
    with pytest.raises(Flow8Error):
        c.set_channel("9", level=1)
    with pytest.raises(Flow8Error):
        c.set_channel("1")
    assert s.sent == []


def test_channel_all_cc_numbers(ctl):
    c, s = ctl
    c.set_channel("3", eq_low=1, eq_lowmid=2, eq_himid=3, eq_hi=4, lowcut=9, comp=11,
                  send_mon1=14, send_mon2=15, send_fx1=16, send_fx2=17)
    ccs = [m[1] for m in s.sent]
    assert ccs == [1, 2, 3, 4, 9, 11, 14, 15, 16, 17]
    assert all(m[0] == 0xB2 for m in s.sent)


def test_bus_and_eq(ctl):
    c, s = ctl
    c.set_bus("main", level=100, limiter="0%", balance=64)
    assert s.sent == [bytes([0xB7, 7, 100]), bytes([0xB7, 8, 0]), bytes([0xB7, 10, 64])]
    s.sent.clear()
    c.set_bus("mon2", eq=[64] * 9)
    assert [m[1] for m in s.sent] == list(range(11, 20)) and all(m[0] == 0xB9 for m in s.sent)
    with pytest.raises(Flow8Error):
        c.set_bus("mon1", eq=[64] * 8)
    with pytest.raises(Flow8Error):
        c.set_bus("없음", level=1)


def test_fx_and_tap(ctl):
    c, s = ctl
    c.set_fx(2, preset=3, param1="50%")
    assert s.sent == [bytes([0xCE, 3]), bytes([0xBE, 1, 64])]
    s.sent.clear()
    c.set_fx("fx1", param2=127)
    assert s.sent == [bytes([0xBD, 2, 127])]
    s.sent.clear()
    c.tap_tempo()
    assert s.sent == [bytes([0x9F, 0, 127])]


def test_state_persists_and_reloads(ctl):
    c, s = ctl
    c.set_channel("1", level=77)
    c.load_snapshot(5)
    again = Flow8Controller(sink=StubSink())
    assert again.state.data["last_snapshot"] == 5
    assert again.state.data["channels"]["0"]["level"] == 77
    assert again.status()["마지막_스냅샷"] == "5번"


# nudge: 기록 없으면 0에서, 0~127 고정, 뮤트·솔로는 거부, 보낸 바이트는 CC16(send_fx1)
def test_nudge_relative(ctl):
    c, s = ctl
    assert c.nudge("1", "send_fx1", 8) == 8
    assert c.nudge("1", "send_fx1", 8) == 16
    assert s.sent[-1] == bytes([0xB0, 16, 16])
    assert c.nudge("1", "send_fx1", -100) == 0
    assert c.nudge("1", "level", 200) == 127
    with pytest.raises(Flow8Error):
        c.nudge("1", "mute", 1)
    with pytest.raises(Flow8Error):
        c.nudge("1", "없음", 1)


# record/restore: 스냅샷을 기억해 두면 불러올 때 섀도가 그 값으로 돌아와 nudge 기준이 맞는다
def test_snapshot_record_and_restore(ctl):
    c, s = ctl
    c.set_channel("1", send_fx1=44, level=70)
    c.record_snapshot(3)
    c.set_channel("1", send_fx1=10)
    c.record_snapshot(2)
    assert "기억된 값 없음" in c.load_snapshot(4)
    assert "기억된 값 없음" not in c.load_snapshot(3)
    assert c.get_value("1", "send_fx1") == 44
    assert c.nudge("1", "send_fx1", 8) == 52
    c.load_snapshot(2)
    assert c.get_value("1", "send_fx1") == 10
    again = Flow8Controller(sink=StubSink())
    assert again.state.snapshot_values(3)["channels"]["0"]["send_fx1"] == 44


# ── 여러 프로세스가 같은 state.json을 쓸 때 서로 지우지 않는다 (2026-09-23 유실 사고) ──
# 재현: 컨트롤러 A(오래 떠 있는 MCP 서버)가 먼저 파일을 읽어 두고, 그 사이 컨트롤러 B
# (일회성 스크립트)가 스냅샷을 기억시킨 뒤, A가 나중에 저장한다. 합쳐 쓰지 않으면
# A의 낡은 메모리가 B의 기록을 통째로 덮어써서 「기억된 값 없음」이 된다.
def test_save_merges_other_process_snapshots():
    server = Flow8Controller(sink=StubSink())      # 세션 시작 때 떠서 계속 들고 있는 쪽
    server.set_channel("1", level=10)

    script = Flow8Controller(sink=StubSink())      # 나중에 뜬 일회성 스크립트
    script.set_channel("1", level=70, send_fx1=10)
    script.record_snapshot(4)
    assert script.state.snapshot_values(4) is not None

    server.load_snapshot(1)                        # 여기서 server가 저장한다

    after = Flow8Controller(sink=StubSink())
    assert after.state.snapshot_values(4) is not None, "다른 프로세스가 기억시킨 스냅샷이 지워졌다"
    assert after.state.snapshot_values(4)["channels"]["0"]["level"] == 70


def test_save_keeps_both_histories():
    a = Flow8Controller(sink=StubSink())
    b = Flow8Controller(sink=StubSink())
    a.tap_tempo()
    b.tap_tempo()
    a.tap_tempo()
    hist = [h["what"] for h in Flow8Controller(sink=StubSink()).state.data["history"]]
    assert hist.count("탭 템포 1회") >= 3, "두 프로세스의 이력이 합쳐지지 않았다"


def test_save_does_not_duplicate_own_history():
    c = Flow8Controller(sink=StubSink())
    before = len(Flow8Controller(sink=StubSink()).state.data["history"])
    c.tap_tempo()
    c.tap_tempo()
    after = len(Flow8Controller(sink=StubSink()).state.data["history"])
    assert after - before == 2, f"같은 줄이 다시 붙었다({after - before}줄)"


def test_alias_save_merges():
    a = Flow8Controller(sink=StubSink())
    b = Flow8Controller(sink=StubSink())
    a.aliases.set_snapshot(7, "가")
    a.aliases.save()
    b.aliases.set_snapshot(8, "나")
    b.aliases.save()
    fresh = Flow8Controller(sink=StubSink())
    assert fresh.aliases.snapshot_name(7) == "가"
    assert fresh.aliases.snapshot_name(8) == "나"


# 별칭은 「바꾼 인스턴스」가 저장해야 남는다. server.py가 도구 호출마다 컨트롤러를
# 새로 만들도록 바꾸면서 실제로 걸린 함정 — set과 save가 서로 다른 인스턴스였다.
def test_alias_set_and_save_need_same_instance():
    c = Flow8Controller(sink=StubSink())
    c.aliases.set_snapshot(9, "같은인스턴스")
    c.aliases.save()
    assert Flow8Controller(sink=StubSink()).aliases.snapshot_name(9) == "같은인스턴스"

    a = Flow8Controller(sink=StubSink())
    b = Flow8Controller(sink=StubSink())
    a.aliases.set_snapshot(10, "사라질별칭")
    b.aliases.save()
    assert Flow8Controller(sink=StubSink()).aliases.snapshot_name(10) is None
