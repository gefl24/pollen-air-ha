import os
import time
import threading
import json
import html
import re
from pathlib import Path
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request, Response, send_from_directory

app = Flask(__name__)

LAT = float(os.getenv("LAT", "40.8426"))
LON = float(os.getenv("LON", "111.7492"))
REFRESH_SECONDS = int(os.getenv("REFRESH_SECONDS", "1800"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))
FORECAST_SOURCE = os.getenv("FORECAST_SOURCE", "api.cdfcz.com")
LOCATION_NAME = os.getenv("LOCATION_NAME", "Hohhot")
CITY_ID = os.getenv("CITY_ID", "101080101")
QWEATHER_KEY = os.getenv("QWEATHER_KEY", "")
QWEATHER_LOCATION = os.getenv("QWEATHER_LOCATION", "101080101")

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
_cdfcz_city_mapping = None
CONFIG_PATH = Path(os.getenv("UI_CONFIG_PATH", "data/ui_config.json"))
HA_HELPERS = {
    "enabled": "input_boolean.pollen_broadcast_enabled",
    "time": "input_datetime.pollen_broadcast_time",
    "template": "input_text.pollen_broadcast_template",
}

DEFAULT_UI_CONFIG = {
    "api_base_url": "",
    "ha_base_url": "",
    "ha_token": "",
    "xiaoai_entity_id": "text.xiaomi_lx06_e165_play_text",
    "schedule_enabled": False,
    "schedule_time": "07:30",
    "schedule_time_2": "00:00",
    "schedule_time_3": "00:00",
    "workdays_only": False,
    "broadcast_template": "早上好，{city}今天花粉风险{pollen_level}，花粉数值{pollen_score}。{pollen_message} 空气质量{air_category_cn}，AQI {aqi}。{window_advice}{mask_advice}",
    "event_trigger_enabled": False,
    "event_entity_id": "sensor.xiaomi_lx06_e165_conversation",
    "event_attribute_name": "content",
    "event_keywords": "天气,天气怎么样,今天天气怎么样",
    "event_delay_minutes": 2,
    "event_broadcast_template": "当前实时花粉情况是，{city}花粉风险{pollen_level}，花粉数值{pollen_score}。{pollen_message} {window_advice}{mask_advice}",
    "wechat_push_enabled": False,
    "wechat_notify_service": "",
    "wechat_push_webhook": "",
    "wechat_push_proxy_url": "",
    "wechat_push_title": "花粉空气播报",
}


def ensure_parent_dir(path):
    path.parent.mkdir(parents=True, exist_ok=True)


def load_ui_config():
    if not CONFIG_PATH.exists():
        return DEFAULT_UI_CONFIG.copy()
    try:
        data = json.loads(CONFIG_PATH.read_text())
        cfg = DEFAULT_UI_CONFIG.copy()
        cfg.update({k: v for k, v in data.items() if k in DEFAULT_UI_CONFIG})
        return cfg
    except Exception:
        return DEFAULT_UI_CONFIG.copy()


def save_ui_config(cfg):
    ensure_parent_dir(CONFIG_PATH)
    merged = DEFAULT_UI_CONFIG.copy()
    merged.update({k: v for k, v in cfg.items() if k in DEFAULT_UI_CONFIG})
    CONFIG_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2))
    return merged


def config_public_view(cfg):
    data = dict(cfg)
    token = data.get("ha_token") or ""
    data["ha_token"] = "***" if token else ""
    data["ha_token_configured"] = bool(token)
    return data


def build_broadcast_message(payload, cfg):
    pollen = payload.get("pollen") or {}
    air = payload.get("air") or {}
    location = payload.get("location") or {}
    air_cn_map = {
        "Good": "优",
        "Moderate": "良",
        "Unhealthy for Sensitive Groups": "轻度污染",
        "Unhealthy": "中度污染",
        "Very Unhealthy": "重度污染",
        "Hazardous": "严重污染",
    }
    values = {
        "city": location.get("city") or location.get("name") or "本地",
        "pollen_level": pollen.get("level") or "未知",
        "pollen_score": pollen.get("hf_num") if pollen.get("hf_num") is not None else "暂无",
        "pollen_message": pollen.get("level_message") or "暂无花粉提示。",
        "aqi": air.get("aqi") if air.get("aqi") is not None else "暂无",
        "air_category_cn": air_cn_map.get(air.get("category"), air.get("category") or "未知"),
        "window_advice": "今天可以适当开窗通风。" if pollen.get("open_window_recommended") is True else "今天不建议长时间开窗。",
        "mask_advice": "易敏人群出门建议戴口罩。" if pollen.get("mask_recommended") is True else "",
    }
    template = cfg.get("broadcast_template") or DEFAULT_UI_CONFIG["broadcast_template"]
    try:
        message = template.format(**values)
    except Exception:
        message = DEFAULT_UI_CONFIG["broadcast_template"].format(**values)
    return re.sub(r"\s+", " ", message).strip()


