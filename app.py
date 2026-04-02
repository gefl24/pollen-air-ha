import os
import time
import threading
import json
import re
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify

app = Flask(__name__)

LAT = float(os.getenv("LAT", "40.8426"))
LON = float(os.getenv("LON", "111.7492"))
REFRESH_SECONDS = int(os.getenv("REFRESH_SECONDS", "1800"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))
FORECAST_SOURCE = os.getenv("FORECAST_SOURCE", "weather.com.cn")
LOCATION_NAME = os.getenv("LOCATION_NAME", "Hohhot")
CITY_ID = os.getenv("CITY_ID", "101081101")

cache = {
    "location": {
        "name": LOCATION_NAME,
        "lat": LAT,
        "lon": LON,
        "city_id": CITY_ID,
    },
    "air": None,
    "pollen": None,
    "forecast": None,
    "uv_index": None,
    "updated_at": None,
    "errors": [],
}

_worker_started = False
_worker_lock = threading.Lock()
_city_mapping = None


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


def fetch_pollencount_forecast(lat, lon):
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
        "source": "pollencount.app",
        "headline": data.get("Headline", {}),
        "air": {
            "aqi": air.get("value"),
            "category": air.get("category"),
            "category_value": air.get("category_value"),
            "primary_pollutant": air.get("type"),
            "source": "pollencount.app",
        },
        "pollen": {
            "available": True,
            "mode": "typed",
            "grass": grass,
            "tree": tree,
            "ragweed": ragweed,
            "mold": mold,
            "source": "pollencount.app",
        },
        "uv_index": uv,
        "daily": forecast_days,
    }


def get_weather_cn_city_mapping():
    global _city_mapping
    if _city_mapping is not None:
        return _city_mapping

    txt = requests.get(
        "https://j.i8tq.com/flower/city.js",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=REQUEST_TIMEOUT,
    ).text
    match = re.search(r"var city = (\[.*\]);?\s*$", txt, re.S)
    if not match:
        raise ValueError("failed to parse weather.com.cn city mapping")
    _city_mapping = json.loads(match.group(1))
    return _city_mapping


def get_weather_cn_city(city_id):
    for item in get_weather_cn_city_mapping():
        if str(item.get("id")) == str(city_id):
            return item
    raise ValueError(f"city id not found in weather.com.cn flower city mapping: {city_id}")


def fetch_weather_cn_city_meta(city_id):
    resp = requests.get(
        f"https://d1.weather.com.cn/weather_index/{city_id}.html",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": f"https://m.weather.com.cn/huafen/index.html?id={city_id}",
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    text = resp.text
    match = re.search(r"weatherinfo\s*=\s*(\{.*?\})\s*;", text, re.S)
    if not match:
        return None
    return json.loads(match.group(1))


def parse_jsonp(text, callback_name="callback"):
    prefix = f"{callback_name}("
    if not text.startswith(prefix) or not text.endswith(")"):
        raise ValueError("unexpected JSONP response format")
    return json.loads(text[len(prefix):-1])


def fetch_weather_cn_pollen(city_id):
    city = get_weather_cn_city(city_id)
    today = datetime.now(timezone.utc).date().isoformat()
    params = {
        "eletype": "1",
        "city": city["en"],
        "start": today,
        "end": today,
        "callback": "callback",
        "predictFlag": "true",
    }
    resp = requests.get(
        "https://graph.weatherdt.com/ty/pollen/v2/hfindex.html",
        params=params,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": f"https://m.weather.com.cn/huafen/index.html?id={city_id}",
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = parse_jsonp(resp.text, "callback")

    daily = data.get("dataList") or []
    today_entry = daily[0] if daily else {}

    forecast_days = []
    for item in daily:
        forecast_days.append(
            {
                "date": item.get("addTime"),
                "week": item.get("week"),
                "level_code": item.get("levelCode"),
                "level": item.get("level"),
                "level_message": item.get("levelMsg"),
                "city_code": item.get("cityCode"),
                "eletype": item.get("eletype"),
            }
        )

    return {
        "source": "weather.com.cn",
        "headline": {
            "Text": f"{city['cn']}花粉风险 {today_entry.get('level') or '暂无'}"
        },
        "air": None,
        "pollen": {
            "available": bool(today_entry),
            "mode": "risk_level",
            "city_id": city["id"],
            "city_name": city["cn"],
            "city_code": city["en"],
            "season": data.get("seasonLevelName"),
            "level_code": today_entry.get("levelCode"),
            "level": today_entry.get("level"),
            "level_message": today_entry.get("levelMsg"),
            "eletype": today_entry.get("eletype"),
            "level_scale": data.get("seasonLevel") or [],
            "source": "weather.com.cn",
        },
        "uv_index": None,
        "daily": forecast_days,
    }


def merge_forecast(primary, fallback):
    merged = {
        "source": primary.get("source") if primary else fallback.get("source"),
        "headline": (primary or {}).get("headline") or (fallback or {}).get("headline") or {},
        "air": (primary or {}).get("air") or (fallback or {}).get("air"),
        "pollen": (primary or {}).get("pollen") or (fallback or {}).get("pollen"),
        "uv_index": (primary or {}).get("uv_index") or (fallback or {}).get("uv_index"),
        "daily": (primary or {}).get("daily") or (fallback or {}).get("daily") or [],
    }
    return merged


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
            "source": cache.get("source") or FORECAST_SOURCE,
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
            "city_id": location.get("city_id"),
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
            "mode": pollen.get("mode"),
            "source": pollen.get("source"),
            "grass_value": grass.get("value"),
            "grass_category": grass.get("category"),
            "tree_value": tree.get("value"),
            "tree_category": tree.get("category"),
            "ragweed_value": ragweed.get("value"),
            "ragweed_category": ragweed.get("category"),
            "mold_value": mold.get("value"),
            "mold_category": mold.get("category"),
            "level_code": pollen.get("level_code"),
            "level": pollen.get("level"),
            "level_message": pollen.get("level_message"),
            "season": pollen.get("season"),
            "city_name": pollen.get("city_name"),
            "city_code": pollen.get("city_code"),
        },
        "forecast": {
            "headline": forecast.get("headline", {}).get("Text"),
            "daily": forecast.get("daily") or [],
        },
    }


