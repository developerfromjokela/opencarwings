from tculink.httpgateway.ficosa.destinations import evauth, evinfo, door, hornlight, remotestart

# ACP Destinations map (Destination ID -> handler function)
DESTINATIONS = {
    0x27: evauth.handle,
    # EVInfo
    0x28: evinfo.handle, # ChargeMonitor
    0x29: evinfo.handle, # UnplugReminder
    0x2a: evinfo.handle, # ChargeFinish
    0x2b: evinfo.handle, # ChargeStart
    0x2c: evinfo.handle, # A/C
    0x3e: evinfo.handle, # ChargeStart80%
    # Car
    0x31: door.handle,
    0x38: hornlight.handle,
    0x39: remotestart.handle
}