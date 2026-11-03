"""Global flights from OpenSky Network: one call = every aircraft on Earth.
4 credits per call, 4000 credits/day on a free account -> one call per ~90 s."""
import time
import httpx

from app.config import settings
from app.models import Entity, EntityType
from app.sources.base import BaseSource

TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
STATES_URL = "https://opensky-network.org/api/states/all"


class OpenSkySource(BaseSource):
    name = "opensky"
    interval = 90

    def __init__(self) -> None:
        super().__init__()
        self._token: str | None = None
        self._token_expires_at = 0.0
        self.credits_remaining: int | None = None

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        r = await client.post(TOKEN_URL, data={
            "grant_type": "client_credentials",
            "client_id": settings.opensky_client_id,
            "client_secret": settings.opensky_client_secret,
        })
        r.raise_for_status()
        data = r.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 1800)
        return self._token

    async def fetch(self) -> list[list]:
        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._get_token(client)
            r = await client.get(STATES_URL, headers={"Authorization": f"Bearer {token}"})
            r.raise_for_status()
            remaining = r.headers.get("X-Rate-Limit-Remaining")
            self.credits_remaining = int(remaining) if remaining else None
            return r.json().get("states") or []

    def normalize(self, s: list) -> Entity | None:
        # 0 icao24, 1 callsign, 2 country, 3 time_position, 4 last_contact,
        # 5 lon, 6 lat, 7 baro_alt(m), 8 on_ground, 9 velocity(m/s), 10 true_track
        lon, lat = s[5], s[6]
        if lat is None or lon is None:
            return None
        return Entity(
            id=f"flight:{s[0].lower()}",
            type=EntityType.flight,
            name=(s[1] or s[0]).strip(),
            lat=lat, lon=lon,
            alt_m=s[7] or 0,
            heading=s[10],
            speed_kmh=s[9] * 3.6 if s[9] is not None else None,
            updated_at=int(s[3] or s[4] or time.time()),
            source=self.name,
            meta={"country": s[2], "on_ground": bool(s[8])},
        )
    def extra_health(self) -> dict:
        return {"credits_remaining": self.credits_remaining}