import asyncio
import time
import httpx

ADSB_URL = "https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/{nm}"


async def fetch_flights(lat: float, lon: float, radius_nm: int = 250) -> list[dict]:
    """Ask adsb.lol for all aircraft within radius_nm of a point. Returns raw records."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(ADSB_URL.format(lat=lat, lon=lon, nm=radius_nm))
        r.raise_for_status()
        return r.json().get("ac", [])


def normalize(ac: dict) -> dict | None:
    """Convert one raw adsb.lol record into our common Argus shape."""
    if ac.get("lat") is None or ac.get("lon") is None:
        return None
    alt = ac.get("alt_baro")
    gs = ac.get("gs")
    return {
        "id": f"flight:{ac['hex']}",
        "type": "flight",
        "name": (ac.get("flight") or ac.get("r") or ac["hex"]).strip(),
        "lat": ac["lat"],
        "lon": ac["lon"],
        "alt_m": 0 if alt in (None, "ground") else round(alt * 0.3048),
        "heading": ac.get("track"),
        "speed_kmh": round(gs * 1.852) if gs is not None else None,
        "updated_at": int(time.time() - ac.get("seen", 0)),
        "meta": {"aircraft_type": ac.get("t"), "registration": ac.get("r")},
    }


async def main():
    raw = await fetch_flights(17.385, 78.487)  # test point: Hyderabad
    flights = [f for f in (normalize(a) for a in raw) if f]
    print(f"{len(flights)} flights within 250 nm")
    for f in flights[:5]:
        print(f'{f["name"]:10} lat={f["lat"]:.3f} lon={f["lon"]:.3f} '
              f'alt={f["alt_m"]} m  speed={f["speed_kmh"]} km/h  heading={f["heading"]}')


if __name__ == "__main__":
    asyncio.run(main())