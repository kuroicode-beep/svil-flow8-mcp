# C:\Projects\svil-flow8-mcp\flow8core\controller.py
# 고수준 API — 사용자 표현을 검증해 MIDI 바이트로 바꾸고, 보낸 뒤 섀도 상태에 기록한다.
from __future__ import annotations

from typing import Any

from . import mapping as M
from .midi import Flow8PortError, MidiSink, RtmidiSink, cc, note_on, program_change
from .state import Aliases, ShadowState

RESET_CONFIRM_WORD = "초기화"


class Flow8Error(ValueError):
    """사용자 입력 오류 — 메시지가 그대로 안내문이 된다."""


class Flow8Controller:
    """sink를 주면 그리로 보내고(테스트), 없으면 실제 포트를 보낼 때만 연다."""

    def __init__(self, sink: MidiSink | None = None) -> None:
        self._sink = sink
        self.state = ShadowState()
        self.aliases = Aliases()

    # ── 전송 ──
    def _send_all(self, messages: list[bytes]) -> None:
        if self._sink is not None:
            for m in messages:
                self._sink.send(m)
            return
        with RtmidiSink() as sink:
            for m in messages:
                sink.send(m)

    def _commit(self, messages: list[bytes], summary: str) -> str:
        self._send_all(messages)
        self.state.note(summary)
        self.state.save()
        return summary

    # ── 스냅샷 ──
    def load_snapshot(self, which: int | str) -> str:
        n = self._resolve_snapshot(which)
        msg = program_change(M.GLOBAL_CH, n)
        self.state.data["last_snapshot"] = n
        name = self.aliases.snapshot_name(n)
        label = f"{n}번" + (f"({name})" if name else "")
        return self._commit([msg], f"스냅샷 {label} 불러옴")

    def _resolve_snapshot(self, which: int | str) -> int:
        if isinstance(which, str) and not which.strip().isdigit():
            n = self.aliases.snapshot_by_name(which)
            if n is None:
                raise Flow8Error(f"스냅샷 이름을 모르겠어요: {which} (1~15 번호나 등록한 별칭)")
        else:
            n = int(str(which).strip())
        if not 1 <= n <= M.SNAPSHOT_MAX:
            raise Flow8Error(f"스냅샷 번호는 1~{M.SNAPSHOT_MAX}만 돼요 (받은 값: {n}). 16번 공장초기화는 이 도구로 보내지 않아요.")
        return n

    def reset_factory(self, confirm: str) -> str:
        if confirm.strip() != RESET_CONFIRM_WORD:
            raise Flow8Error(f"공장초기화는 confirm 인자에 정확히 '{RESET_CONFIRM_WORD}'를 넣어야 실행돼요. 아무것도 보내지 않았어요.")
        self.state.data["last_snapshot"] = None
        return self._commit([program_change(M.GLOBAL_CH, M.RESET_PROGRAM)], "공장초기화 명령 전송(PC16)")

    def tap_tempo(self) -> str:
        return self._commit([note_on(M.GLOBAL_CH, 0, 127)], "탭 템포 1회")

    # ── 채널 ──
    def set_channel(self, channel: str | int, **fields: Any) -> str:
        ch = self._channel(channel)
        msgs: list[bytes] = []
        parts: list[str] = []
        for field, raw in fields.items():
            if raw is None:
                continue
            if field not in M.CHANNEL_CC:
                raise Flow8Error(f"채널 항목을 모르겠어요: {field}")
            if field in M.GAIN_ONLY_FIELDS and not ch.has_gain:
                raise Flow8Error(f"{ch.label} 채널에는 {field}가 없어요 (USB/BT 채널은 게인·컴프·로우컷 없음)")
            if field in ("mute", "solo"):
                on = self._to_bool(raw)
                value = 0 if on else 127          # 반전 규격: 127=해제
                self.state.set_channel(ch.idx, field, on)
                parts.append(f"{field} {'켬' if on else '해제'}")
            else:
                value = self._cc(raw)
                self.state.set_channel(ch.idx, field, value)
                parts.append(f"{field}={value}")
            msgs.append(cc(ch.idx, M.CHANNEL_CC[field], value))
        if not msgs:
            raise Flow8Error("바꿀 항목이 없어요 (level, gain, mute … 중 하나 이상)")
        return self._commit(msgs, f"{ch.label}: " + ", ".join(parts))

    def mute(self, channel: str | int, on: bool = True) -> str:
        return self.set_channel(channel, mute=on)

    def solo(self, channel: str | int, on: bool = True) -> str:
        return self.set_channel(channel, solo=on)

    # ── 버스 ──
    def set_bus(self, bus: str, eq: list[Any] | None = None, **fields: Any) -> str:
        key, midi_ch, label = self._bus(bus)
        msgs: list[bytes] = []
        parts: list[str] = []
        for field, raw in fields.items():
            if raw is None:
                continue
            if field not in M.BUS_CC:
                raise Flow8Error(f"버스 항목을 모르겠어요: {field} (level·balance·limiter·eq)")
            value = self._cc(raw)
            self.state.set_bus(key, field, value)
            msgs.append(cc(midi_ch, M.BUS_CC[field], value))
            parts.append(f"{field}={value}")
        if eq is not None:
            if len(eq) != M.BUS_EQ_BANDS:
                raise Flow8Error(f"버스 EQ는 밴드 {M.BUS_EQ_BANDS}개 값을 순서대로 주세요 (받은 개수: {len(eq)})")
            vals = [self._cc(v) for v in eq]
            for band, v in enumerate(vals):
                msgs.append(cc(midi_ch, M.BUS_EQ_BASE_CC + band, v))
            self.state.set_bus(key, "eq", vals)
            parts.append("eq 9밴드")
        if not msgs:
            raise Flow8Error("바꿀 항목이 없어요 (level, balance, limiter, eq)")
        return self._commit(msgs, f"{label}: " + ", ".join(parts))

    # ── FX ──
    def set_fx(self, slot: str | int, preset: int | None = None, param1: Any = None, param2: Any = None) -> str:
        s = str(slot).strip().lower()
        if s not in M.FX_SLOTS:
            raise Flow8Error(f"FX 슬롯은 1 또는 2예요 (받은 값: {slot})")
        fx_id = M.FX_SLOTS[s]
        midi_ch = M.FX_CTRL_BASE + fx_id
        msgs: list[bytes] = []
        parts: list[str] = []
        if preset is not None:
            p = int(preset)
            if not 1 <= p <= 127:
                raise Flow8Error("FX 프리셋 번호는 1 이상이어야 해요")
            msgs.append(program_change(midi_ch, p))
            self.state.set_fx(f"fx{fx_id + 1}", "preset", p)
            parts.append(f"preset={p}")
        for name, raw in (("param1", param1), ("param2", param2)):
            if raw is None:
                continue
            v = self._cc(raw)
            msgs.append(cc(midi_ch, M.FX_PARAM_CC[name], v))
            self.state.set_fx(f"fx{fx_id + 1}", name, v)
            parts.append(f"{name}={v}")
        if not msgs:
            raise Flow8Error("바꿀 항목이 없어요 (preset, param1, param2)")
        return self._commit(msgs, f"FX{fx_id + 1}: " + ", ".join(parts))

    # ── 조회 ──
    def status(self) -> dict[str, Any]:
        d = self.state.data
        last = d.get("last_snapshot")
        return {
            "기준": "믹서는 상태를 돌려주지 않아요 — 아래는 이 PC에서 마지막으로 보낸 값이에요",
            "마지막_스냅샷": (f"{last}번" + (f"({self.aliases.snapshot_name(last)})" if last and self.aliases.snapshot_name(last) else "")) if last else "이 PC에서 보낸 기록 없음",
            "채널": {M.CHANNELS[int(k)].label: v for k, v in d.get("channels", {}).items()},
            "버스": d.get("buses", {}),
            "fx": d.get("fx", {}),
            "갱신": d.get("updated_at"),
            "최근_이력": d.get("history", [])[-5:],
        }

    def port_check(self) -> str:
        try:
            with RtmidiSink():
                pass
            return "FLOW 8 MIDI OUT 포트 열림·닫힘 정상"
        except Flow8PortError as exc:
            return str(exc)

    # ── 도우미 ──
    def _channel(self, channel: str | int) -> M.Channel:
        try:
            return M.resolve_channel(channel, self.aliases.channel_aliases())
        except KeyError as exc:
            raise Flow8Error(str(exc)) from exc

    def _bus(self, bus: str) -> tuple[str, int, str]:
        try:
            return M.resolve_bus(bus)
        except KeyError as exc:
            raise Flow8Error(str(exc)) from exc

    @staticmethod
    def _cc(raw: Any) -> int:
        try:
            return M.to_cc(raw)
        except ValueError as exc:
            raise Flow8Error(str(exc)) from exc

    @staticmethod
    def _to_bool(raw: Any) -> bool:
        if isinstance(raw, bool):
            return raw
        s = str(raw).strip().lower()
        if s in ("1", "true", "on", "켜", "켬", "yes", "y", "뮤트"):
            return True
        if s in ("0", "false", "off", "꺼", "해제", "no", "n"):
            return False
        raise Flow8Error(f"켜기/끄기 값을 모르겠어요: {raw}")
