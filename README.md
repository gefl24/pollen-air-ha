# pollen-air-ha

Hohhot pollen and air quality service, with a Home Assistant-friendly JSON API.

## What it does

This service aggregates:
- Air quality data
- Pollen data
- UV index
- Daily forecast data

It is designed for lightweight self-hosted deployment and Home Assistant integration.

## Current API output

### `GET /api/current`

Returns the full raw-ish normalized payload including:
- `location`
- `air.aqi`
- `air.category`
- `air.primary_pollutant`
- `pollen.grass`
- `pollen.tree`
- `pollen.ragweed`
- `pollen.mold`
- `uv_index`
- `forecast.daily`

### `GET /api/ha/current`

Returns a flatter Home Assistant-friendly payload including:
- `meta.updated_at`
- `location.city`
- `location.region`
- `air.aqi`
- `air.category`
- `air.primary_pollutant`
- `uv.value`
- `pollen.grass_value`
- `pollen.grass_category`
- `pollen.tree_value`
- `pollen.tree_category`
- `pollen.ragweed_value`
- `pollen.ragweed_category`
- `pollen.mold_value`
- `pollen.mold_category`
- `forecast.daily`

## Example use cases

- Home Assistant REST sensor
- Local dashboard widget
- Personal allergy monitoring
- Self-hosted environmental status endpoint

## Quick start

### Run with Docker Compose

```bash
docker compose up -d --build
```

Then access:

```bash
curl http://localhost:8080/api/current
```

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Then fill in the required values.

## Files

- `app.py` — application entry
- `Dockerfile` — container build
- `docker-compose.yml` — local deployment
- `.env.example` — example environment variables
- `examples/home-assistant/packages/pollen_air.yaml` — Home Assistant package example

## GitHub Actions

This repository includes a GitHub Actions workflow that:
- builds the Docker image on pushes to `main`
- builds on pull requests targeting `main`
- runs manually via `workflow_dispatch`
- also builds for version tags like `v0.1.0`

## Release / tag

Example:

```bash
git tag v0.1.0
git push origin v0.1.0
```

## Recommended next step

A cleaner `/api/ha/current` endpoint can be added later to flatten fields for easier Home Assistant templating.
