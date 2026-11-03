"""Local-detail flights from adsb.lol: aircraft within 250 nm of each 'hot point'
(places users are currently looking at). Free, no key. Fresh every 10 s."""
import time
import httpx

from app.models import Entity, EntityType
from app.sources.base import BaseSource

URL = "https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/{nm}"


class AdsbLolSource(BaseSource):
    name = "adsb_lol"
    interval = 10

    def __init__(self, hot_points: set[tuple[float, float]], radius_nm: int = 250) -> None:
        super().__init__()
        self.hot_points = hot_points
        self.radius_nm = radius_nm

    async def fetch(self) -> list[dict]:
        records: list[dict] = []
        async with httpx.AsyncClient(timeout=15) as client:
            for lat, lon in list(self.hot_points):
                r = await client.get(URL.format(lat=lat, lon=lon, nm=self.radius_nm))
                r.raise_for_status()
                records.extend(r.json().get("ac", []))
        return records

    def normalize(self, ac: dict) -> Entity | None:
        if ac.get("lat") is None or ac.get("lon") is None:
            return None
        alt = ac.get("alt_baro")
        gs = ac.get("gs")
        return Entity(
            id=f"flight:{ac['hex'].lower()}",      # same id scheme as OpenSky, so they merge
            type=EntityType.flight,
            name=(ac.get("flight") or ac.get("r") or ac["hex"]).strip(),
            lat=ac["lat"], lon=ac["lon"],
            alt_m=0 if alt in (None, "ground") else alt * 0.3048,
            heading=ac.get("track"),
            speed_kmh=gs * 1.852 if gs is not None else None,
            updated_at=int(time.time() - ac.get("seen", 0)),
            source=self.name,
            meta={"aircraft_type": ac.get("t"), "registration": ac.get("r")},
        )