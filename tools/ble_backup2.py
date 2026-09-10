# C:\Projects\svil-flow8-mcp\tools\ble_backup2.py — 본딩 제거 → 새 연결 → CCCD 직접 활성화(결과코드 확인) → 인증/세션/이름/덤프 → USB SysEx 저장
import asyncio, json, os, sys, time
from datetime import datetime
from pathlib import Path
import rtmidi
from bleak import BleakClient, BleakScanner
from winrt.windows.devices.bluetooth import BluetoothLEDevice
from winrt.windows.devices.bluetooth.genericattributeprofile import GattClientCharacteristicConfigurationDescriptorValue as CCCDV
sys.stdout.reconfigure(encoding="utf-8")
SVC="14839ad4-8d7e-415c-9a42-167340cf2339"; CH="0034594a-a8e7-4b1a-a6b1-cd5243059a57"; ADDR=0xC7F35C0BC422
AUTH=bytes.fromhex("3901fd062b0639f17fe7b7278b8f355a495c2a"); SESSION=bytes([0x37,1,0x38]); CONFIG=bytes([0x07,1,0x08]); DUMP=bytes([0x4B,1,0x4C])
HDR=bytes([0xF0,0x00,0x20,0x32,0x21]); OUT=Path(os.environ["LOCALAPPDATA"])/"svil-flow8"/"backups"
def names_from(b):
    out=[]; p=b[2:-1]; i=0
    while i<len(p):
        n=p[i]; i+=1
        if n==0 or i+n>len(p): break
        out.append(p[i:i+n].decode("utf-8","replace").strip()); i+=n
    return out
async def main():
    # 1) 낡은 본딩 제거
    d=await BluetoothLEDevice.from_bluetooth_address_async(ADDR)
    if d and d.device_information.pairing.is_paired:
        r=await d.device_information.pairing.unpair_async(); print("본딩 제거:", r.status)
    else: print("본딩 없음")
    mi=rtmidi.MidiIn(); mi.open_port([k for k,n in enumerate(mi.get_ports()) if "FLOW 8" in n][0]); mi.ignore_types(sysex=False)
    dev=await BleakScanner.find_device_by_filter(lambda x,ad: SVC in [u.lower() for u in (ad.service_uuids or [])], timeout=12)
    print("장치:", dev.address if dev else None)
    if not dev: mi.close_port(); return 2
    notes=[]; names=[]
    def cb(h,data):
        b=bytes(data); notes.append(b); print("  알림:", b[:24].hex(" "), "…" if len(b)>24 else "")
        if b and b[0]==0x27: names[:]=names_from(b)
    async with BleakClient(dev, timeout=15, winrt=dict(use_cached_services=False)) as c:
        print("연결:", c.is_connected)
        ch=c.services.get_characteristic(CH)
        # 2) CCCD 직접 활성화 — 실제 GATT 상태코드 확인
        try:
            res=await ch.obj.write_client_characteristic_configuration_descriptor_with_result_async(CCCDV.NOTIFY)
            print("CCCD(Notify) 결과:", res.status, "| 프로토콜 오류:", res.protocol_error)
        except Exception as e: print("CCCD 호출 예외:", repr(e)[:160])
        try: await c.start_notify(CH, cb); print("start_notify: OK")
        except Exception as e: print("start_notify 실패:", repr(e)[:120])
        await asyncio.sleep(1.5); print("인증 전 알림:", len(notes), "| 연결:", c.is_connected)
        await c.write_gatt_char(CH, AUTH, response=False); print("인증 쓰기")
        for _ in range(6):
            await asyncio.sleep(0.5)
            if any(n[:3]==bytes([0x36,1,0x37]) for n in notes) or not c.is_connected: break
        print("인증 후 알림:", len(notes), "| 연결:", c.is_connected)
        if not c.is_connected:
            mi.close_port(); print("→ 인증 직후 끊김: 폰 FLOW Mix 앱이 믹서에 연결돼 있는지 확인(앱 종료 또는 폰 블루투스 끄기)"); return 3
        await c.write_gatt_char(CH, SESSION, response=False); await asyncio.sleep(2.5); print("세션 후 알림:", len(notes))
        await c.write_gatt_char(CH, CONFIG, response=False); await asyncio.sleep(2.0)
        if names: print("스냅샷 이름:", ", ".join(f"{i+1}={n or '(빈칸)'}" for i,n in enumerate(names)))
        await c.write_gatt_char(CH, DUMP, response=False); print("덤프 요청 — USB 대기 25초")
        dump=None; t=time.time()+25
        while time.time()<t:
            m=mi.get_message()
            if m and bytes(m[0]).startswith(HDR) and len(m[0])>=100: dump=bytes(m[0]); break
            await asyncio.sleep(0.02)
    mi.close_port(); OUT.mkdir(parents=True, exist_ok=True)
    base=OUT/f"{datetime.now():%Y%m%d_%H%M}_latest"
    meta={"captured_at":datetime.now().isoformat(timespec="seconds"),"device":dev.address,"snapshot_names":names,"ble_notifications":[n.hex(" ") for n in notes],"sysex":None}
    if dump:
        base.with_suffix(".syx").write_bytes(dump); meta["sysex"]={"size":len(dump),"header_hex":dump[:12].hex(" "),"ends_with_f7":dump[-1]==0xF7}
        print(f"저장 완료: {base.with_suffix('.syx')} ({len(dump)} bytes)")
    else: print("USB 덤프 미수신")
    base.with_suffix(".json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8"); print("메타:", base.with_suffix(".json"))
    return 0 if dump else 1
sys.exit(asyncio.run(main()))
