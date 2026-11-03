from enum import Enum
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    flight = "flight"
    ship = "ship"
    satellite = "satellite"
    earthquake = "earthquake"
    fire = "fire"
    news = "news"
    launch = "launch"


class Entity(BaseModel):
    """One thing in the world, in the single shape every source must produce.
    If a source can't fill these fields correctly, the record is rejected."""
    id: str                                   # "<type>:<stable id>", e.g. "flight:4ca87c"
    type: EntityType
    name: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    alt_m: float = 0
    heading: float | None = None             # degrees, 0 = north
    speed_kmh: float | None = None
    updated_at: int                           # unix seconds of the report
    source: str                               # which adapter produced it, e.g. "opensky"
    meta: dict = Field(default_factory=dict)  # source-specific extras


class SourceHealth(BaseModel):
    name: str
    ok: bool
    last_success_at: float | None = None
    consecutive_failures: int = 0
    last_error: str | None = None
    items: int = 0
    circuit_open_until: float | None = None