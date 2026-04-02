# 🍃 Pollen-Air-HA

*面向呼和浩特的花粉与空气质量服务，提供适合 Home Assistant 对接的 JSON API。*

[![Docker Image](https://github.com/gefl24/pollen-air-ha/actions/workflows/docker-image.yml/badge.svg)](https://github.com/gefl24/pollen-air-ha/actions/workflows/docker-image.yml)
[![Release](https://img.shields.io/github/v/release/gefl24/pollen-air-ha)](https://github.com/gefl24/pollen-air-ha/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

> **💡 项目概览**：适合轻量自托管部署，也适合直接接入 Home Assistant。

这个服务聚合了以下数据：
* ☁️ **空气质量数据**（AQI、空气等级、首要污染物）
* 🌼 **花粉数据**（默认使用中国天气 `weather.com.cn` 的花粉风险等级；保留 `pollencount.app` 作为空气/UV 等兜底数据源）
* ☀️ **紫外线指数**
* 📅 **每日预报数据**

🌐 **[中文说明文档](docs/README.zh-CN.md)**

---

<details>
<summary><b>📖 目录</b></summary>

- [配置说明](#️-配置说明)
- [快速开始](#-快速开始)
- [Docker 镜像](#-docker-镜像)
- [API 接口](#-api-接口)
- [Home Assistant 对接](#-home-assistant-对接)
- [项目结构](#-项目结构)
- [开发与部署](#️-开发与部署)
</details>

## ⚙️ 配置说明

启动服务前，先复制环境变量示例文件，再按需修改：

```bash
cp .env.example .env
```

你可以在 `.env` 中配置：
- 位置名称
- 经纬度
- 中国天气城市 ID（默认 `101081101`，即呼和浩特花粉页使用的城市 ID）
- 主数据源（默认 `weather.com.cn`）
- 刷新间隔
- 请求超时时间

> 当前默认策略：**花粉主源走 `weather.com.cn`，空气质量 / UV 等缺失字段由 `pollencount.app` 兜底**。

## 🚀 快速开始

使用 Docker Compose 可以最快跑起来：

```bash
docker compose up -d --build
```

启动后可直接测试接口：

```bash
curl http://localhost:8080/api/current
curl http://localhost:8080/api/ha/current
```

## 🐳 Docker 镜像

GitHub Actions 会自动构建并发布镜像到 GitHub Container Registry（GHCR）。

你可以直接拉最新镜像，也可以使用仓库自带的 `docker-compose.yml`。

```bash
docker pull ghcr.io/gefl24/pollen-air-ha:latest
```

## 📡 API 接口

| 接口 | 说明 | 关键字段 |
| :--- | :--- | :--- |
| `GET /health` | 健康检查接口 | `status` |
| `GET /api/current` | 完整归一化数据 | `location`、`air.aqi`、`air.category`、`pollen.*`、`uv_index`、`forecast.daily` |
| `GET /api/ha/current` | 更扁平、适合 HA 的接口 | `meta.updated_at`、`location.*`、`air.*`、`uv.value`、`pollen.*_value`、`pollen.*_category` |

## 🏡 Home Assistant 对接

这个 API 本来就是朝着 Home Assistant 接入去设计的，建议你从下面两个文件开始看：

* 📚 **[Home Assistant 对接说明](docs/HOME_ASSISTANT.md)**（完整接入步骤）
* 📄 **[示例 Package 配置](examples/home-assistant/packages/pollen_air.yaml)**（可直接参考抄配置）

如果后面还要继续优化，可以再往后端补一层“风险等级 / 开窗建议 / 过敏提醒”这种摘要字段，HA 端会更省心。

## 📂 项目结构

```text
pollen-air-ha/
├── app.py                  # 应用入口
├── Dockerfile              # 容器构建文件
├── docker-compose.yml      # 本地部署配置
├── .env.example            # 环境变量示例
├── docs/                   # 文档（HA 对接说明、中文说明）
└── examples/               # Home Assistant 配置示例
```

## 🛠️ 开发与部署

### GitHub Actions

仓库已经内置 CI/CD 流程，当前会：

* 在发往 `main` 的 Pull Request 上执行构建检查
* 在推送到 `main` 时构建并发布 GHCR 镜像
* 在打标签时发布版本镜像（例如 `v0.1.0`）
* 支持手动触发 `workflow_dispatch`

### Release / Tag 示例

如果你要手动发一个新版本：

```bash
git tag v0.1.0
git push origin v0.1.0
```
