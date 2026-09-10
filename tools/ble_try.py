# ble_try.py — 연결 유지·덤프 수신을 위한 4가지 시도(설정 변경 없음): A 암호화 페어링 후 구독·인증 / B 인증 없이 덤프요청 / C 세션+덤프요청 / D 응답요구 쓰기 관찰
import asyncio, sys, time
import rtmidi
from bleak import BleakClient, BleakScanner
from winrt.windows.devices.bluetooth import BluetoothLEDevice
from winrt.windows.devices.enumeration import DevicePairingKinds, DevicePairingProtectionLevel
from winrt.windows.devices.bluetooth.genericattributeprofile import GattClientCharacteristicConfigurationDescriptorValue as CCCDV
sys.stdout.reconfigure(encoding="utf-8")
SVC="14839ad4-8d7e-415c-9a42-167340cf2339"; CH="0034594a-a8e7-4b1a-a6b1-cd5243059a57"; ADDR=0xC7F35C0BC422
AUTH=bytes.fromhex("3901fd062b0639f17fe7b7278b8f355a495c2a"); SESSION=bytes([0x37,1,0x38]); DUMP=bytes([0x4B,1,0x4C]); HDR=bytes([0xF0,0,0x20,0x32,0x21])
mi=rtmidi.MidiIn(); mi.open_port([k for k,n in enumerate(mi.get_ports()) if "FLOW 8" in n][0]); mi.ignore_types(sysex=False)
def usb_wait(sec):
    t=time.time()+sec
    while time.time()<t:
        m=mi.get_message()
        if m and bytes(m[0])[:1]==b"\xf0": return bytes(m[0])
        time.sleep(0.02)
    return None
async def find():
    return await BleakScanner.find_device_by_filter(lambda x,ad: SVC in [u.lower() for u in (ad.service_uuids or [])], timeout=12)
async def alive(c, sec):
    for i in range(int(sec*4)):
        await asyncio.sleep(0.25)
        if not c.is_connected: return round((i+1)*0.25,2)
    return None
async def try_A():
    print("\n[A] 암호화 페어링 → CCCD → 인증")
    d=await BluetoothLEDevice.from_bluetooth_address_async(ADDR)
    p=d.device_information.pairing
    if p.is_paired: print("  기존 본딩 제거:", (await p.unpair_async()).status)
    custom=p.custom; tok=custom.add_pairing_requested(lambda s,a: (print("  페어링 요청:", a.pairing_kind), a.accept()))
    r=await custom.pair_async(DevicePairingKinds.CONFIRM_ONLY|DevicePairingKinds.CONFIRM_PIN_MATCH|DevicePairingKinds.DISPLAY_PIN, DevicePairingProtectionLevel.ENCRYPTION)
    custom.remove_pairing_requested(tok); print("  pair 결과:", r.status, "| 보호수준:", r.protection_level_used)
    dev=await find()
    if not dev: print("  스캔 실패"); return
    async with BleakClient(dev, timeout=15, winrt=dict(use_cached_services=False)) as c:
        ch=c.services.get_characteristic(CH)
        res=await ch.obj.write_client_characteristic_configuration_descriptor_with_result_async(CCCDV.NOTIFY)
        print("  CCCD:", res.status, "/ 오류", res.protocol_error)
        await c.write_gatt_char(CH, AUTH, response=False); print("  인증 쓰기 후 끊김:", await alive(c,3), "초")
async def try_B():
    print("\n[B] 인증 없이 덤프요청만")
    dev=await find()
    async with BleakClient(dev, timeout=15) as c:
        await c.write_gatt_char(CH, DUMP, response=False); d=usb_wait(8); print("  USB 덤프:", (len(d) if d else None), "| 끊김:", await alive(c,1))
async def try_C():
    print("\n[C] 세션시작 → 덤프요청 (인증 없이)")
    dev=await find()
    async with BleakClient(dev, timeout=15) as c:
        await c.write_gatt_char(CH, SESSION, response=False); await asyncio.sleep(0.5); print("  세션 후 끊김:", await alive(c,1))
        if c.is_connected:
            await c.write_gatt_char(CH, DUMP, response=False); d=usb_wait(8); print("  USB 덤프:", (len(d) if d else None))
async def try_D():
    print("\n[D] 인증을 응답요구(WithResponse)로")
    dev=await find()
    async with BleakClient(dev, timeout=15) as c:
        t=time.time()
        try: await c.write_gatt_char(CH, AUTH, response=True); print(f"  응답 OK ({time.time()-t:.2f}s)")
        except Exception as e: print(f"  실패 ({time.time()-t:.2f}s):", repr(e)[:120])
        print("  끊김:", await alive(c,2))
async def main():
    for f in (try_A, try_B, try_C, try_D):
        try: await f()
        except Exception as e: print("  예외:", repr(e)[:160])
        await asyncio.sleep(1.5)
    mi.close_port()
asyncio.run(main())
