# pollen-air-ha

Hohhot pollen and air quality service, with a Home Assistant-friendly JSON API.

[![Docker Image](https://github.com/gefl24/pollen-air-ha/actions/workflows/docker-image.yml/badge.svg)](https://github.com/gefl24/pollen-air-ha/actions/workflows/docker-image.yml)
[![Release](https://img.shields.io/github/v/release/gefl24/pollen-air-ha)](https://github.com/gefl24/pollen-air-ha/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

## Overview

This service aggregates:
- Air quality data
- Pollen data
- UV index
- Daily forecast data

It is designed for lightweight self-hosted deployment and direct Home Assistant integration.

## Table of contents

- [Quick start](#quick-start)
- [Docker image](#docker-image)
- [API endpoints](#api-endpoints)
- [Home Assistant docs](#home-assistant-docs)
- [Project files](#project-files)
- [GitHub Actions](#github-actions)
- [Release / tag](#release--tag)

## Quick start

### Run with Docker Compose

```bash
docker compose up -d --build
```

Then access:

```bash
curl http://localhost:8080/api/current
curl http://localhost:8080/api/ha/current
```

## Docker image

GitHub Actions will publish the image to GHCR:

```bash
docker pull ghcr.io/gefl24/pollen-air-ha:latest
```

You can also use the included `docker-compose.yml` directly.

## API endpoints

### `GET /health`
Health status endpoint.

### `GET /api/current`
Returns the fuller normalized payload including:
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

## Home Assistant docs

- Full guide: [docs/HOME_ASSISTANT.md](docs/HOME_ASSISTANT.md)
- Example package: [examples/home-assistant/packages/pollen_air.yaml](examples/home-assistant/packages/pollen_air.yaml)

If you want direct GitHub-viewable setup instructions, start here:
- [Home Assistant Integration Guide](docs/HOME_ASSISTANT.md)

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Then fill in the required values.

## Project files

- `app.py` — application entry
- `Dockerfile` — container build
- `docker-compose.yml` — local deployment
- `.env.example` — example environment variables
- `docs/HOME_ASSISTANT.md` — Home Assistant integration guide
- `examples/home-assistant/packages/pollen_air.yaml` — Home Assistant package example

## GitHub Actions

This repository includes a GitHub Actions workflow that:
- builds on pull requests targeting `main`
- builds and publishes a GHCR image on pushes to `main`
- publishes tagged builds for versions like `v0.1.0`
- supports manual triggering via `workflow_dispatch`

## Release / tag

Example:

```bash
git tag v0.1.0
git push origin v0.1.0
```

## Recommended next step

A backend risk/advice layer can be added later for even simpler Home Assistant dashboards and automations.
