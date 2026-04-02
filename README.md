# pollen-air-ha

一个最小可运行的 Docker 服务，用于获取指定地点的空气污染与花粉预报，并统一暴露给 Home Assistant。

## 当前目标

- 地点：呼和浩特
- 数据源：`pollencount.app`
- 输出：HTTP JSON API
- 支持字段：
  - AirQuality
  - Grass
  - Tree
  - Ragweed
  - Mold
  - UVIndex

## 目录结构

```bash
.
├── app.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## 启动

```bash
docker compose up -d --build
```

## 查看接口

```bash
curl http://localhost:8080/health
curl http://localhost:8080/api/current
```

## API

### `GET /health`
返回服务状态、更新时间、错误信息。

### `GET /api/current`
返回当前地点、空气质量、花粉、5天预报摘要。

## 数据源说明

当前通过以下接口获取数据：

- `https://pollencount.app/api/geocodeReverse?lat=...&lng=...`
- `https://pollencount.app/api/getForecast?lat=...&lng=...`

实测呼和浩特可返回：
- 地点反查
- 空气质量
- 花粉字段（Grass / Tree / Ragweed / Mold）

注意：某些日期花粉数值可能为 0，这表示当前预报值低，不是接口不可用。

## Home Assistant 示例

```yaml
rest:
  - resource: http://你的Docker主机IP:8080/api/current
    scan_interval: 1800
    sensor:
      - name: hohhot_air_aqi
        value_template: "{{ value_json.air.aqi }}"
      - name: hohhot_air_category
        value_template: "{{ value_json.air.category }}"
      - name: hohhot_pollen_grass
        value_template: "{{ value_json.pollen.grass.value }}"
      - name: hohhot_pollen_tree
        value_template: "{{ value_json.pollen.tree.value }}"
      - name: hohhot_pollen_ragweed
        value_template: "{{ value_json.pollen.ragweed.value }}"
      - name: hohhot_mold
        value_template: "{{ value_json.pollen.mold.value }}"
      - name: hohhot_uv_index
        value_template: "{{ value_json.forecast.uv_index.value }}"
```

## 后续建议

如果要做成长期稳定项目，建议继续补：

1. 增加结果缓存落盘
2. 增加 Prometheus metrics
3. 增加 MQTT 输出给 Home Assistant
4. 增加数据源降级策略（避免第三方源挂掉）
