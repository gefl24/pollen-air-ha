# Home Assistant 对接详细操作手册

这份手册按 **Home Assistant 里实际操作顺序** 写，目标是让你完成三件事：

1. 在 HA 里接入 `pollen-air-ha` 的花粉 / 空气质量数据
2. 让小爱音箱可以播报
3. 配置“当 `sensor.xiaomi_lx06_e165_conversation` 识别到天气类问题后，延迟 2 分钟播报实时花粉”

---

## 一、准备工作

开始前，先确认以下信息已经就绪。

### 1. `pollen-air-ha` 服务地址

例如：

```text
http://192.168.1.20:8080
```

浏览器或命令行能访问：

```text
http://你的服务地址:8080/api/ha/current
```

如果能返回 JSON，说明服务正常。

### 2. Home Assistant 地址

例如：

```text
http://homeassistant.local:8123
```

或：

```text
http://192.168.1.10:8123
```

### 3. Home Assistant 长期访问令牌（Long-Lived Access Token）

在 HA 中：

- 左下角点 **个人头像 / Profile**
- 拉到页面底部 **长期访问令牌**
- 点 **创建令牌**
- 名字可以填：`pollen-air-ha`
- 创建后复制保存

> 注意：Token 只显示一次，丢了就得重新生成。

### 4. 小爱播报实体

当前项目默认使用：

```text
text.xiaomi_lx06_e165_play_text
```

### 5. 小爱会话实体

当前建议监听：

```text
sensor.xiaomi_lx06_e165_conversation
```

属性优先用：

```text
content
```

---

## 二、启动 `pollen-air-ha` 服务

如果服务还没运行，在项目目录执行：

```bash
docker compose up -d --build
```

启动后测试：

```bash
curl http://你的服务地址:8080/api/ha/current
```

如果能看到 JSON 返回，说明服务正常。

---

## 三、在 HA 中开启 packages 模式

推荐使用 **package 方式** 接入，配置更集中，也更容易维护。

### 第一步：打开 `configuration.yaml`

如果你使用 File Editor / Studio Code Server，可直接打开：

```text
/config/configuration.yaml
```

### 第二步：确认存在以下配置

```yaml
homeassistant:
  packages: !include_dir_named packages
```

#### 情况 A：原来没有 `homeassistant:` 段

直接增加：

```yaml
homeassistant:
  packages: !include_dir_named packages
```

#### 情况 B：已有 `homeassistant:` 段

就在里面补一行：

```yaml
packages: !include_dir_named packages
```

示例：

```yaml
homeassistant:
  name: Home
  latitude: 40.0
  longitude: 111.0
  packages: !include_dir_named packages
```

### 第三步：确保 `packages` 目录存在

在 HA 配置目录下创建：

```text
/config/packages
```

---

## 四、打开项目控制台

浏览器打开：

```text
http://你的服务地址:8080/ui
```

控制台支持：

- 保存服务配置
- 检查 HA 连接
- 测试小爱播报
- 生成 Package YAML
- 配置实体变化触发播报

---

## 五、在控制台填写配置

### A. 核心服务配置

#### 1）服务 API 基准地址

例如：

```text
http://192.168.1.20:8080
```

#### 2）Home Assistant URL

例如：

```text
http://192.168.1.10:8123
```

#### 3）HA 长期访问令牌

粘贴刚才生成的 Token。

#### 4）小爱 TTS 实体 ID

填：

```text
text.xiaomi_lx06_e165_play_text
```

---

### B. 每日播报计划（可选）

如果你还希望每天固定播报，可配置这部分。

- **启用每日定时播报**：按需勾选
- **播报时刻**：例如 `07:30`
- **第二次 / 第三次播报时间**：不用就填 `00:00`
- **仅在法定工作日执行**：按需勾选

---

### C. 实体触发播报（本次重点）

#### 1）启用实体属性变化触发播报

勾选。

#### 2）监听实体 ID

填写：

```text
sensor.xiaomi_lx06_e165_conversation
```

#### 3）监听属性名

填写：

