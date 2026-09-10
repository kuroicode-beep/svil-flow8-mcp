# C:\Projects\svil-flow8-mcp\tools\ble_pair.py — FLOW 8 LE를 Windows에 페어링(본딩) 시도. 믹서 설정 변경 없음.
import asyncio, sys
sys.stdout.reconfigure(encoding="utf-8")
from winrt.windows.devices.bluetooth import BluetoothLEDevice
from winrt.windows.devices.enumeration import DevicePairingKinds, DevicePairingProtectionLevel
ADDR = 0xC7F35C0BC422  # 진단에서 확인한 FLOW 8 LE 주소
async def main():
    dev = await BluetoothLEDevice.from_bluetooth_address_async(ADDR)
    if dev is None: print("장치 객체 획득 실패(광고 범위 밖?)"); return
    print("이름:", dev.name, "| 연결상태:", dev.connection_status)
    p = dev.device_information.pairing
    print("is_paired:", p.is_paired, "| can_pair:", p.can_pair, "| protection:", p.protection_level)
    if p.is_paired: print("이미 페어링됨"); return
    custom = p.custom
    def on_req(sender, args):
        print("페어링 요청 종류:", args.pairing_kind, "| PIN:", getattr(args, "pin", None)); args.accept()
    token = custom.add_pairing_requested(on_req)
    kinds = DevicePairingKinds.CONFIRM_ONLY | DevicePairingKinds.DISPLAY_PIN | DevicePairingKinds.PROVIDE_PIN | DevicePairingKinds.CONFIRM_PIN_MATCH
    res = await custom.pair_async(kinds, DevicePairingProtectionLevel.NONE)
    custom.remove_pairing_requested(token)
    print("결과:", res.status, "| protection:", res.protection_level_used)
asyncio.run(main())
