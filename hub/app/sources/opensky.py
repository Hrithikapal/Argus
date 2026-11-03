"""Global flights from OpenSky Network: one call = every aircraft on Earth.
Costs 4 credits per call; authenticated accounts get 4000/day, so ~1 call per 90 s."""
import asyncio
import logging
import time
import httpx

from app.config import settings

log = logging.getLogger("argus.opensky")

TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
STATES_URL = "https://opensky-network.org/api/states/all"

_token: str | None = None
_token_expires_at: float = 0.0


async def get_token(client: httpx.AsyncClient) -> str:
    """Return a valid access token, fetching a new one if the old one is about to expire."""
    global _token, _token_expires_at
    if _token and time.time() < _token_expires_at - 60:
        return _token
    r = await client.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": settings.opensky_client_id,
        "client_secret": settings.opensky_client_secret,
    })
    r.raise_for_status()
    data = r.json()
    _token = data["access_token"]
    _token_expires_at = time.time() + data.get("expires_in", 1800)
    return _token


async def fetch_world() -> tuple[list[list], int | None]:
    """All aircraft worldwide. Returns (raw state vectors, credits remaining today)."""
    async with httpx.AsyncClient(timeout=30) as client:
        token = await get_token(client)
        r = await client.get(STATES_URL, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        remaining = r.headers.get("X-Rate-Limit-Remaining")
        return r.json().get("states") or [], int(remaining) if remaining else None


def normalize(s: list) -> dict | None:
    """OpenSky gives each aircraft as a plain list; positions are fixed:
    0 icao24, 1 callsign, 2 country, 3 time_position, 4 last_contact,
    5 lon, 6 lat, 7 baro_alt(m), 8 on_ground, 9 velocity(m/s), 10 true_track"""
    lon, lat = s[5], s[6]
    if lat is None or lon is None:
        return None
    return {
        "id": f"flight:{s[0]}",
        "type": "flight",
        "name": (s[1] or s[0]).strip(),
        "lat": lat,
        "lon": lon,
        "alt_m": round(s[7]) if s[7] is not None else 0,
        "heading": s[10],
        "speed_kmh": round(s[9] * 3.6) if s[9] is not None else None,
        "updated_at": int(s[3] or s[4] or time.time()),
        "meta": {"country": s[2], "on_ground": bool(s[8]), "source": "opensky"},
    }


async def main():
    raw, credits = await fetch_world()
    flights = [f for f in (normalize(s) for s in raw) if f]
    print(f"{len(flights)} aircraft worldwide right now; credits left today: {credits}")
    for f in flights[:5]:
        print(f'{f["name"]:10} {f["meta"]["country"]:15} lat={f["lat"]:.2f} lon={f["lon"]:.2f} alt={f["alt_m"]} m')


if __name__ == "__main__":
    asyncio.run(main())