```text
content
```

#### 4）命中关键词（逗号分隔）

推荐填写：

```text
天气,天气怎么样,今天天气怎么样
```

如果你想更宽一点，也可以写：

```text
天气,天气怎么样,今天天气怎么样,今天天气,天气预报
```

#### 5）延迟播报（秒或 HH:MM:SS）

支持两种写法：

```text
30
```

或：

```text
00:00:30
```

如果你想延迟 2 分钟，也可以填：

```text
120
```

或：

```text
00:02:00
```

---

### D. 每日播报内容模板

这是给 **每日定时播报** 用的。

可以先用默认值，不必一开始就修改。

---

### E. 触发后播报模板

这是给 **问天气后 2 分钟补播实时花粉** 用的。

推荐模板：

```text
当前实时花粉情况是，{city}花粉风险{pollen_level}，花粉数值{pollen_score}。{pollen_message} {window_advice}{mask_advice}
```

也可以换成更口语一点的：

```text
现在给你补一条实时花粉情况。{city}当前花粉风险{pollen_level}，花粉数值{pollen_score}。{pollen_message} {window_advice}{mask_advice}
```

---

## 六、先验证与 HA 的连接

在控制台中依次点击：

### 1）保存配置

先保存。

### 2）检查连接

如果正常，应能确认：

- HA 地址可访问
- Token 有效
- 小爱实体存在

如果失败，优先检查：

- HA URL 是否正确
- Token 是否有效
- 容器是否能访问 HA
- 实体 ID 是否拼错

---

## 七、生成 Package YAML

在控制台里点击：

- **Package YAML 预览**
- **复制**

复制出来的 YAML 通常包含：

1. 从 `/api/ha/current` 读取数据的 REST sensor
2. 花粉 / AQI / 风险辅助模板实体
3. 小爱播报脚本
4. 每日定时播报自动化
5. 实体变化触发播报自动化（监听 `sensor.xiaomi_lx06_e165_conversation`）

---

## 八、把 YAML 放进 HA

在 HA 配置目录下新建文件：

```text
/config/packages/pollen_air.yaml
```

把刚才复制的 YAML **完整粘贴进去**，然后保存。

---

## 九、在 HA 中检查配置

在 Home Assistant 中：

- 打开 **开发者工具**
- 进入 **YAML**
- 点击 **检查配置**

如果报错，常见原因：

1. YAML 缩进被改坏了
2. `configuration.yaml` 没有开启 packages
3. 文件放错目录，不在 `/config/packages/`

---

## 十、重载或重启 Home Assistant

第一次接入 package，建议直接重启 HA，最省心。

### 方法 1：重启 HA

- **设置**
- **系统**
- **重启**

### 方法 2：在开发者工具中重载 YAML（不一定每次都够）

- 自动化
- 脚本
- 模板实体

如果重载后不完整，就直接重启。

---

## 十一、重启后检查是否生效

在 **开发者工具 → 状态** 中搜索以下实体。

### 1）核心原始数据实体

```text
sensor.pollen_air_ha_raw
```

这是整套配置的核心数据源。

### 2）模板实体

你应该能看到类似：

- 呼和浩特花粉等级
- 呼和浩特花粉提示
- 呼和浩特花粉数值
- 呼和浩特 AQI
- 呼和浩特空气质量等级
- 呼和浩特花粉是否风险
- 呼和浩特建议开窗
- 呼和浩特建议戴口罩

### 3）脚本实体

```text
script.xiaoai_broadcast_pollen_air
```

### 4）自动化实体

应至少包含：

- 每日小爱播报花粉和空气质量
- 小爱问天气后延迟播报实时花粉

---

## 十二、先做手动测试

不要一上来就只靠真实对话，先测链路。

### 测试 1：手动执行播报脚本

在 HA 中：

- 打开 **开发者工具**
- 进入 **服务**
- 选择服务：

```text
script.turn_on
```

- 目标实体选择：

```text
script.xiaoai_broadcast_pollen_air
```

执行。

#### 正常结果

