# C:\Projects\svil-flow8-mcp\tools\ble_diag.py — FLOW 8 BLE 진단: 특성 속성, 구독, 쓰기 방식별 결과 (설정 변경 없음)
import asyncio, sys
from bleak import BleakClient, BleakScanner
sys.stdout.reconfigure(encoding="utf-8")
SVC = "14839ad4-8d7e-415c-9a42-167340cf2339"; CH = "0034594a-a8e7-4b1a-a6b1-cd5243059a57"
AUTH = bytes.fromhex("3901fd062b0639f17fe7b7278b8f355a495c2a")
async def main():
    dev = await BleakScanner.find_device_by_filter(lambda d, ad: "FLOW" in (d.name or "").upper() or SVC in [u.lower() for u in (ad.service_uuids or [])], timeout=12)
    print("장치:", dev.name if dev else None, dev.address if dev else "")
    if not dev: return
    notes = []
    async with BleakClient(dev, timeout=15) as c:
        print("연결:", c.is_connected, "| MTU:", getattr(c, "mtu_size", "?"))
        for s in c.services:
            print("서비스", s.uuid)
            for ch in s.characteristics:
                print("   특성", ch.uuid, ch.properties, "handle", ch.handle)
        try:
            await c.start_notify(CH, lambda h, d: (notes.append(bytes(d)), print("  알림:", bytes(d).hex(" "))))
            print("구독: OK"); await asyncio.sleep(2.0)
        except Exception as e: print("구독 실패:", repr(e))
        for resp in (False, True):
            try:
                await c.write_gatt_char(CH, AUTH, response=resp); print(f"쓰기(response={resp}): OK"); await asyncio.sleep(1.5); break
            except Exception as e: print(f"쓰기(response={resp}) 실패:", repr(e)[:160])
        print("연결 유지:", c.is_connected, "| 알림 수:", len(notes))
        if not notes and not c.is_connected: print("→ 쓰기 직후 연결이 끊김 (페어링/암호화 요구 가능성)")
        if c.is_connected and not any(n[:3]==bytes([0x36,1,0x37]) for n in notes):
            try:
                print("페어링 시도…"); ok = await c.pair(); print("pair():", ok)
                await c.write_gatt_char(CH, AUTH, response=True); await asyncio.sleep(1.5)
                print("페어링 후 알림 수:", len(notes))
            except Exception as e: print("페어링/재쓰기 실패:", repr(e)[:160])
asyncio.run(main())
