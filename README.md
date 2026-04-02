# pollen-air-ha

一个最小可运行的 Docker 服务，用于获取指定地点的空气污染数据，并尝试获取花粉数据，统一暴露给 Home Assistant。

## 当前目标

- 地点：呼和浩特
- 空气质量：Open-Meteo
- 花粉：优先尝试 Open-Meteo pollen 字段
- 输出：HTTP JSON API

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
返回当前地点、空气质量、花粉数据。

## 说明

### 空气质量
当前使用 Open-Meteo air-quality API，通常可稳定返回：
- AQI
- PM2.5
- PM10
- 臭氧
- 二氧化氮
- 二氧化硫
- 一氧化碳

### 花粉
当前优先调用 Open-Meteo pollen 相关字段：
- alder_pollen
- birch_pollen
- grass_pollen
- mugwort_pollen
- olive_pollen
- ragweed_pollen

若该地区无返回，则明确返回：
- `available: false`
- `reason: provider_returned_no_pollen_data_for_this_region`

不会伪造数据。

## Home Assistant 示例

```yaml
rest:
  - resource: http://你的Docker主机IP:8080/api/current
    scan_interval: 1800
    sensor:
      - name: hohhot_air_aqi_us
        value_template: "{{ value_json.air.aqi_us }}"
      - name: hohhot_pm25
        value_template: "{{ value_json.air.pm25 }}"
      - name: hohhot_pm10
        value_template: "{{ value_json.air.pm10 }}"
      - name: hohhot_pollen_grass
        value_template: >
          {% if value_json.pollen and value_json.pollen.available %}
            {{ value_json.pollen.grass }}
          {% else %}
            unavailable
          {% endif %}
```

## 后续建议

如果要做成长期稳定项目，建议继续补：

1. 多数据源容错
2. 花粉插件化 provider
3. Prometheus metrics
4. MQTT 输出给 Home Assistant
5. 历史数据落盘
