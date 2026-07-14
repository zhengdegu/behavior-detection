# Behavior Detection System — 配置管理 API

> Base URL: `http://<host>:18000`
>
> 认证: `Authorization: Bearer <token>`

---

## 认证

### POST /api/auth/login

```json
// Request
{ "username": "admin", "password": "password123" }

// Response 200
{ "token": "eyJhbGciOiJIUzI1NiIs...", "username": "admin" }
```

---

## 摄像头配置

### GET /api/cameras

获取所有摄像头及其完整配置。

**Response 200:**

```json
[
  {
    "id": "cam01",
    "name": "大堂入口",
    "url": "rtsp://192.168.1.100:554/stream1",
    "online": true,
    "detect": { "fps": 5, "confidence": 0.5 },
    "roi": [
      [[0.1, 0.2], [0.9, 0.2], [0.9, 0.9], [0.1, 0.9]]
    ],
    "rules": {
      "crowd": { "enabled": true, "max_count": 5, "radius": 200, "confirm_frames": 5, "cooldown": 60 },
      "fight": { "enabled": true, "proximity_radius": 150, "min_speed": 80, "min_persons": 2, "confirm_frames": 6, "cooldown": 30 },
      "fall": { "enabled": false },
      "loiter": { "enabled": false }
    },
    "mqtt_publish": { "enabled": true, "crowd": true, "fight": true, "fall": true, "loiter": false }
  }
]
```

---

### POST /api/cameras

添加摄像头。