def call_home_assistant_service(cfg, message):
    base_url = (cfg.get("ha_base_url") or "").rstrip("/")
    token = cfg.get("ha_token") or ""
    entity_id = cfg.get("xiaoai_entity_id") or ""
    if not base_url:
        raise ValueError("ha_base_url is required")
    if not token:
        raise ValueError("ha_token is required")
    if not entity_id:
        raise ValueError("xiaoai_entity_id is required")
    resp = requests.post(
        f"{base_url}/api/services/text/set_value",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"entity_id": entity_id, "value": message},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    try:
        return resp.json()
    except Exception:
        return {"status": resp.status_code, "text": resp.text}


def call_wechat_push(cfg, message):
    if not cfg.get("wechat_push_enabled"):
        return {"enabled": False, "skipped": True}
    notify_service = (cfg.get("wechat_notify_service") or "").strip()
    title = (cfg.get("wechat_push_title") or "花粉空气播报").strip()
    if not notify_service:
        raise ValueError("wechat_notify_service is required when wechat_push_enabled is true")
    return ha_request(
        cfg,
        "POST",
        f"/api/services/{notify_service.replace('.', '/')}",
        {"title": title, "message": message},
    )


def ha_request(cfg, method, path, json_body=None):
    base_url = (cfg.get("ha_base_url") or "").rstrip("/")
    token = cfg.get("ha_token") or ""
    if not base_url:
        raise ValueError("ha_base_url is required")
    if not token:
        raise ValueError("ha_token is required")
    resp = requests.request(
        method,
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=json_body,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    if resp.text.strip():
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}
    return {}


def get_ha_entity_state(cfg, entity_id):
    return ha_request(cfg, "GET", f"/api/states/{entity_id}")


def check_ha_status(cfg):
    entity_id = cfg.get("xiaoai_entity_id") or ""
    result = {
        "connected": False,
        "ha_base_url": (cfg.get("ha_base_url") or "").rstrip("/"),
        "entity_id": entity_id,
        "entity_exists": False,
        "entity_state": None,
        "error": None,
    }
    try:
        ha_request(cfg, "GET", "/api/")
        result["connected"] = True
    except Exception as e:
        result["error"] = str(e)
        return result
    if entity_id:
        try:
            entity = get_ha_entity_state(cfg, entity_id)
            result["entity_exists"] = True
            result["entity_state"] = entity.get("state")
            result["entity"] = entity
        except Exception as e:
            result["error"] = f"entity check failed: {e}"
    return result


def sync_helpers_to_ha(cfg):
    missing = []
    states = {}
    for key, entity_id in HA_HELPERS.items():
        try:
            states[key] = get_ha_entity_state(cfg, entity_id)
        except Exception:
            missing.append(entity_id)
    if missing:
        raise ValueError("missing helper entities: " + ", ".join(missing))

    enabled_service = "/api/services/input_boolean/turn_on" if cfg.get("schedule_enabled") else "/api/services/input_boolean/turn_off"
    ha_request(cfg, "POST", enabled_service, {"entity_id": HA_HELPERS["enabled"]})

    ha_request(
        cfg,
        "POST",
        "/api/services/input_datetime/set_datetime",
        {"entity_id": HA_HELPERS["time"], "time": cfg.get("schedule_time") or "07:30"},
    )

    ha_request(
        cfg,
        "POST",
        "/api/services/input_text/set_value",
        {"entity_id": HA_HELPERS["template"], "value": cfg.get("broadcast_template") or DEFAULT_UI_CONFIG["broadcast_template"]},
    )
    return {
        "ok": True,
        "helpers": HA_HELPERS,
        "schedule_enabled": cfg.get("schedule_enabled"),
        "schedule_time": cfg.get("schedule_time"),
    }


