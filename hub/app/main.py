import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.store import store
from app.sources import opensky
from app.sources.flights import fetch_flights, normalize as normalize_local

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("argus")

WORLD_INTERVAL = 90   # OpenSky: whole world, 4 credits per call, ~1000 calls/day
LOCAL_INTERVAL = 10   # adsb.lol: fresh detail around where users are looking
hot_points: set[tuple[float, float]] = {(17.385, 78.487)}   # the web client will update this later
last_ok: dict[str, float] = {}


async def world_flights_loop():
    while True:
        try:
            raw, credits = await opensky.fetch_world()
            store.upsert_many([f for f in (opensky.normalize(s) for s in raw) if f])
            last_ok["opensky"] = time.time()
            log.info("opensky: %s aircraft, credits left %s", len(raw), credits)
        except Exception as e:
            log.warning("opensky fetch failed: %s", e)
        store.prune()
        await asyncio.sleep(WORLD_INTERVAL)


async def local_flights_loop():
    while True:
        try:
            for lat, lon in list(hot_points):
                raw = await fetch_flights(lat, lon)
                store.upsert_many([f for f in (normalize_local(a) for a in raw) if f])
            last_ok["adsb_lol"] = time.time()
        except Exception as e:
            log.warning("adsb.lol fetch failed: %s", e)
        await asyncio.sleep(LOCAL_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [asyncio.create_task(world_flights_loop()),
             asyncio.create_task(local_flights_loop())]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="Argus hub", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    now = time.time()
    return {
        "counts": store.counts(),
        "sources": {k: {"last_ok_seconds_ago": round(now - v)} for k, v in last_ok.items()},
    }


@app.get("/entities")
def entities(
    bbox: str | None = Query(None, description="south,west,north,east"),
    types: str | None = Query(None, description="comma-separated, e.g. flight,ship"),
):
    box = tuple(float(x) for x in bbox.split(",")) if bbox else None
    kinds = set(types.split(",")) if types else None
    items = store.query(box, kinds)
    return {"count": len(items), "items": items}