```json
// Request
{
  "id": "cam01",
  "name": "大堂入口",
  "url": "rtsp://192.168.1.100:554/stream1"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | ✅ | 唯一标识，不可重复 |
| name | string | ✅ | 名称 |
| url | string | ✅ | RTSP 流地址 |

---

### PUT /api/cameras/{camera_id}

更新摄像头配置。所有字段可选，仅传需要修改的。更新后自动重启检测。

```json
// Request
{
  "name": "大堂入口",
  "url": "rtsp://192.168.1.100:554/stream1",
  "detect": {
    "fps": 3,
    "confidence": 0.6
  },
  "roi": [
    [[0.1, 0.2], [0.8, 0.2], [0.8, 0.8], [0.1, 0.8]],
    [[0.3, 0.05], [0.7, 0.05], [0.7, 0.4], [0.3, 0.4]]
  ],
  "rules": {
    "crowd": {
      "enabled": true,
      "max_count": 5,
      "radius": 200,
      "confirm_frames": 5,
      "cooldown": 60,
      "roi": [],
      "schedule": { "enabled": false, "periods": [] }
    },
    "fight": {
      "enabled": true,
      "proximity_radius": 150,
      "min_speed": 80,
      "min_persons": 2,
      "confirm_frames": 6,
      "cooldown": 30,
      "co_move_cos_threshold": 0.7,
      "min_relative_speed": 40.0,
      "min_distance_variance": 10.0,
      "joint_overlap_threshold": 1
    },
    "fall": {
      "enabled": true,
      "ratio_threshold": 1.0,
      "min_ratio_change": 0.5,
      "min_y_drop": 20,
      "confirm_frames": 5,
      "cooldown": 30,
      "min_hip_velocity": 30.0,
      "spine_angle_threshold": 45.0,
      "inactivity_frames": 3,
      "inactivity_threshold": 15.0,
      "history_size": 10
    },
    "loiter": {
      "enabled": false,
      "min_duration": 60.0,
      "max_distance": 150.0,
      "max_displacement_ratio": 0.3,
      "min_total_path": 50.0,
      "trajectory_window": 60.0,
      "inertia": 3,
      "confirm_frames": 5,
      "cooldown": 120.0
    }
  },
  "mqtt_publish": {
    "enabled": true,
    "crowd": true,
    "fight": true,
    "fall": true,
    "loiter": false
  },
  "timezone": "Asia/Shanghai"
}
```

---

### DELETE /api/cameras/{camera_id}

删除摄像头。

```json
// Response 200
{ "message": "Camera 'cam01' deleted" }
```

---

## 检测规则参数

### 聚集检测 (crowd)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | bool | false | 是否启用 |
| max_count | int | 5 | 触发告警的最小聚集人数 |
| radius | float | 200 | 聚类距离阈值 (像素) |
| confirm_frames | int | 5 | 连续满足条件帧数才触发 |
| cooldown | float | 60 | 冷却时间 (秒) |

### 打架检测 (fight)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | bool | false | 是否启用 |
| proximity_radius | float | 150 | 近距离阈值 (像素) |
| min_speed | float | 80 | 运动速度阈值 (像素/秒) |
| min_persons | int | 2 | 最少参与人数 |
| confirm_frames | int | 6 | 连续确认帧数 |
| cooldown | float | 30 | 冷却时间 (秒) |
| co_move_cos_threshold | float | 0.7 | 同向运动余弦阈值 |
| min_relative_speed | float | 40.0 | 最小相对速度 |
| min_distance_variance | float | 10.0 | 最小距离方差 |
| joint_overlap_threshold | int | 1 | 关节侵入阈值 |

### 跌倒检测 (fall)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | bool | false | 是否启用 |
| ratio_threshold | float | 1.0 | bbox 宽高比阈值 |
| min_ratio_change | float | 0.5 | 宽高比最小变化量 |
| min_y_drop | float | 20 | 最小垂直下落距离 (像素) |
| confirm_frames | int | 5 | 连续确认帧数 |
| cooldown | float | 30 | 冷却时间 (秒) |
| min_hip_velocity | float | 30.0 | 臀部最小下落速度 |
| spine_angle_threshold | float | 45.0 | 脊柱角度阈值 (度) |
| inactivity_frames | int | 3 | 跌倒后静止确认帧数 |
| inactivity_threshold | float | 15.0 | 静止判定最大移动量 |
| history_size | int | 10 | 姿态历史缓冲大小 |

### 徘徊检测 (loiter)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | bool | false | 是否启用 |
| min_duration | float | 60.0 | 最小停留时间 (秒) |
| max_distance | float | 150.0 | 最大位移距离 (像素) |
| max_displacement_ratio | float | 0.3 | 净位移/总路径比 |
| min_total_path | float | 50.0 | 最小总路径 (像素) |
| trajectory_window | float | 60.0 | 轨迹分析窗口 (秒) |
| inertia | int | 3 | ROI 内连续帧数才开始计数 |
| confirm_frames | int | 5 | 连续确认帧数 |
| cooldown | float | 120.0 | 冷却时间 (秒) |

### 规则通用可选字段

| 参数 | 类型 | 说明 |
|------|------|------|
| roi | array | 该规则专属 ROI，空则用摄像头全局 ROI |
| schedule | object | 检测时间段，见下方 |

---

## ROI 格式

归一化坐标 (0~1)，多多边形，并集关系：

```json
[
  [[0.1, 0.2], [0.8, 0.2], [0.8, 0.9], [0.1, 0.9]],
  [[0.3, 0.05], [0.7, 0.05], [0.7, 0.4], [0.3, 0.4]]
]
```

- 坐标原点左上 (0,0)，右下 (1,1)
- 每个多边形至少 3 个顶点
- 空数组 `[]` = 全画面检测
- 兼容旧格式 `[[x,y], ...]` (单多边形)

---

## Schedule 配置

```json
{
  "enabled": true,
  "periods": [
    { "start": "08:00", "end": "18:00", "days": [0, 1, 2, 3, 4] },
    { "start": "22:00", "end": "06:00", "days": [0, 1, 2, 3, 4, 5, 6] }
  ]
}
```

| 参数 | 说明 |
|------|------|
| enabled | false = 24/7 检测 |
| periods[].start | "HH:MM" |
| periods[].end | "HH:MM"，支持跨午夜 |
| periods[].days | 0=周一, 6=周日 |

---

## MQTT 配置

### GET /api/mqtt/config

```json
// Response 200
{
  "host": "mqtt.example.com",
  "port": 1883,
  "username": "user",
  "password": "",
  "topic": "behavior-detection/events",
  "enabled": true,
  "update_interval": 30,
  "tls_enabled": false,
  "tls_insecure": false
}
```

### PUT /api/mqtt/config

```json
// Request
{
  "host": "mqtt.example.com",
  "port": 1883,
  "username": "user",
  "password": "secret",
  "topic": "behavior-detection/events",
  "enabled": true,
  "update_interval": 30,
  "tls_enabled": false,
  "tls_insecure": false
}
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| host | string | "" | Broker 地址 |
| port | int | 1883 | 端口 |
| username | string | "" | 用户名 |
| password | string | "" | 密码，空字符串=保留原密码 |
| topic | string | "behavior-detection/events" | 发布 Topic |
| enabled | bool | false | 是否启用 |
| update_interval | int | 30 | updating 消息间隔 (秒, 5-3600) |
| tls_enabled | bool | false | 启用 TLS |
| tls_insecure | bool | false | 跳过证书验证 |

### GET /api/mqtt/status

```json
{ "connected": true, "active_sessions": 3 }
```

---

## 错误响应

```json
{ "error": "Error description" }
```

| 状态码 | 说明 |
|--------|------|
| 400 | 参数错误 |
| 401 | 未认证 |
| 404 | 资源不存在 |
| 409 | ID 冲突 |
| 503 | 服务不可用 |

---

## 集成示例

```bash
# 登录
TOKEN=$(curl -s -X POST http://host:18000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | jq -r .token)

# 添加摄像头
curl -X POST http://host:18000/api/cameras \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"id":"cam01","name":"入口","url":"rtsp://admin:pass@192.168.1.10/stream"}'

# 配置规则
curl -X PUT http://host:18000/api/cameras/cam01 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "detect": {"fps": 3},
    "roi": [[[0.1,0.1],[0.9,0.1],[0.9,0.9],[0.1,0.9]]],
    "rules": {
      "crowd": {"enabled":true,"max_count":3},
      "fight": {"enabled":true},
      "fall":  {"enabled":true},
      "loiter":{"enabled":false}
    },
    "mqtt_publish": {"enabled":true,"crowd":true,"fight":true,"fall":true}
  }'

# 配置 MQTT
curl -X PUT http://host:18000/api/mqtt/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"host":"mqtt.server.com","port":1883,"topic":"alerts/behavior","enabled":true}'
```
