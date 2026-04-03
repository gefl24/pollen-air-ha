# 🍃 Pollen-Air-HA

*面向呼和浩特的花粉与空气质量服务，提供适合 Home Assistant 对接的 JSON API。*

[![Docker Image](https://github.com/gefl24/pollen-air-ha/actions/workflows/docker-image.yml/badge.svg)](https://github.com/gefl24/pollen-air-ha/actions/workflows/docker-image.yml)
[![Release](https://img.shields.io/github/v/release/gefl24/pollen-air-ha)](https://github.com/gefl24/pollen-air-ha/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

> **💡 项目概览**：适合轻量自托管部署，也适合直接接入 Home Assistant。

这个服务聚合了以下数据：
* ☁️ **空气质量数据**（AQI、空气等级、首要污染物）
* 🌼 **花粉数据**（默认使用 `api.cdfcz.com` 的花粉风险等级接口；空气质量与 UV 改为优先使用和风 `qweather.com`，`pollencount.app` 仅作最终兜底）
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
- [轻量控制台](#-轻量控制台)
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
- 花粉城市 ID（默认 `101080101`，当前用于呼和浩特）
- 和风城市 ID（默认 `101080101`，用于空气质量/UV）
- 和风 API Key（`QWEATHER_KEY`）
- 主数据源（默认 `api.cdfcz.com`）
- 刷新间隔
- 请求超时时间

> 当前默认策略：**花粉主源走 `api.cdfcz.com`，空气质量 / UV 优先走和风 `qweather.com`，若和风未配置再回退到 `pollencount.app`**。

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
| `GET /api/ha/current` | 更扁平、适合 HA 的接口 | `meta.updated_at`、`location.*`、`air.*`、`uv.value`、`pollen.level`、`pollen.hf_num`、`pollen.is_risky`、`pollen.open_window_recommended` |


## 🖥️ 轻量控制台

项目现在已经内置一个轻量 Web 控制台：

- `GET /ui`

控制台当前支持：

- 配置 API 地址 / Home Assistant 地址 / Token / 小爱实体 ID
- 配置播报模板
- 配置每日 **3 个播报时间点**（`00:00` 视为不执行）
- 立即测试 **小爱语音播报**
- 立即测试 **微信文字推送**
- 读取 / 同步 HA Helper
- 检查 HA 连接状态
- 生成 Home Assistant Package YAML
- 生成 Helper YAML

### 控制台配置持久化

控制台配置会保存到本地：

```text
/app/data/ui_config.json
```

仓库内的 `docker-compose.yml` 已经挂载：

```yaml
volumes:
  - ./data:/app/data
```

所以容器重建后配置不会丢。

### 微信推送支持

控制台支持在小爱语音播报之外，再发送一条微信文字推送。

当前支持两种方式：

1. **直接 Webhook**
   - Server酱
   - PushPlus
   - 企业微信机器人
2. **企微中转 URL（优先）**
   - 适合本地服务不在公网、不能直接让企业微信机器人回调本地的场景
   - 服务会先把消息发给你的中转接口，再由中转接口转发到企业微信机器人

当前可配置项包括：

- `wechat_push_enabled`
- `wechat_push_title`
- `wechat_push_webhook`
- `wechat_push_proxy_url`

### 语音 + 微信测试

控制台里的“语音+微信测试”会同时尝试：

- 小爱音箱语音播报
- 微信文字推送

如果只想测语音，可以先关闭微信推送；如果只想测微信，可以保留微信推送配置并让小爱配置为空后单独验证接口返回。

## 🏡 Home Assistant 对接

这个 API 本来就是朝着 Home Assistant 接入去设计的，建议你从下面两个文件开始看：

### 当前推荐接入方式

现在有两条路：

#### 1. Package 方式
适合想快速接进 HA 的场景：

- 使用控制台生成 `Package YAML`
- 放到：

```text
/config/packages/pollen_air.yaml
```

- 并在 `configuration.yaml` 中确保：

```yaml
homeassistant:
  packages: !include_dir_named packages
```

#### 2. 控制台 + Helper 方式
适合想实时改配置、不想反复手改 YAML 的场景：

- 控制台保存本地配置
- 同步到 HA Helper
- 读取 HA Helper 当前状态

目前 Helper 相关实体使用：

- `input_boolean.pollen_broadcast_enabled`
- `input_datetime.pollen_broadcast_time`
- `input_text.pollen_broadcast_template`

如果 HA 中还没有这些 Helper，可以先通过控制台生成 `Helper YAML`。

* 📚 **[Home Assistant 对接说明](docs/HOME_ASSISTANT.md)**（完整接入步骤）
* 📄 **[示例 Package 配置](examples/home-assistant/packages/pollen_air.yaml)**（可直接参考抄配置，已适配 `configuration.yaml` 的 `packages: !include_dir_named packages` 写法，并包含小爱音箱 `text.xiaomi_lx06_e165_play_text` 播报示例）

如果后面还要继续优化，可以再往后端补一层“风险等级 / 开窗建议 / 过敏提醒”这种摘要字段，HA 端会更省心。


HA 自动化现在可以直接用这些字段：
- `pollen.is_risky`：是否属于中/高/很高风险
- `pollen.is_very_risky`：是否属于高/很高风险
- `pollen.risk_score`：当前花粉数值（当前主源下对应 `hf_num`）
- `pollen.open_window_recommended`：是否建议开窗
- `pollen.mask_recommended`：是否建议戴口罩外出

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
