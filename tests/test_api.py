import asyncio

from conftest import load
from fake_itach import FakeITach

api = load("api")


def run(coro):
    return asyncio.run(coro)


def with_unit(fn, **kwargs):
    async def runner():
        unit = await FakeITach(**kwargs).start()
        try:
            client = api.GlobalCacheClient("127.0.0.1", unit.port, timeout=2)
            return await fn(unit, client)
        finally:
            await unit.stop()

    return run(runner())


def test_get_devices():
    async def go(unit, client):
        return await client.get_devices()

    modules = with_unit(go)
    assert [(m.address, m.count, m.type) for m in modules] == [
        (0, 0, "ETHERNET"), (1, 3, "IR"), (3, 3, "RELAY"),
    ]
    ir_mod = modules[1]
    assert ir_mod.is_ir and ir_mod.connectors == ["1:1", "1:2", "1:3"]
    assert modules[2].is_relay and not modules[2].is_ir


def test_relay_roundtrip_uses_one_connection_for_polling():
    async def go(unit, client):
        assert await client.set_relay_state("3:2", True) is True
        before = unit.connections
        states = await client.get_states(["3:1", "3:2", "3:3"])
        assert unit.connections == before + 1
        return states

    assert with_unit(go) == {"3:1": False, "3:2": True, "3:3": False}


def test_error_codes_are_described():
    async def go(unit, client):
        try:
            await client.set_relay_state("9:9", True)
        except api.GlobalCacheCommandError as err:
            return str(err)

    assert "Invalid connector address" in with_unit(go)


def test_send_ir_builds_sendir_line():
    async def go(unit, client):
        await client.send_ir("1:2", "38000,1,1,342,171,21,21")
        return unit.sent_ir

    sent = with_unit(go)
    assert len(sent) == 1
    parts = sent[0].split(",")
    assert parts[0] == "sendir" and parts[1] == "1:2"
    assert parts[3:] == ["38000", "1", "1", "342", "171", "21", "21"]


def test_send_ir_retries_when_busy():
    async def go(unit, client):
        await client.send_ir("1:1", "38000,1,1,10,10")
        return unit.sent_ir

    assert len(with_unit(go, busy_first=True)) == 2


def test_ir_modes_and_version_and_stop():
    async def go(unit, client):
        modes = await client.get_ir_modes(["1:1", "1:2"])
        await client.stop_ir("1:1")
        return modes, await client.get_version()

    modes, version = with_unit(go, ir_mode="SENSOR")
    assert modes == {"1:1": "SENSOR", "1:2": "SENSOR"}
    assert version == "710-1005-05"


def test_learn_ir_unavailable():
    async def go(unit, client):
        try:
            await client.learn_ir(1)
        except api.GlobalCacheError as err:
            return str(err)

    assert "not available" in with_unit(go, learner=False)


def test_learn_ir_timeout_stops_learner():
    async def go(unit, client):
        try:
            await client.learn_ir(0.3)
        except api.GlobalCacheError as err:
            return str(err)

    assert "Timed out" in with_unit(go)


def test_connection_refused_maps_to_connection_error():
    async def go():
        client = api.GlobalCacheClient("127.0.0.1", 1, timeout=1)
        try:
            await client.get_devices()
        except api.GlobalCacheConnectionError:
            return True

    assert run(go())


def test_learn_ir_success_returns_normalised_body():
    async def go(unit, client):
        return await client.learn_ir(2)

    code = "sendir,1:1,0,38000,1,1,342,171,21,21,21,64"
    assert with_unit(go, learn_code=code) == "38000,1,1,342,171,21,21,21,64"