def read_helpers_from_ha(cfg):
    missing = []
    result = {"helpers": HA_HELPERS.copy()}
    try:
        enabled = get_ha_entity_state(cfg, HA_HELPERS["enabled"])
        result["schedule_enabled"] = enabled.get("state") == "on"
    except Exception:
        missing.append(HA_HELPERS["enabled"])
    try:
        time_entity = get_ha_entity_state(cfg, HA_HELPERS["time"])
        time_value = ((time_entity.get("attributes") or {}).get("timestamp") and None) or time_entity.get("state")
        if isinstance(time_value, str) and len(time_value) >= 5:
            result["schedule_time"] = time_value[:5]
        else:
            result["schedule_time"] = None
    except Exception:
        missing.append(HA_HELPERS["time"])
    try:
        template_entity = get_ha_entity_state(cfg, HA_HELPERS["template"])
        result["broadcast_template"] = template_entity.get("state")
    except Exception:
        missing.append(HA_HELPERS["template"])
    result["missing"] = missing
    return result


def sanitize_ui_payload(data, current=None):
    current = current or load_ui_config()
    cleaned = current.copy()
    cleaned["api_base_url"] = str((data.get("api_base_url") or current.get("api_base_url") or "")).strip()
    cleaned["ha_base_url"] = str((data.get("ha_base_url") or current.get("ha_base_url") or "")).strip()
    token = data.get("ha_token")
    if token:
        cleaned["ha_token"] = str(token).strip()
    cleaned["xiaoai_entity_id"] = str((data.get("xiaoai_entity_id") or current.get("xiaoai_entity_id") or "")).strip()
    cleaned["schedule_enabled"] = bool(data.get("schedule_enabled"))
    cleaned["schedule_time"] = str((data.get("schedule_time") or current.get("schedule_time") or "07:30")).strip()[:5]
    cleaned["schedule_time_2"] = str((data.get("schedule_time_2") or current.get("schedule_time_2") or "00:00")).strip()[:5]
    cleaned["schedule_time_3"] = str((data.get("schedule_time_3") or current.get("schedule_time_3") or "00:00")).strip()[:5]
    cleaned["workdays_only"] = bool(data.get("workdays_only"))
    cleaned["broadcast_template"] = str((data.get("broadcast_template") or current.get("broadcast_template") or DEFAULT_UI_CONFIG["broadcast_template"])).strip()
    cleaned["event_trigger_enabled"] = bool(data.get("event_trigger_enabled"))
    cleaned["event_entity_id"] = str((data.get("event_entity_id") or current.get("event_entity_id") or DEFAULT_UI_CONFIG["event_entity_id"])).strip()
    cleaned["event_attribute_name"] = str((data.get("event_attribute_name") or current.get("event_attribute_name") or DEFAULT_UI_CONFIG["event_attribute_name"])).strip()
    cleaned["event_keywords"] = str((data.get("event_keywords") or current.get("event_keywords") or DEFAULT_UI_CONFIG["event_keywords"])).strip()
    delay_minutes = data.get("event_delay_minutes")
    if delay_minutes in (None, ""):
        delay_minutes = current.get("event_delay_minutes") or DEFAULT_UI_CONFIG["event_delay_minutes"]
    try:
        delay_minutes = int(delay_minutes)
    except Exception:
        delay_minutes = DEFAULT_UI_CONFIG["event_delay_minutes"]
    cleaned["event_delay_minutes"] = max(0, min(delay_minutes, 120))
    cleaned["event_broadcast_template"] = str((data.get("event_broadcast_template") or current.get("event_broadcast_template") or DEFAULT_UI_CONFIG["event_broadcast_template"])).strip()
    cleaned["wechat_push_enabled"] = bool(data.get("wechat_push_enabled"))
    cleaned["wechat_notify_service"] = str((data.get("wechat_notify_service") or current.get("wechat_notify_service") or "")).strip()
    cleaned["wechat_push_webhook"] = str((data.get("wechat_push_webhook") or current.get("wechat_push_webhook") or "")).strip()
    cleaned["wechat_push_proxy_url"] = str((data.get("wechat_push_proxy_url") or current.get("wechat_push_proxy_url") or "")).strip()
    cleaned["wechat_push_title"] = str((data.get("wechat_push_title") or current.get("wechat_push_title") or "花粉空气播报")).strip()
    return cleaned


