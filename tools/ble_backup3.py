# ble_backup3.py — 암호화 수준으로 페어링(본딩) → 연결 → 구독 시도 → 인증 → 세션 → 이름 → 덤프요청 → USB SysEx 저장 (설정 변경 없음)
import asyncio, json, os, sys, time
from datetime import datetime
from pathlib import Path
import rtmidi
from bleak import BleakClient, BleakScanner
from winrt.windows.devices.bluetooth import BluetoothLEDevice
from winrt.windows.devices.enumeration import DevicePairingKinds, DevicePairingProtectionLevel
from winrt.windows.devices.bluetooth.genericattributeprofile import GattClientCharacteristicConfigurationDescriptorValue as CCCDV
sys.stdout.reconfigure(encoding="utf-8")
SVC="14839ad4-8d7e-415c-9a42-167340cf2339"; CH="0034594a-a8e7-4b1a-a6b1-cd5243059a57"; ADDR=0xC7F35C0BC422
AUTH=bytes.fromhex("3901fd062b0639f17fe7b7278b8f355a495c2a"); SESSION=bytes([0x37,1,0x38]); CONFIG=bytes([0x07,1,0x08]); DUMP=bytes([0x4B,1,0x4C])
HDR=bytes([0xF0,0,0x20,0x32,0x21]); OUT=Path(os.environ["LOCALAPPDATA"])/"svil-flow8"/"backups"
STATUS={0:"Paired",1:"NotReadyToPair",2:"NotPaired",3:"AlreadyPaired",4:"ConnectionRejected",5:"TooManyConnections",6:"HardwareFailure",7:"AuthenticationTimeout",8:"AuthenticationNotAllowed",9:"AuthenticationFailure",10:"NoSupportedProfiles",11:"ProtectionLevelCouldNotBeMet",12:"AccessDenied",13:"InvalidCeremonyData",14:"PairingCanceled",15:"OperationAlreadyInProgress",16:"RequiredHandlerNotRegistered",17:"RejectedByHandler",18:"RemoteDeviceHasAssociation",19:"Failed"}
def names_from(b):
    out=[]; p=b[2:-1]; i=0
    while i<len(p):
        n=p[i]; i+=1
        if n==0 or i+n>len(p): break
        out.append(p[i:i+n].decode("utf-8","replace").strip()); i+=n
    return out
async def pair_encrypted():
    d=await BluetoothLEDevice.from_bluetooth_address_async(ADDR)
    p=d.device_information.pairing
    print("현재 is_paired:", p.is_paired, "| 보호수준:", p.protection_level)
    if p.is_paired and p.protection_level>=2: print("이미 암호화 본딩 있음"); return True
    if p.is_paired: print("낡은 본딩 제거:", (await p.unpair_async()).status)
    custom=p.custom
    tok=custom.add_pairing_requested(lambda s,a: (print("  페어링 요청 종류:", int(a.pairing_kind)), a.accept()))
    kinds=DevicePairingKinds.CONFIRM_ONLY|DevicePairingKinds.CONFIRM_PIN_MATCH|DevicePairingKinds.DISPLAY_PIN|DevicePairingKinds.PROVIDE_PIN
    try:
        r=await custom.pair_with_protection_level_async(kinds, DevicePairingProtectionLevel.ENCRYPTION)
    except AttributeError:
        r=await custom.pair_async(kinds)
    finally:
        custom.remove_pairing_requested(tok)
    st=int(r.status); print("페어링 결과:", st, STATUS.get(st,"?"), "| 사용된 보호수준:", int(r.protection_level_used))
    return st in (0,3)
async def main():
    ok=await pair_encrypted()
    mi=rtmidi.MidiIn(); mi.open_port([k for k,n in enumerate(mi.get_ports()) if "FLOW 8" in n][0]); mi.ignore_types(sysex=False)
    dev=await BleakScanner.find_device_by_filter(lambda x,ad: SVC in [u.lower() for u in (ad.service_uuids or [])] or "FLOW" in (x.name or "").upper(), timeout=12)
    print("장치:", dev.address if dev else None)
    if not dev: mi.close_port(); return 2
    notes=[]; names=[]
    def cb(h,data):
        b=bytes(data); notes.append(b); print("  알림:", b[:20].hex(" "), "…" if len(b)>20 else "")
        if b and b[0]==0x27: names[:]=names_from(b)
    async with BleakClient(dev, timeout=15, winrt=dict(use_cached_services=False)) as c:
        print("연결:", c.is_connected)
        ch=c.services.get_characteristic(CH)
        try:
            res=await ch.obj.write_client_characteristic_configuration_descriptor_with_result_async(CCCDV.NOTIFY); print("CCCD:", int(res.status), "/ 오류", res.protocol_error)
        except Exception as e: print("CCCD 예외:", repr(e)[:100])
        try: await c.start_notify(CH, cb); print("start_notify: OK")
        except Exception as e: print("start_notify 실패:", repr(e)[:100])
        await asyncio.sleep(1.5); print("인증 전 알림:", len(notes))
        await c.write_gatt_char(CH, AUTH, response=False); print("인증 쓰기")
        for i in range(8):
            await asyncio.sleep(0.25)
            if not c.is_connected: print(f"  {(i+1)*0.25}s 후 끊김"); break
        print("인증 후 알림:", len(notes), "| 연결:", c.is_connected)
        dump=None
        if c.is_connected:
            await c.write_gatt_char(CH, SESSION, response=False); await asyncio.sleep(2.5); print("세션 후 알림:", len(notes), "| 연결:", c.is_connected)
            if c.is_connected:
                await c.write_gatt_char(CH, CONFIG, response=False); await asyncio.sleep(2.0)
                if names: print("스냅샷 이름:", ", ".join(f"{i+1}={n or '(빈칸)'}" for i,n in enumerate(names)))
                await c.write_gatt_char(CH, DUMP, response=False); print("덤프 요청 — USB 대기 25초")
                t=time.time()+25
                while time.time()<t:
                    m=mi.get_message()
                    if m and bytes(m[0]).startswith(HDR) and len(m[0])>=100: dump=bytes(m[0]); break
                    await asyncio.sleep(0.02)
    mi.close_port(); OUT.mkdir(parents=True, exist_ok=True)
    base=OUT/f"{datetime.now():%Y%m%d_%H%M}_latest"
    meta={"captured_at":datetime.now().isoformat(timespec="seconds"),"device":dev.address,"paired_encrypted":ok,"snapshot_names":names,"ble_notifications":[n.hex(" ") for n in notes],"sysex":None}
    if dump:
        base.with_suffix(".syx").write_bytes(dump); meta["sysex"]={"size":len(dump),"header_hex":dump[:12].hex(" "),"ends_with_f7":dump[-1]==0xF7}; print(f"저장 완료: {base.with_suffix('.syx')} ({len(dump)} bytes)")
    else: print("USB 덤프 미수신")
    base.with_suffix(".json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    return 0 if dump else 1
sys.exit(asyncio.run(main()))
