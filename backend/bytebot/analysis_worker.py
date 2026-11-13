"""Bounded, lifespan-owned workers with durable recovery, without another service."""
import asyncio
from contextlib import suppress
from .analysis_store import claim, heartbeat, fail, LostLease
from .analysis_graph import build_graph


class AnalysisWorker:
    def __init__(self, pool, provider, slots=2, poll_seconds=1, heartbeat_seconds=10):
        self.pool, self.provider = pool, provider
        self.slots, self.poll_seconds, self.heartbeat_seconds = slots, poll_seconds, heartbeat_seconds
        self.graph = build_graph(pool, provider)
        self.tasks = []

    def start(self):
        self.tasks = [asyncio.create_task(self.loop()) for _ in range(self.slots)]

    async def close(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def pulse(self, run):
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            heartbeat(self.pool, run)

    async def execute(self, run):
        pulse = asyncio.create_task(self.pulse(run))
        work = asyncio.create_task(self.graph.ainvoke({'run': run, 'outputs': run['outputs']}))
        try:
            done, _ = await asyncio.wait([pulse, work], return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except LostLease:
            pass
        except asyncio.CancelledError:
            raise
        except Exception:
            with suppress(Exception):
                fail(self.pool, run)
        finally:
            pulse.cancel()
            work.cancel()
            await asyncio.gather(pulse, work, return_exceptions=True)

    async def loop(self):
        while True:
            try:
                run = claim(self.pool)
                if run:
                    await self.execute(run)
                    continue
            except asyncio.CancelledError:
                raise
            except Exception:
                # Database outages leave persisted work recoverable. Never log
                # exceptions that might contain SQL parameters or evidence.
                pass
            await asyncio.sleep(self.poll_seconds)