def sync_schedule_to_config_yaml(cfg):
    if not cfg.get("schedule_enabled"):
        return None
    days = "1-5" if cfg.get("workdays_only") else "*"
    hh, mm = (cfg.get("schedule_time") or "07:30").split(":")
    return f"# Suggested cron expression for external scheduler: {int(mm)} {int(hh)} * * {days}"


def fetch_current_payload_for_ui(cfg):
    base_url = (cfg.get("api_base_url") or "").rstrip("/")
    if base_url:
        resp = requests.get(f"{base_url}/api/ha/current", timeout=REQUEST_TIMEOUT, headers={"Accept": "application/json"})
        resp.raise_for_status()
        return resp.json()
    return build_ha_payload()


def build_helper_package_yaml(cfg):
    schedule_time = cfg.get("schedule_time") or "07:30"
    broadcast_template = cfg.get("broadcast_template") or DEFAULT_UI_CONFIG["broadcast_template"]
    safe_template = broadcast_template.replace('"', "'")
    return f'''input_boolean:
  pollen_broadcast_enabled:
    name: Pollen Broadcast Enabled

input_datetime:
  pollen_broadcast_time:
    name: Pollen Broadcast Time
    has_date: false
    has_time: true

input_text:
  pollen_broadcast_template:
    name: Pollen Broadcast Template
    max: 255
    initial: "{safe_template}"

# 初始化建议时间：{schedule_time}
'''


def build_ha_package_yaml(cfg):
    template_path = Path("templates/ha_package_template.yaml")
    body = template_path.read_text()
    api_base_url = (cfg.get("api_base_url") or "http://YOUR_SERVER_IP:8080").rstrip("/")
    entity_id = cfg.get("xiaoai_entity_id") or "text.xiaomi_lx06_e165_play_text"
    schedule_time = cfg.get("schedule_time") or "07:30"
    broadcast_template = cfg.get("broadcast_template") or DEFAULT_UI_CONFIG["broadcast_template"]

    weekdays_block = ""
    if cfg.get("workdays_only"):
        weekdays_block = (
            "    condition:\n"
            "      - condition: time\n"
            "        weekday:\n"
            "          - mon\n"
            "          - tue\n"
            "          - wed\n"
            "          - thu\n"
            "          - fri"
        )

    wechat_notify_block = ""
    if cfg.get("wechat_push_enabled") and (cfg.get("wechat_push_webhook") or "").strip():
        wechat_notify_block = "      - service: rest_command.pollen_air_wechat_notify\n"

    event_trigger_block = ""
    if cfg.get("event_trigger_enabled"):
        event_entity_id = cfg.get("event_entity_id") or DEFAULT_UI_CONFIG["event_entity_id"]
        event_attribute_name = cfg.get("event_attribute_name") or DEFAULT_UI_CONFIG["event_attribute_name"]
        event_template = cfg.get("event_broadcast_template") or DEFAULT_UI_CONFIG["event_broadcast_template"]
        raw_delay = cfg.get("event_delay_minutes")
        if raw_delay in (None, ""):
            raw_delay = DEFAULT_UI_CONFIG["event_delay_minutes"]
        try:
            event_delay = int(raw_delay)
        except Exception:
            event_delay = DEFAULT_UI_CONFIG["event_delay_minutes"]
        event_delay = max(0, min(event_delay, 120))
        delay_h = event_delay // 60
        delay_m = event_delay % 60
        event_delay_hms = f"{delay_h:02d}:{delay_m:02d}:00"
        keywords = [k.strip() for k in str(cfg.get("event_keywords") or DEFAULT_UI_CONFIG["event_keywords"]).split(",") if k.strip()]
        event_keywords_list = "[" + ", ".join(json.dumps(k, ensure_ascii=False) for k in keywords) + "]"
        event_trigger_block = """

  - alias: 小爱问天气后延迟播报实时花粉
    id: xiaoai_weather_then_pollen_now
    trigger:
      - platform: state
        entity_id: __EVENT_ENTITY_ID__
    action:
      - variables:
          spoken_text: >-
            {{ state_attr('__EVENT_ENTITY_ID__', '__EVENT_ATTRIBUTE_NAME__') or trigger.to_state.state or '' }}
          spoken_text_lc: "{{ spoken_text | lower }}"
          trigger_keywords: __EVENT_KEYWORDS__
      - condition: template
        value_template: >-
          {{ trigger_keywords | select('in', spoken_text_lc) | list | count > 0 }}
      - delay: "__EVENT_DELAY_HMS__"
      - service: homeassistant.update_entity
        target:
          entity_id: sensor.pollen_air_ha_raw
      - delay: "00:00:03"
      - variables:
          pollen: "{{ state_attr('sensor.pollen_air_ha_raw', 'pollen') or dict() }}"
          air: "{{ state_attr('sensor.pollen_air_ha_raw', 'air') or dict() }}"
          air_cn: >-
            {% set m = {'Good':'优','Moderate':'良','Unhealthy for Sensitive Groups':'轻度污染','Unhealthy':'中度污染','Very Unhealthy':'重度污染','Hazardous':'严重污染'} %}
            {{ m.get(air.category, air.category if air.category else '未知') }}
          msg: >-
            __EVENT_BROADCAST_TEMPLATE__
      - service: text.set_value
        target:
          entity_id: __ENTITY_ID__
        data:
          value: "{{ msg }}"
    mode: restart
"""
        event_trigger_block = event_trigger_block.replace("__EVENT_ENTITY_ID__", event_entity_id)
        event_trigger_block = event_trigger_block.replace("__EVENT_ATTRIBUTE_NAME__", event_attribute_name)
        event_trigger_block = event_trigger_block.replace("__EVENT_KEYWORDS__", event_keywords_list)
        event_trigger_block = event_trigger_block.replace("__EVENT_DELAY_HMS__", event_delay_hms)
        event_trigger_block = event_trigger_block.replace("__EVENT_BROADCAST_TEMPLATE__", event_template)
        event_trigger_block = event_trigger_block.replace("__ENTITY_ID__", entity_id)

    body = body.replace("__API_BASE_URL__", api_base_url)
    body = body.replace("__ENTITY_ID__", entity_id)
    body = body.replace("__SCHEDULE_TIME__", schedule_time)
    body = body.replace("__BROADCAST_TEMPLATE__", broadcast_template)
    body = body.replace("__WEEKDAYS_BLOCK__", weekdays_block)
    body = body.replace("__WECHAT_NOTIFY_BLOCK__", wechat_notify_block)
    body = body.replace("__EVENT_TRIGGER_BLOCK__", event_trigger_block)
    return body

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


