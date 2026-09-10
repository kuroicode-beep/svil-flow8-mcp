# ble_desc.py — 특성의 디스크립터를 WinRT로 직접 열거하고, 0x2902(CCCD) 유무·핸들·읽기값을 본다 (변경 없음)
import asyncio, sys
from bleak import BleakClient, BleakScanner
from winrt.windows.devices.bluetooth import BluetoothCacheMode
sys.stdout.reconfigure(encoding="utf-8")
SVC="14839ad4-8d7e-415c-9a42-167340cf2339"; CH="0034594a-a8e7-4b1a-a6b1-cd5243059a57"
async def main():
    dev=await BleakScanner.find_device_by_filter(lambda x,ad: SVC in [u.lower() for u in (ad.service_uuids or [])], timeout=12)
    if not dev: print("장치 없음"); return
    async with BleakClient(dev, timeout=15, winrt=dict(use_cached_services=False)) as c:
        ch=c.services.get_characteristic(CH)
        print("특성 핸들:", ch.handle, "| props:", ch.properties)
        r=await ch.obj.get_descriptors_with_cache_mode_async(BluetoothCacheMode.UNCACHED)
        print("디스크립터 조회 상태:", r.status, "| 개수:", r.descriptors.size)
        for d in r.descriptors:
            print("  desc uuid", d.uuid, "handle", d.attribute_handle)
            try:
                rv=await d.read_value_async(); b=bytes(rv.value) if rv.value else b""; print("     값:", b.hex(" "), "| 상태:", rv.status)
            except Exception as e: print("     읽기 실패:", repr(e)[:100])
        # 서비스 내 모든 특성 핸들 (CCCD가 0x000b인지 확인)
        for s in c.services:
            if s.uuid.startswith("14839ad4"):
                for x in s.characteristics: print("  char", x.uuid[:8], "handle", x.handle, x.properties)
asyncio.run(main())
