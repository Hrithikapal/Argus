import asyncio
import logging
import time
from abc import ABC, abstractmethod

from app.models import Entity, SourceHealth
from app.store import store

log = logging.getLogger("argus.sources")


class BaseSource(ABC):
    """Parent of every data feed.

    A child only sets `name` and `interval` and implements two methods:
      fetch()      -> call the upstream API, return raw records
      normalize()  -> turn one raw record into an Entity (or None to skip it)
    This class does the rest: the forever-loop, exponential backoff on errors,
    a circuit breaker after repeated failures, and health reporting."""

    name: str = "base"
    interval: float = 60.0           # seconds between successful fetches
    base_backoff: float = 10.0       # first wait after a failure
    max_backoff: float = 600.0       # never wait longer than 10 min
    circuit_threshold: int = 5       # failures in a row before we stop trying
    circuit_cooldown: float = 300.0  # how long we stop for (seconds)

    def __init__(self) -> None:
        self.health = SourceHealth(name=self.name, ok=False)
        self._failures = 0
        
    def extra_health(self) -> dict:
        """Optional: a child can add feed-specific numbers to /health."""
        return {}    

    @abstractmethod
    async def fetch(self) -> list:
        ...

    @abstractmethod
    def normalize(self, raw) -> Entity | None:
        ...

    async def tick(self) -> int:
        """One fetch -> normalize -> store cycle. Returns how many entities were stored."""
        raw = await self.fetch()
        entities: list[Entity] = []
        for r in raw:
            try:
                e = self.normalize(r)
            except Exception as exc:          # one bad record must never kill the batch
                log.debug("%s: skipping bad record: %s", self.name, exc)
                continue
            if e is not None:
                entities.append(e)
        store.upsert_many(entities)
        return len(entities)

    async def run(self) -> None:
        """Run forever. Start it once as a background task."""
        while True:
            if self._circuit_open():
                await asyncio.sleep(5)
                continue
            try:
                count = await self.tick()
            except Exception as exc:
                self._on_failure(exc)
                if not self._circuit_open():
                    await asyncio.sleep(self._backoff())
                continue
            self._on_success(count)
            await asyncio.sleep(self.interval)

    # --- internals ---------------------------------------------------------

    def _circuit_open(self) -> bool:
        until = self.health.circuit_open_until
        return until is not None and time.time() < until

    def _backoff(self) -> float:
        return min(self.base_backoff * 2 ** (self._failures - 1), self.max_backoff)

    def _on_success(self, count: int) -> None:
        self._failures = 0
        self.health = SourceHealth(name=self.name, ok=True, last_success_at=time.time(), items=count)
        log.info("%s: %d items", self.name, count)

    def _on_failure(self, exc: Exception) -> None:
        self._failures += 1
        self.health.ok = False
        self.health.consecutive_failures = self._failures
        self.health.last_error = f"{type(exc).__name__}: {exc}"[:200]
        if self._failures >= self.circuit_threshold:
            self.health.circuit_open_until = time.time() + self.circuit_cooldown
            log.error("%s: circuit OPEN for %.0fs after %d failures (%s)",
                      self.name, self.circuit_cooldown, self._failures, self.health.last_error)
        else:
            log.warning("%s: failure %d, retrying in %.0fs (%s)",
                        self.name, self._failures, self._backoff(), self.health.last_error)