def qweather_category_from_aqi(aqi):
    if aqi is None:
        return None, None
    if aqi <= 50:
        return "Good", 1
    if aqi <= 100:
        return "Moderate", 2
    if aqi <= 150:
        return "Unhealthy for Sensitive Groups", 3
    if aqi <= 200:
        return "Unhealthy", 4
    if aqi <= 300:
        return "Very Unhealthy", 5
    return "Hazardous", 6


def qweather_category_from_uv(index):
    if index is None:
        return None, None
    if index <= 2:
        return "Low", 1
    if index <= 5:
        return "Moderate", 2
    if index <= 7:
        return "High", 3
    if index <= 10:
        return "Very High", 4
    return "Extreme", 5


def fetch_qweather_air_forecast():
    if not QWEATHER_KEY:
        raise ValueError("QWEATHER_KEY is not configured")

    air_now = fetch_json(
        "https://devapi.qweather.com/v7/air/now",
        {"location": QWEATHER_LOCATION, "key": QWEATHER_KEY},
    )
    now = air_now.get("now") or {}
    aqi = int(now["aqi"]) if now.get("aqi") not in (None, "") else None
    air_category, air_category_value = qweather_category_from_aqi(aqi)

    indices = fetch_json(
        "https://devapi.qweather.com/v7/indices/1d",
        {"location": QWEATHER_LOCATION, "type": "5", "key": QWEATHER_KEY},
    )
    uv_today = (indices.get("daily") or [{}])[0]
    uv_value = int(uv_today["level"]) if uv_today.get("level", "").isdigit() else None
    uv_category, uv_category_value = qweather_category_from_uv(uv_value)

    return {
        "source": "qweather.com",
        "headline": {},
        "air": {
            "aqi": aqi,
            "category": air_category,
            "category_value": air_category_value,
            "primary_pollutant": now.get("primary"),
            "source": "qweather.com",
        },
        "pollen": None,
        "uv_index": {
            "value": uv_value,
            "category": uv_category,
            "category_value": uv_category_value,
            "type": None,
            "text": uv_today.get("text"),
        },
        "daily": [],
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


def get_cdfcz_city_mapping():
    global _cdfcz_city_mapping
    if _cdfcz_city_mapping is not None:
        return _cdfcz_city_mapping

    resp = requests.get(
        "https://api.cdfcz.com/huafen/getCityList",
        params={"app": "fcwhservice", "channel": "h5", "platform": "h5"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    result = data.get("result") or []
    _cdfcz_city_mapping = result
    return _cdfcz_city_mapping


def get_cdfcz_city(city_id):
    for item in get_cdfcz_city_mapping():
        if str(item.get("id")) == str(city_id):
            return item
    raise ValueError(f"city id not found in cdfcz city mapping: {city_id}")


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


def fetch_cdfcz_pollen(city_id):
    city = get_cdfcz_city(city_id)
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


def fetch_cdfcz_pollen(city_id):
    city = get_cdfcz_city(city_id)
    city_code = city.get("code") or city.get("en")
    params = {
        "city": city_code,
        "app": "fcwhservice",
        "channel": "h5",
        "platform": "h5",
    }
    resp = requests.get(
        "https://api.cdfcz.com/huafen/getCityInfo",
        params=params,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    payload = resp.json()
    result = payload.get("result") or []
    if not result:
        raise ValueError("cdfcz pollen response did not include result")

    today_entry = result[0]

    return {
        "source": "api.cdfcz.com",
        "headline": {
            "Text": f"{today_entry.get('city') or city['cn']}花粉风险 {today_entry.get('hf_level') or '暂无'}"
        },
        "air": None,
        "pollen": {
            "available": True,
            "mode": "risk_level",
            "city_id": city["id"],
            "city_name": today_entry.get("city") or city.get("city") or city.get("cn"),
            "city_code": today_entry.get("code") or city_code,
            "season": "春季",
            "level_code": None,
            "level": today_entry.get("hf_level"),
            "level_message": today_entry.get("content"),
            "eletype": today_entry.get("eletype"),
            "level_scale": [],
            "source": "api.cdfcz.com",
            "hf_num": today_entry.get("hf_num"),
            "percent": today_entry.get("percent"),
            "color": today_entry.get("color"),
        },
        "uv_index": None,
        "daily": [
            {
                "date": today_entry.get("date"),
                "week": None,
                "level_code": None,
                "level": today_entry.get("hf_level"),
                "level_message": today_entry.get("content"),
                "city_code": today_entry.get("code") or city_code,
                "eletype": today_entry.get("eletype"),
                "hf_num": today_entry.get("hf_num"),
                "percent": today_entry.get("percent"),
                "color": today_entry.get("color"),
            }
        ],
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


def derive_pollen_risk_helpers(pollen):
    level = (pollen.get("level") or "").strip()
    hf_num = pollen.get("hf_num")
    risky_levels = {"中", "高", "很高"}
    very_risky_levels = {"高", "很高"}
    is_risky = level in risky_levels
    is_very_risky = level in very_risky_levels
    open_window_recommended = None if not level else not is_risky
    mask_recommended = None if not level else is_risky
    return {
        "is_risky": is_risky,
        "is_very_risky": is_very_risky,
        "open_window_recommended": open_window_recommended,
        "mask_recommended": mask_recommended,
        "risk_score": hf_num,
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
    risk_helpers = derive_pollen_risk_helpers(pollen)

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
            "hf_num": pollen.get("hf_num"),
            "percent": pollen.get("percent"),
            "color": pollen.get("color"),
            "is_risky": risk_helpers.get("is_risky"),
            "is_very_risky": risk_helpers.get("is_very_risky"),
            "risk_score": risk_helpers.get("risk_score"),
            "open_window_recommended": risk_helpers.get("open_window_recommended"),
            "mask_recommended": risk_helpers.get("mask_recommended"),
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
        if FORECAST_SOURCE == "api.cdfcz.com":
            primary_forecast = fetch_cdfcz_pollen(CITY_ID)
        elif FORECAST_SOURCE == "weather.com.cn":
            primary_forecast = fetch_weather_cn_pollen(CITY_ID)
        else:
            primary_forecast = fetch_pollencount_forecast(LAT, LON)
            if FORECAST_SOURCE == "pollencount+weather.com.cn":
                fallback_forecast = fetch_weather_cn_pollen(CITY_ID)
            elif FORECAST_SOURCE == "pollencount+api.cdfcz.com":
                fallback_forecast = fetch_cdfcz_pollen(CITY_ID)
    except Exception as e:
        errors.append(f"primary pollen fetch failed: {e}")

    if FORECAST_SOURCE in {"weather.com.cn", "api.cdfcz.com"}:
        try:
            fallback_forecast = fetch_qweather_air_forecast()
        except Exception as e:
            errors.append(f"qweather air fetch failed: {e}")
            if fallback_forecast is None:
                try:
                    fallback_forecast = fetch_pollencount_forecast(LAT, LON)
                except Exception as e2:
                    errors.append(f"fallback forecast fetch failed: {e2}")

    forecast = merge_forecast(primary_forecast, fallback_forecast) if (primary_forecast or fallback_forecast) else None

    city_name = LOCATION_NAME
    if FORECAST_SOURCE == "api.cdfcz.com":
        city_info = get_cdfcz_city(CITY_ID)
        if city_info and city_info.get("city"):
            city_name = city_info.get("city")
        elif location_info and location_info.get("city"):
            city_name = location_info.get("city")
    else:
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


@app.route("/ui")
def ui_console():
    return send_from_directory("templates", "ui.html")


@app.route("/api/ui/config", methods=["GET"])
def api_ui_config_get():
    return jsonify(config_public_view(load_ui_config()))


@app.route("/api/ui/config", methods=["POST"])
def api_ui_config_save():
    data = request.get_json(silent=True) or {}
    cfg = sanitize_ui_payload(data)
    save_ui_config(cfg)
    return jsonify({"ok": True, "config": config_public_view(cfg), "schedule_hint": sync_schedule_to_config_yaml(cfg)})


@app.route("/api/ui/test-broadcast", methods=["POST"])
def api_ui_test_broadcast():
    incoming = request.get_json(silent=True) or {}
    current = load_ui_config()
    cfg = sanitize_ui_payload(incoming, current=current)
    if incoming:
        save_ui_config(cfg)
    try:
        payload = fetch_current_payload_for_ui(cfg)
        message = build_broadcast_message(payload, cfg)
    except Exception as e:
        return jsonify({"ok": False, "error": "broadcast data failed", "message": str(e)}), 400

    voice_result = None
    wechat_result = None
    errors = {}

    try:
        voice_result = call_home_assistant_service(cfg, message)
    except Exception as e:
        errors["voice"] = str(e)

    try:
        wechat_result = call_wechat_push(cfg, message)
    except Exception as e:
        errors["wechat"] = str(e)

    ok = not errors or bool(voice_result) or bool(wechat_result)
    status = 200 if ok else 400
    return jsonify({
        "ok": ok,
        "message": message,
        "result": {"voice": voice_result, "wechat": wechat_result},
        "errors": errors,
    }), status


@app.route("/api/ui/package-preview", methods=["GET"])
def api_ui_package_preview():
    cfg = load_ui_config()
    return Response(build_ha_package_yaml(cfg), mimetype="text/plain; charset=utf-8")


@app.route("/api/ui/helper-package-preview", methods=["GET"])
def api_ui_helper_package_preview():
    cfg = load_ui_config()
    return Response(build_helper_package_yaml(cfg), mimetype="text/plain; charset=utf-8")


@app.route("/api/ui/ha-status", methods=["GET"])
def api_ui_ha_status():
    cfg = load_ui_config()
    try:
        return jsonify({"ok": True, "status": check_ha_status(cfg)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/ui/sync-helpers", methods=["POST"])
def api_ui_sync_helpers():
    incoming = request.get_json(silent=True) or {}
    current = load_ui_config()
    cfg = sanitize_ui_payload(incoming, current=current)
    if incoming:
        save_ui_config(cfg)
    try:
        result = sync_helpers_to_ha(cfg)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/ui/read-helpers", methods=["GET"])
def api_ui_read_helpers():
    cfg = load_ui_config()
    try:
        data = read_helpers_from_ha(cfg)
        return jsonify({"ok": True, "result": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


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
