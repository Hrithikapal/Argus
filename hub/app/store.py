import time
from collections import defaultdict


class EntityStore:
    """Everything Argus knows about right now, keyed by id.
    Anything not updated within ttl_seconds gets dropped."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._items: dict[str, dict] = {}

    def upsert_many(self, entities: list[dict]) -> None:
        for e in entities:
            self._items[e["id"]] = e

    def prune(self) -> int:
        cutoff = time.time() - self.ttl
        stale = [k for k, e in self._items.items() if e["updated_at"] < cutoff]
        for k in stale:
            del self._items[k]
        return len(stale)

    def query(self, bbox=None, types=None) -> list[dict]:
        out = []
        for e in self._items.values():
            if types and e["type"] not in types:
                continue
            if bbox:
                south, west, north, east = bbox
                if not (south <= e["lat"] <= north and west <= e["lon"] <= east):
                    continue
            out.append(e)
        return out

    def counts(self) -> dict[str, int]:
        c = defaultdict(int)
        for e in self._items.values():
            c[e["type"]] += 1
        return dict(c)


store = EntityStore()