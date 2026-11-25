"""A tiny fake iTach TCP server for tests."""
import asyncio


class FakeITach:
    def __init__(self, *, ir_mode="IR", busy_first=False, learner=True, learn_delay=0.05, learn_code=None):
        self.ir_mode = ir_mode
        self.busy_first = busy_first
        self.learner = learner
        self.learn_delay = learn_delay
        self.learn_code = learn_code
        self._learn_pending = False
        self.relays = {"3:1": 0, "3:2": 0, "3:3": 0}
        self.sent_ir: list[str] = []
        self.connections = 0
        self._busy_done = False

    async def start(self):
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()

    async def _handle(self, reader, writer):
        self.connections += 1
        try:
            while True:
                cmd = (await reader.readuntil(b"\r")).decode().strip()
                for out in await self._respond(cmd):
                    writer.write((out + "\r").encode())
                await writer.drain()
                if self._learn_pending and self.learn_code:
                    self._learn_pending = False
                    await asyncio.sleep(self.learn_delay)
                    writer.write((self.learn_code + "\r").encode())
                    await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()

    async def _respond(self, cmd):
        parts = cmd.split(",")
        name = parts[0]
        if name == "getdevices":
            return ["device,0,0 ETHERNET", "device,1,3 IR", "device,3,3 RELAY", "endlistdevices"]
        if name == "getversion":
            return ["710-1005-05"]
        if name == "get_IR":
            return [f"IR,{parts[1]},{self.ir_mode}"]
        if name in ("getstate", "setstate"):
            conn = parts[1]
            if conn not in self.relays:
                return [f"ERR_{conn},003"]
            if name == "setstate":
                self.relays[conn] = int(parts[2])
            return [f"state,{conn},{self.relays[conn]}"]
        if name == "sendir":
            self.sent_ir.append(cmd)
            if self.busy_first and not self._busy_done:
                self._busy_done = True
                return [f"busyIR,{parts[1]},{parts[2]}"]
            return [f"completeir,{parts[1]},{parts[2]}"]
        if name == "stopir":
            return [f"stopir,{parts[1]}"]
        if name == "get_IRL":
            if not self.learner:
                return ["IR Learner Unavailable"]
            await asyncio.sleep(0)
            self._learn_pending = True
            return ["IR Learner Enabled"]
        if name == "stop_IRL":
            return ["IR Learner Disabled"]
        return ["unknowncommand 1"]
