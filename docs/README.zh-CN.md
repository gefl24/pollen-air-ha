# pollen-air-ha 中文说明

这是一个面向 **呼和浩特** 的花粉与空气质量服务，提供适合 **Home Assistant** 对接的 JSON 接口。

## 项目用途

这个项目主要解决两件事：

1. 拉取空气质量、花粉、紫外线、预报数据
2. 提供更适合 Home Assistant 使用的接口，减少模板层的脏活

## 接口说明

### 1）完整接口

```text
GET /api/current
```

返回较完整的数据结构，适合调试、二次开发、做自定义展示。

### 2）HA 专用接口

```text
GET /api/ha/current
```

返回更扁平的字段，适合 Home Assistant REST sensor 直接读取。

## 快速启动

### Docker Compose

```bash
docker compose up -d --build
```

启动后可测试：

```bash
curl http://localhost:8080/health
curl http://localhost:8080/api/current
curl http://localhost:8080/api/ha/current
```

## Home Assistant 对接

详细文档见：

- `docs/HOME_ASSISTANT.md`
- `examples/home-assistant/packages/pollen_air.yaml`

如果你只是想尽快接入 HA，优先看这两个文件就够了。

## 适合谁用

- 想在 HA 里看本地空气 / 花粉情况的人
- 过敏季想做提醒自动化的人
- 想自托管环境数据接口的人

## 当前特性

- 空气质量
- 花粉数据（grass / tree / ragweed / mold）
- 紫外线指数
- 5 天预报
- Docker 部署
- GitHub Actions 自动构建
- GHCR 镜像发布

## 后续可扩展方向

- 增加综合风险等级
- 增加开窗建议 / 口罩建议
- 增加更适合 HA 展示的摘要字段
- 增加更多城市或坐标配置模板