def refresh_once():
    errors = []
    location_info = None
    weather_cn_meta = None
    primary_forecast = None
    fallback_forecast = None

    try:
        location_info = fetch_location_name(LAT, LON)
    except Exception as e:
        errors.append(f"location fetch failed: {e}")

    try:
        weather_cn_meta = fetch_weather_cn_city_meta(CITY_ID)
    except Exception as e:
        errors.append(f"weather.com.cn city meta fetch failed: {e}")

    try:
        if FORECAST_SOURCE == "weather.com.cn":
            primary_forecast = fetch_weather_cn_pollen(CITY_ID)
            fallback_forecast = fetch_pollencount_forecast(LAT, LON)
        else:
            primary_forecast = fetch_pollencount_forecast(LAT, LON)
            if FORECAST_SOURCE == "pollencount+weather.com.cn":
                fallback_forecast = fetch_weather_cn_pollen(CITY_ID)
    except Exception as e:
        errors.append(f"primary forecast fetch failed: {e}")

    if FORECAST_SOURCE == "weather.com.cn" and fallback_forecast is None:
        try:
            fallback_forecast = fetch_pollencount_forecast(LAT, LON)
        except Exception as e:
            errors.append(f"fallback forecast fetch failed: {e}")

    forecast = merge_forecast(primary_forecast, fallback_forecast) if (primary_forecast or fallback_forecast) else None

    city_name = LOCATION_NAME
    weather_cn_city = get_weather_cn_city(CITY_ID)
    if weather_cn_city and weather_cn_city.get("cn"):
        city_name = weather_cn_city.get("cn")
    elif weather_cn_meta and weather_cn_meta.get("city"):
        city_name = weather_cn_meta.get("city")
    elif location_info and location_info.get("city"):
        city_name = location_info.get("city")

    cache["location"] = {
        "name": city_name,
        "lat": LAT,
        "lon": LON,
        "city": city_name,
        "state": (location_info or {}).get("state"),
        "country": (location_info or {}).get("country"),
        "city_id": CITY_ID,
        "source": "weather.com.cn" if weather_cn_meta else (location_info or {}).get("source"),
    }

    cache["forecast"] = forecast
    cache["air"] = forecast.get("air") if forecast else None
    cache["pollen"] = forecast.get("pollen") if forecast else None
    cache["uv_index"] = forecast.get("uv_index") if forecast else None
    cache["source"] = forecast.get("source") if forecast else FORECAST_SOURCE
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
            "source": cache.get("source") or FORECAST_SOURCE,
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
                "source": cache.get("source") or FORECAST_SOURCE,
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
