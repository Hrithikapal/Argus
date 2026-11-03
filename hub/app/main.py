import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.store import store
from app.sources.flights import fetch_flights, normalize

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("argus")

FLIGHT_POINTS = [(17.385, 78.487)]   # one circle for now; we'll tile the world later
FLIGHT_INTERVAL = 10                 # seconds between fetches
last_ok: dict[str, float] = {}       # per-source timestamp of last successful fetch


async def flights_loop():
    while True:
        try:
            for lat, lon in FLIGHT_POINTS:
                raw = await fetch_flights(lat, lon)
                store.upsert_many([f for f in (normalize(a) for a in raw) if f])
            last_ok["flight"] = time.time()
            log.info("flights in store: %s", store.counts().get("flight", 0))
        except Exception as e:
            log.warning("flights fetch failed: %s", e)
        store.prune()
        await asyncio.sleep(FLIGHT_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(flights_loop())
    yield
    task.cancel()


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