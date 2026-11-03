import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.store import store
from app.sources.base import BaseSource
from app.sources.flights_adsblol import AdsbLolSource
from app.sources.flights_opensky import OpenSkySource

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("argus")

# Places users are currently looking at. The web client will update this in Phase 3.
hot_points: set[tuple[float, float]] = {(17.385, 78.487)}

# Every feed Argus runs. Adding a new one = one line here + one small adapter file.
SOURCES: list[BaseSource] = [
    OpenSkySource(),
    AdsbLolSource(hot_points),
]


async def prune_loop(every: float = 30.0) -> None:
    """Drop stale entities on a fixed schedule, independent of the feeds."""
    while True:
        await asyncio.sleep(every)
        dropped = store.prune()
        if dropped:
            log.info("pruned %d stale entities", dropped)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [asyncio.create_task(src.run(), name=src.name) for src in SOURCES]
    tasks.append(asyncio.create_task(prune_loop(), name="prune"))
    log.info("started %d sources: %s", len(SOURCES), ", ".join(s.name for s in SOURCES))
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="Argus hub", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "ok": all(src.health.ok for src in SOURCES),
        "counts": store.counts(),
        "sources": {src.name: src.health.model_dump() | src.extra_health() for src in SOURCES},
        "time": time.time(),
    }


@app.get("/entities")
def entities(
    bbox: str | None = Query(None, description="south,west,north,east"),
    types: str | None = Query(None, description="comma-separated, e.g. flight,ship"),
):
    box = None
    if bbox:
        parts = bbox.split(",")
        if len(parts) != 4:
            raise HTTPException(400, "bbox must be south,west,north,east")
        box = tuple(float(x) for x in parts)
    kinds = set(types.split(",")) if types else None
    items = store.query(box, kinds)
    return {"count": len(items), "items": items}