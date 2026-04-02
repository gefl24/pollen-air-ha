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

cache = {
    "location": {
        "name": os.getenv("LOCATION_NAME", "Hohhot"),
        "lat": LAT,
        "lon": LON,
    },
    "air": None,
    "pollen": None,
    "updated_at": None,
    "errors": [],
}

_worker_started = False
_worker_lock = threading.Lock()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def fetch_json(url, params):
    resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_air_data(lat, lon):
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join([
            "european_aqi",
            "us_aqi",
            "pm2_5",
            "pm10",
            "ozone",
            "nitrogen_dioxide",
            "sulphur_dioxide",
            "carbon_monoxide",
        ]),
        "timezone": "auto",
    }

    data = fetch_json(url, params)
    current = data.get("current", {})

    return {
        "aqi_eu": current.get("european_aqi"),
        "aqi_us": current.get("us_aqi"),
        "pm25": current.get("pm2_5"),
        "pm10": current.get("pm10"),
        "o3": current.get("ozone"),
        "no2": current.get("nitrogen_dioxide"),
        "so2": current.get("sulphur_dioxide"),
        "co": current.get("carbon_monoxide"),
        "source": "open-meteo",
    }


def fetch_pollen_data(lat, lon):
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join([
            "alder_pollen",
            "birch_pollen",
            "grass_pollen",
            "mugwort_pollen",
            "olive_pollen",
            "ragweed_pollen",
        ]),
        "timezone": "auto",
    }

    data = fetch_json(url, params)
    current = data.get("current", {})

    pollen_fields = {
        "alder": current.get("alder_pollen"),
        "birch": current.get("birch_pollen"),
        "grass": current.get("grass_pollen"),
        "mugwort": current.get("mugwort_pollen"),
        "olive": current.get("olive_pollen"),
        "ragweed": current.get("ragweed_pollen"),
    }

    if all(v is None for v in pollen_fields.values()):
        return {
            "available": False,
            "reason": "provider_returned_no_pollen_data_for_this_region",
            "source": "open-meteo",
            "raw": pollen_fields,
        }

    return {
        "available": True,
        **pollen_fields,
        "source": "open-meteo",
    }


def refresh_once():
    errors = []
    air = None
    pollen = None

    try:
        air = fetch_air_data(LAT, LON)
    except Exception as e:
        errors.append(f"air fetch failed: {e}")

    try:
        pollen = fetch_pollen_data(LAT, LON)
    except Exception as e:
        errors.append(f"pollen fetch failed: {e}")

    cache["air"] = air
    cache["pollen"] = pollen
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
    return jsonify({
        "service": "pollen-air-ha",
        "endpoints": ["/health", "/api/current"],
    })


@app.route("/health")
def health():
    ok = cache["air"] is not None or cache["pollen"] is not None
    return jsonify({
        "status": "ok" if ok else "degraded",
        "updated_at": cache["updated_at"],
        "errors": cache["errors"],
    }), (200 if ok else 503)


@app.route("/api/current")
def current():
    return jsonify(cache)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
