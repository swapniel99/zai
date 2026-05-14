import asyncio
import calendar as cal_mod
from datetime import date, timedelta

import httpx

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL  = "https://archive-api.open-meteo.com/v1/archive"

DAILY_VARS = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"]
FORECAST_HORIZON_DAYS = 16


async def _geocode(client: httpx.AsyncClient, location: str) -> tuple[float, float, str] | None:
    resp = await client.get(GEOCODE_URL, params={"name": location, "count": 1, "language": "en"})
    resp.raise_for_status()
    results = resp.json().get("results")
    if not results:
        return None
    r = results[0]
    return r["latitude"], r["longitude"], f"{r.get('name')}, {r.get('country', '')}"


def _summarise(daily: dict) -> dict:
    max_t  = [t for t in daily.get("temperature_2m_max", []) if t is not None]
    min_t  = [t for t in daily.get("temperature_2m_min", []) if t is not None]
    precip = [p for p in daily.get("precipitation_sum", []) if p is not None]
    return {
        "avg_max":    round(sum(max_t)  / len(max_t),  1) if max_t  else None,
        "avg_min":    round(sum(min_t)  / len(min_t),  1) if min_t  else None,
        "total_precip": round(sum(precip), 1)              if precip else None,
    }


def _fmt(label: str, month_str: str, s: dict) -> str:
    if s["avg_max"] is None:
        return f"No climate data available for {label}."
    return (
        f"Climate for {label} in {month_str}:\n"
        f"  Avg high: {s['avg_max']}°C  |  Avg low: {s['avg_min']}°C\n"
        f"  Total precipitation: {s['total_precip']} mm"
    )


async def get_climate_data(location: str, month: str) -> str:
    """
    Return temperature range and precipitation for a location and month.
    month: month name or 'Month YYYY' (e.g. 'April', 'April 2027').
    Uses live forecast for dates within 16 days; historical ERA5 archive otherwise.
    """
    month_names = {m.lower(): i for i, m in enumerate(cal_mod.month_abbr) if m}
    month_names.update({m.lower(): i for i, m in enumerate(cal_mod.month_name) if m})

    parts = month.strip().split()
    target_month = month_names.get(parts[0].lower())
    if target_month is None:
        return f"Could not parse month: {month}"

    today = date.today()
    target_year = int(parts[1]) if len(parts) > 1 else today.year
    start = date(target_year, target_month, 1)
    end   = date(target_year, target_month, cal_mod.monthrange(target_year, target_month)[1])

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            geo = await _geocode(client, location)
            if geo is None:
                return f"Could not geocode location: {location}"
            lat, lon, label = geo

            if start <= today + timedelta(days=FORECAST_HORIZON_DAYS):
                forecast_end = min(end, today + timedelta(days=FORECAST_HORIZON_DAYS - 1))
                resp = await client.get(
                    FORECAST_URL,
                    params={
                        "latitude": lat, "longitude": lon,
                        "daily": ",".join(DAILY_VARS),
                        "start_date": start.isoformat(),
                        "end_date": forecast_end.isoformat(),
                        "timezone": "auto",
                    },
                )
                resp.raise_for_status()
                return _fmt(label, month, _summarise(resp.json().get("daily", {})))

            else:
                # Fetch 3 prior years concurrently
                async def _fetch_year(yr: int) -> dict:
                    s = date(yr, target_month, 1)
                    e = date(yr, target_month, cal_mod.monthrange(yr, target_month)[1])
                    r = await client.get(
                        ARCHIVE_URL,
                        params={
                            "latitude": lat, "longitude": lon,
                            "daily": ",".join(DAILY_VARS),
                            "start_date": s.isoformat(),
                            "end_date": e.isoformat(),
                            "timezone": "auto",
                        },
                    )
                    r.raise_for_status()
                    return r.json().get("daily", {})

                years_data = await asyncio.gather(*[_fetch_year(target_year - i) for i in range(1, 4)])

                all_max, all_min, all_precip = [], [], []
                for d in years_data:
                    all_max    += [t for t in d.get("temperature_2m_max", []) if t is not None]
                    all_min    += [t for t in d.get("temperature_2m_min", []) if t is not None]
                    all_precip += [p for p in d.get("precipitation_sum", []) if p is not None]

                summary = {
                    "avg_max":      round(sum(all_max)    / len(all_max),    1) if all_max    else None,
                    "avg_min":      round(sum(all_min)    / len(all_min),    1) if all_min    else None,
                    "total_precip": round(sum(all_precip) / 3,               1) if all_precip else None,
                }
                return _fmt(label, month, summary)

    except Exception as e:
        return f"Climate data fetch failed for {location}: {e}"
