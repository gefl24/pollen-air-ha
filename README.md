# 🍃 Pollen-Air-HA

*Hohhot pollen and air quality service, with a Home Assistant-friendly JSON API.*

[![Docker Image](https://github.com/gefl24/pollen-air-ha/actions/workflows/docker-image.yml/badge.svg)](https://github.com/gefl24/pollen-air-ha/actions/workflows/docker-image.yml)
[![Release](https://img.shields.io/github/v/release/gefl24/pollen-air-ha)](https://github.com/gefl24/pollen-air-ha/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

> **💡 Overview**: Designed for lightweight self-hosted deployment and direct Home Assistant integration.

This service aggregates:
* ☁️ **Air quality data** (AQI, Category, Primary Pollutant)
* 🌼 **Pollen data** (Grass, Tree, Ragweed, Mold)
* ☀️ **UV index**
* 📅 **Daily forecast data**

🌐 **[中文说明文档 (Chinese README)](docs/README.zh-CN.md)**

---

<details>
<summary><b>📖 Table of Contents</b></summary>

- [Configuration](#configuration)
- [Quick Start](#quick-start)
- [Docker Image](#docker-image)
- [API Endpoints](#api-endpoints)
- [Home Assistant Integration](#home-assistant-integration)
- [Project Files](#project-files)
- [Development & Deployment](#development--deployment)
</details>

## ⚙️ Configuration

Before running the service, copy the example environment file and fill in your required values:

```bash
cp .env.example .env

## 🚀 Quick Start

Run the service easily using Docker Compose:

```bash
docker compose up -d --build
```

Test the endpoints:

```bash
curl http://localhost:8080/api/current
curl http://localhost:8080/api/ha/current
```

## 🐳 Docker Image

GitHub Actions automatically builds and publishes the image to GitHub Container Registry (GHCR). You can pull the latest image directly or use the included `docker-compose.yml`.

```bash
docker pull ghcr.io/gefl24/pollen-air-ha:latest
```

## 📡 API Endpoints

| Endpoint | Description | Key Payload Fields |
| :--- | :--- | :--- |
| `GET /health` | Health status check | `status` |
| `GET /api/current` | Full normalized payload | `location`, `air.aqi`, `air.category`, `pollen.*`, `uv_index`, `forecast.daily` |
| `GET /api/ha/current` | Flatter, HA-friendly payload | `meta.updated_at`, `location.*`, `air.*`, `uv.value`, `pollen.*_value`, `pollen.*_category` |

## 🏡 Home Assistant Integration

This API is tailored for Home Assistant. Start here for seamless integration:

  * 📚 **[Home Assistant Integration Guide](https://www.google.com/search?q=docs/HOME_ASSISTANT.md)** (Full setup instructions)
  * 📄 **[Example Package Configuration](https://www.google.com/search?q=examples/home-assistant/packages/pollen_air.yaml)** *Recommended next step: A backend risk/advice layer can be added later for even simpler Home Assistant dashboards and automations.*

## 📂 Project Files

```text
pollen-air-ha/
├── app.py                  # Application entry point
├── Dockerfile              # Container build instructions
├── docker-compose.yml      # Local deployment configuration
├── .env.example            # Example environment variables
├── docs/                   # Documentation (HA guide, ZH README)
└── examples/               # Home Assistant package examples
```

## 🛠️ Development & Deployment

### GitHub Actions

This repository includes a CI/CD workflow that:

  * Builds on pull requests targeting `main`.
  * Builds and publishes a GHCR image on pushes to `main`.
  * Publishes tagged builds for versions (e.g., `v0.1.0`).
  * Supports manual triggering via `workflow_dispatch`.

### Release / Tag Example

To trigger a new version release:

```bash
git tag v0.1.0
git push origin v0.1.0
```

```

### 💡 主要优化点：
1. **视觉层次 (Visual Hierarchy)**：引入了 Emoji（如 🍃, ⚙️, 🚀），打破了大段纯文本的沉闷感，使用户视线能快速定位关键部分。
2. **重点突出 (Emphasis)**：将 `Overview` 改为引用块（Blockquote），并用加粗和列表清晰展示了聚合的数据类型。
3. **中文文档前置**：对于双语项目，把中文文档的链接放在开头可以让国内用户一眼看到，体验更好。
4. **表格展示 API (Tables)**：把原本较长的 API 字段列表浓缩成了表格，对比度更强，扫视效率更高。
5. **结构重组 (Restructuring)**：
   - 将“配置 (.env)”步骤挪到了“快速运行 (docker compose)”前面，符合常规的操作流。
   - 使用 `<details>` 和 `<summary>` 标签将“目录 (TOC)”折叠，避免在手机端或首页占用过多首屏空间。
   - 把分散的 "GitHub Actions" 和 "Release" 合并到了同一个大类 `Development & Deployment` 下。
   - 使用 ASCII 树状图 (`tree` 风格) 重新格式化了“项目文件”列表，看起来更有代码仓库的技术感。
```
