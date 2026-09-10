# C:\Projects\svil-flow8-mcp\tools\ble_diag2.py — 페어링·CCCD 직접 쓰기·읽기 특성·인증 후 유지 여부 진단 (설정 변경 없음)
import asyncio, sys
from bleak import BleakClient, BleakScanner
sys.stdout.reconfigure(encoding="utf-8")
SVC = "14839ad4-8d7e-415c-9a42-167340cf2339"; CH = "0034594a-a8e7-4b1a-a6b1-cd5243059a57"
R1 = "0035594a-a8e7-4b1a-a6b1-cd5243059a57"; R2 = "0036594a-a8e7-4b1a-a6b1-cd5243059a57"
AUTH = bytes.fromhex("3901fd062b0639f17fe7b7278b8f355a495c2a"); SESSION = bytes([0x37,1,0x38])
async def main():
    dev = await BleakScanner.find_device_by_filter(lambda d, ad: SVC in [u.lower() for u in (ad.service_uuids or [])] or "FLOW" in (d.name or "").upper(), timeout=12)
    print("장치:", dev.address if dev else None)
    if not dev: return
    notes = []
    async with BleakClient(dev, timeout=15) as c:
        for u in (R1, R2):
            try: v = await c.read_gatt_char(u); print(f"읽기 {u[:8]}: {bytes(v).hex(' ')} | {bytes(v)!r}")
            except Exception as e: print(f"읽기 {u[:8]} 실패:", repr(e)[:120])
        try:
            print("페어링 시도…"); print("pair():", await c.pair())
        except Exception as e: print("pair 실패:", repr(e)[:160])
        print("연결:", c.is_connected)
        ch = c.services.get_characteristic(CH)
        for d in ch.descriptors: print("  디스크립터", d.uuid, "handle", d.handle)
        cccd = next((d for d in ch.descriptors if d.uuid.startswith("00002902")), None)
        if cccd:
            try: await c.write_gatt_descriptor(cccd.handle, b"\x01\x00"); print("CCCD 직접 쓰기: OK")
            except Exception as e: print("CCCD 직접 쓰기 실패:", repr(e)[:160])
        try:
            await c.start_notify(CH, lambda h, d: (notes.append(bytes(d)), print("  알림:", bytes(d).hex(" ")))); print("start_notify: OK")
        except Exception as e: print("start_notify 실패:", repr(e)[:160])
        await asyncio.sleep(1.5)
        print("인증 전 알림 수:", len(notes), "| 연결:", c.is_connected)
        if c.is_connected:
            try:
                await c.write_gatt_char(CH, AUTH, response=False); print("인증 쓰기 OK")
                for i in range(6):
                    await asyncio.sleep(0.5)
                    if not c.is_connected: print(f"  {0.5*(i+1)}s 후 연결 끊김"); break
                print("인증 후 알림 수:", len(notes), "| 연결:", c.is_connected)
                if c.is_connected:
                    await c.write_gatt_char(CH, SESSION, response=False); await asyncio.sleep(2)
                    print("세션시작 후 알림 수:", len(notes), "| 연결:", c.is_connected)
            except Exception as e: print("쓰기 실패:", repr(e)[:160])
asyncio.run(main())
