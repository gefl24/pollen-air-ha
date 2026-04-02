import os
import time
import threading
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify

app = Flask(__name__)

LAT = float(os.getenv("LAT", "40.8426"))
LON = float(os.getenv("LON", "111.7492"))
REFRESH_SECONDS = int(os.getenv("REFRESH_SECONDS", "1800"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))
FORECAST_SOURCE = os.getenv("FORECAST_SOURCE", "pollencount.app")

cache = {
    "location": {
        "name": os.getenv("LOCATION_NAME", "Hohhot"),
        "lat": LAT,
        "lon": LON,
    },
    "air": None,
    "pollen": None,
    "forecast": None,
    "updated_at": None,
    "errors": [],
}

_worker_started = False
_worker_lock = threading.Lock()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def fetch_json(url, params):
    resp = requests.get(
        url,
        params=params,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()


def normalize_air_and_pollen(entries):
    result = {}
    for item in entries:
        name = item.get("Name")
        if not name:
            continue
        result[name] = {
            "value": item.get("Value"),
            "category": item.get("Category"),
            "category_value": item.get("CategoryValue"),
            "type": item.get("Type"),
        }
    return result


def fetch_location_name(lat, lon):
    data = fetch_json(
        "https://pollencount.app/api/geocodeReverse",
        {"lat": lat, "lng": lon},
    )

    city = data.get("city") or ""
    state = data.get("state") or ""
    country = data.get("country") or ""

    display_name = ", ".join([x for x in [city, state, country] if x]).strip()
    return {
        "city": city,
        "state": state,
        "country": country,
        "display_name": display_name or cache["location"].get("name") or "Unknown",
        "source": "pollencount.app",
    }


def fetch_forecast_data(lat, lon):
    data = fetch_json(
        "https://pollencount.app/api/getForecast",
        {"lat": lat, "lng": lon},
    )
    daily = data.get("DailyForecasts", [])
    if not daily:
        raise ValueError("forecast response did not include DailyForecasts")

    today = daily[0]
    air_and_pollen = normalize_air_and_pollen(today.get("AirAndPollen", []))

    def get_entry(name):
        return air_and_pollen.get(
            name,
            {"value": None, "category": None, "category_value": None, "type": None},
        )

    air = get_entry("AirQuality")
    grass = get_entry("Grass")
    tree = get_entry("Tree")
    ragweed = get_entry("Ragweed")
    mold = get_entry("Mold")
    uv = get_entry("UVIndex")

    forecast_days = []
    for item in daily[:5]:
        normalized = normalize_air_and_pollen(item.get("AirAndPollen", []))
        forecast_days.append(
            {
                "date": item.get("Date"),
                "air_quality": normalized.get("AirQuality"),
                "grass": normalized.get("Grass"),
                "tree": normalized.get("Tree"),
                "ragweed": normalized.get("Ragweed"),
                "mold": normalized.get("Mold"),
                "uv_index": normalized.get("UVIndex"),
            }
        )

    return {
        "source": FORECAST_SOURCE,
        "headline": data.get("Headline", {}),
        "air": {
            "aqi": air.get("value"),
            "category": air.get("category"),
            "category_value": air.get("category_value"),
            "primary_pollutant": air.get("type"),
            "source": FORECAST_SOURCE,
        },
        "pollen": {
            "available": True,
            "grass": grass,
            "tree": tree,
            "ragweed": ragweed,
            "mold": mold,
            "source": FORECAST_SOURCE,
        },
        "uv_index": uv,
        "daily": forecast_days,
    }


def build_ha_payload():
    location = cache.get("location") or {}
    air = cache.get("air") or {}
    pollen = cache.get("pollen") or {}
    forecast = cache.get("forecast") or {}

    grass = pollen.get("grass") or {}
    tree = pollen.get("tree") or {}
    ragweed = pollen.get("ragweed") or {}
    mold = pollen.get("mold") or {}

    return {
        "meta": {
            "service": "pollen-air-ha",
            "source": FORECAST_SOURCE,
            "updated_at": cache.get("updated_at"),
            "errors": cache.get("errors", []),
        },
        "location": {
            "name": location.get("name"),
            "city": location.get("city"),
            "region": location.get("state"),
            "country": location.get("country"),
            "lat": location.get("lat"),
            "lon": location.get("lon"),
        },
        "air": {
            "aqi": air.get("aqi"),
            "category": air.get("category"),
            "category_value": air.get("category_value"),
            "primary_pollutant": air.get("primary_pollutant"),
        },
        "uv": {
            "value": (cache.get("uv_index") or {}).get("value"),
            "category": (cache.get("uv_index") or {}).get("category"),
            "category_value": (cache.get("uv_index") or {}).get("category_value"),
        },
        "pollen": {
            "grass_value": grass.get("value"),
            "grass_category": grass.get("category"),
            "tree_value": tree.get("value"),
            "tree_category": tree.get("category"),
            "ragweed_value": ragweed.get("value"),
            "ragweed_category": ragweed.get("category"),
            "mold_value": mold.get("value"),
            "mold_category": mold.get("category"),
        },
        "forecast": {
            "headline": forecast.get("headline", {}).get("Text"),
            "daily": forecast.get("daily") or [],
        },
    }


def refresh_once():
    errors = []
    location_info = None
    forecast = None

    try:
        location_info = fetch_location_name(LAT, LON)
    except Exception as e:
        errors.append(f"location fetch failed: {e}")

    try:
        forecast = fetch_forecast_data(LAT, LON)
    except Exception as e:
        errors.append(f"forecast fetch failed: {e}")

    if location_info:
        cache["location"] = {
            "name": location_info["display_name"],
            "lat": LAT,
            "lon": LON,
            "city": location_info["city"],
            "state": location_info["state"],
            "country": location_info["country"],
            "source": location_info["source"],
        }

    cache["forecast"] = forecast
    cache["air"] = forecast.get("air") if forecast else None
    cache["pollen"] = forecast.get("pollen") if forecast else None
    cache["uv_index"] = forecast.get("uv_index") if forecast else None
    cache["updated_at"] = now_iso()
    cache["errors"] = errors


def background_worker():
    while True:
        try:
            refresh_once()
        except Exception as e:
            cache["errors"] = [f"background refresh failed: {e}"]
            cache["updated_at"] = now_iso()
        time.sleep(REFRESH_SECONDS)


def ensure_worker_started():
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        refresh_once()
        t = threading.Thread(target=background_worker, daemon=True)
        t.start()
        _worker_started = True


ensure_worker_started()


@app.route("/")
def index():
    return jsonify(
        {
            "service": "pollen-air-ha",
            "source": FORECAST_SOURCE,
            "endpoints": ["/health", "/api/current", "/api/ha/current"],
        }
    )


@app.route("/health")
def health():
    ok = cache["forecast"] is not None
    return (
        jsonify(
            {
                "status": "ok" if ok else "degraded",
                "updated_at": cache["updated_at"],
                "errors": cache["errors"],
                "source": FORECAST_SOURCE,
            }
        ),
        (200 if ok else 503),
    )


@app.route("/api/current")
def current():
    return jsonify(cache)


@app.route("/api/ha/current")
def ha_current():
    return jsonify(build_ha_payload())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
