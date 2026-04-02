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

`GET /api/current`

Returns a JSON payload including:
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
