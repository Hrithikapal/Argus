import time
from collections import defaultdict

from app.models import Entity


class EntityStore:
    """Everything Argus knows about right now, keyed by id.
    In-memory for now; the Redis geo index replaces the internals in Phase 2,
    but the methods below stay the same so nothing else has to change."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._items: dict[str, Entity] = {}

    def upsert_many(self, entities: list[Entity]) -> int:
        """Newer report wins. Returns how many were actually written."""
        written = 0
        for e in entities:
            old = self._items.get(e.id)
            if old is None or e.updated_at >= old.updated_at:
                self._items[e.id] = e
                written += 1
        return written

    def prune(self, now: float | None = None) -> int:
        """Drop anything not updated within ttl. Returns how many were dropped."""
        cutoff = (now or time.time()) - self.ttl
        stale = [k for k, e in self._items.items() if e.updated_at < cutoff]
        for k in stale:
            del self._items[k]
        return len(stale)

    def query(self, bbox: tuple[float, float, float, float] | None = None,
              types: set[str] | None = None) -> list[Entity]:
        out: list[Entity] = []
        for e in self._items.values():
            if types and e.type.value not in types:
                continue
            if bbox:
                south, west, north, east = bbox
                if not (south <= e.lat <= north and west <= e.lon <= east):
                    continue
            out.append(e)
        return out

    def counts(self) -> dict[str, int]:
        c: dict[str, int] = defaultdict(int)
        for e in self._items.values():
            c[e.type.value] += 1
        return dict(c)

    def __len__(self) -> int:
        return len(self._items)


store = EntityStore()