import asyncio
import socket

from conftest import load

discovery = load("discovery")

BEACON = (
    b"AMXB<-UUID=GC100_000C1E024239_GlobalCache><-SDKClass=Utility>"
    b"<-Make=GlobalCache><-Model=iTachIP2IR><-Revision=710-1005-05>"
    b"<-Pkg_Level=GCPK002><-Config-URL=http://192.168.1.70>"
    b"<-PCB_PN=025-0026-06><-Status=Ready>"
)


def test_parse_beacon():
    unit = discovery.parse_beacon(BEACON, "10.0.0.9")
    assert unit == discovery.DiscoveredUnit(
        mac="000C1E024239", host="192.168.1.70", model="iTachIP2IR", revision="710-1005-05"
    )


def test_parse_beacon_falls_back_to_sender_ip():
    data = b"AMXB<-UUID=GC100_000C1E024239_GlobalCache><-Make=GlobalCache>"
    assert discovery.parse_beacon(data, "10.0.0.9").host == "10.0.0.9"


def test_parse_beacon_ignores_other_devices():
    assert discovery.parse_beacon(b"hello", "1.2.3.4") is None
    assert discovery.parse_beacon(b"AMXB<-UUID=X_Y><-Make=Other>", "1.2.3.4") is None


def test_scan_receives_unicast_beacon():
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    async def run():
        async def send_later():
            await asyncio.sleep(0.2)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.sendto(BEACON, ("127.0.0.1", port))
            s.close()

        task = asyncio.create_task(send_later())
        found = await discovery.async_scan(0.6, port=port, group=None, bind_host="127.0.0.1")
        await task
        return found

    found = asyncio.run(run())
    assert list(found) == ["000C1E024239"]


def test_scan_never_raises_when_port_unavailable():
    async def run():
        # privileged port -> bind fails for non-root; either way no exception
        return await discovery.async_scan(0.1, port=1, group=None)

    assert isinstance(asyncio.run(run()), dict)