小爱应该直接播报一段花粉信息。

#### 如果没播

优先检查：

- `text.xiaomi_lx06_e165_play_text` 是否还能正常播报
- 小爱设备是否在线
- HA 是否能控制这个实体

---

### 测试 2：检查花粉数据是否已读到

在 **开发者工具 → 状态** 查看：

```text
sensor.pollen_air_ha_raw
```

确认属性中包含：

- `pollen.level`
- `pollen.hf_num`
- `pollen.level_message`
- `pollen.open_window_recommended`
- `pollen.mask_recommended`

如果这些字段存在，说明后续播报内容有数据可用。

---

## 十三、测试“问天气后 2 分钟播报”

### 方法 1：直接对小爱说一句

例如：

```text
今天天气怎么样
```

然后等待 2 分钟。

### 预期动作链

自动化应依次完成：

1. 监听到 `sensor.xiaomi_lx06_e165_conversation` 变化
2. 读取 `content`
3. 判断内容包含“天气”类关键词
4. 延迟 2 分钟
5. 更新 `sensor.pollen_air_ha_raw`
6. 调用 `text.xiaomi_lx06_e165_play_text`
7. 小爱播报实时花粉

> 补充说明：当前生成的事件播报文本会在末尾自动附加时间戳，用于避免“文本完全相同导致设备不重复播报”的情况。

---

### 方法 2：查看自动化 trace

在 HA 中：

- **设置**
- **自动化与场景**
- 找到：
  `小爱问天气后延迟播报实时花粉`
- 查看 **追踪 / Traces**

这样可以看到：

- 是否真的触发了
- 卡在条件、延时还是服务调用

---

## 十四、如果没有触发，怎么排查

### 1）先确认会话实体有没有变化

在 **开发者工具 → 状态** 搜：

```text
sensor.xiaomi_lx06_e165_conversation
```

然后对小爱说一句：

```text
今天天气怎么样
```

看它的 `state` 或 `attributes` 是否更新。

如果完全没变化，那问题在小爱集成链路，不在 `pollen-air-ha`。

---

### 2）确认属性名到底是不是 `content`

虽然当前推荐填 `content`，但最稳的方法还是直接看 HA 状态页里的原始 attributes。

如果实际字段名不是 `content`，而是：

- `conversation`
- `query`
- `text`

那就把控制台里的监听属性名改掉，重新生成 package 并覆盖配置。

---

### 3）关键词是不是写太死了

如果只写：

```text
今天天气怎么样
```

那说“天气怎么样”时就不一定触发。

建议先宽松一点：

```text
天气,天气怎么样,今天天气怎么样
```

---

### 4）小爱播报实体还能不能手动播

在 **开发者工具 → 服务** 中测试：

服务：

```text
text.set_value
```

目标实体：

```text
text.xiaomi_lx06_e165_play_text
```

数据：

```yaml
value: 这是一条测试播报
```

如果这都不播，说明问题不在本项目，而在小爱播放链路本身。

---

### 5）看 trace，比猜强

Home Assistant 的自动化 trace 很有用，优先看它，别靠猜。

重点看：

- 有没有触发
- 条件是否通过
- 是否在 delay 中
- 调用服务时有没有报错

---

## 十五、推荐配置建议

对于当前场景，推荐这样配置：

### 每日播报

- 开启
- 比如早上 `07:30`

### 实体触发播报

- 开启
- 监听实体：

```text
sensor.xiaomi_lx06_e165_conversation
```

- 属性：

```text
content
```

- 关键词：

```text
天气,天气怎么样,今天天气怎么样
```

- 延迟：

```text
2
```

这样你会同时拥有：

1. 固定晨报
2. 问天气后的补充花粉播报

---

## 十六、相关文件

仓库中与 HA 对接最相关的文件：

- `docs/HOME_ASSISTANT.md`
- `docs/HOME_ASSISTANT.zh-CN.md`
- `examples/home-assistant/packages/pollen_air.yaml`

如果你只想快速抄配置，先看 example；
如果你想完整理解流程，再看这份手册。
