# Home Assistant Integration Guide

This project provides a Home Assistant-friendly endpoint:

- `GET /api/ha/current`

It is designed to reduce messy Jinja templates in Home Assistant.

---

## 1. Start the service

### Docker Compose

```bash
docker compose up -d --build
```

Then verify:

```bash
curl http://YOUR_SERVER_IP:8080/api/ha/current
```

---

## 2. Example response

Example fields returned by `/api/ha/current`:

```json
{
  "meta": {
    "service": "pollen-air-ha",
    "source": "pollencount.app",
    "updated_at": "2026-04-02T09:00:00+00:00",
    "errors": []
  },
  "location": {
    "name": "Xincheng District, Inner Mongolia, China",
    "city": "Xincheng District",
    "region": "Inner Mongolia",
    "country": "China",
    "lat": 40.8426,
    "lon": 111.7492
  },
  "air": {
    "aqi": 42,
    "category": "Good",
    "category_value": 1,
    "primary_pollutant": "O3"
  },
  "uv": {
    "value": 3,
    "category": "Moderate",
    "category_value": 2
  },
  "pollen": {
    "grass_value": 0,
    "grass_category": "Low",
    "tree_value": 0,
    "tree_category": "Low",
    "ragweed_value": 0,
    "ragweed_category": "Low",
    "mold_value": 0,
    "mold_category": "Low"
  },
  "forecast": {
    "headline": "...",
    "daily": []
  }
}
```

---

## 3. Home Assistant package mode

Recommended in `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Then create:

```text
packages/pollen_air.yaml
```

You can use the included example file from this repository:

```text
examples/home-assistant/packages/pollen_air.yaml
```

This repository now includes a package example that is already adapted for `configuration.yaml` package mode and XiaoAi text-entity playback (`text.xiaomi_lx06_e165_play_text`).

---

## 4. Package example (configuration.yaml compatible)

Replace `YOUR_SERVER_IP` with your actual server IP or domain.

A ready-to-copy package file is included here:

```text
examples/home-assistant/packages/pollen_air.yaml
```

It contains:
- REST sensor for `/api/ha/current`
- template sensors for pollen / AQI / risk helpers
- XiaoAi broadcast script using `text.xiaomi_lx06_e165_play_text`
- daily automation example

---

## 5. Recommended entities

Useful entities to expose in Home Assistant:

- `sensor.pollen_air_aqi`
- `sensor.pollen_air_category`
- `sensor.pollen_air_primary_pollutant`
- `sensor.pollen_uv_value`
- `sensor.pollen_grass_value`
- `sensor.pollen_grass_category`
- `sensor.pollen_tree_value`
- `sensor.pollen_tree_category`
- `sensor.pollen_ragweed_value`
- `sensor.pollen_ragweed_category`
- `sensor.pollen_mold_value`
- `sensor.pollen_mold_category`

---

## 6. Example Lovelace card

```yaml
type: entities
title: Pollen / Air Quality
show_header_toggle: false
entities:
  - entity: sensor.pollen_air_aqi
    name: 空气 AQI
  - entity: sensor.pollen_air_category
    name: 空气等级
  - entity: sensor.pollen_uv_value
    name: 紫外线指数
  - entity: sensor.pollen_grass_value
    name: 草花粉指数
  - entity: sensor.pollen_tree_value
    name: 树花粉指数
  - entity: sensor.pollen_ragweed_value
    name: 豚草花粉指数
  - entity: sensor.pollen_mold_value
    name: 霉菌指数
```

---

## 7. Example automation

```yaml
automation:
  - alias: pollen_air_high_aqi_alert
    id: pollen_air_high_aqi_alert
    trigger:
      - platform: numeric_state
        entity_id: sensor.pollen_air_aqi
        above: 100
    action:
      - service: persistent_notification.create
        data:
          title: 空气质量提醒
          message: >
            当前 AQI 为 {{ states('sensor.pollen_air_aqi') }}，
            空气等级：{{ states('sensor.pollen_air_category') }}。
    mode: single
```

---

## 8. Notes

- The `/api/current` endpoint is the fuller payload.
- The `/api/ha/current` endpoint is better for Home Assistant.
- If you want even less HA templating, you can extend the backend further with ready-to-display risk/advice fields.

---

## 9. Repository example files

Included in this repository:

- `examples/home-assistant/packages/pollen_air.yaml`
- `docs/HOME_ASSISTANT.md`

These are meant to be directly viewable from GitHub.
