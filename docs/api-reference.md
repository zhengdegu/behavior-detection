# Behavior Detection System — 配置管理 API

> Base URL: `http://75.50.58.28:18000`
>
> 认证: `Authorization: Bearer <token>`

---

## 认证

### POST /api/auth/login

```json
// Request
{ "username": "admin", "password": "Item@2025." }

// Response 200
{ "token": "eyJhbGciOiJIUzI1NiIs...", "username": "admin" }
```

| 状态码 | 说明 | Response Body |
|--------|------|--------------|
| 200 | 登录成功，返回 token | `{ "token": "eyJhbGciOiJIUzI1NiIs...", "username": "admin" }` |
| 400 | 请求体格式错误或缺少字段 | `{ "error": "Missing required field: username" }` |
| 401 | 用户名或密码错误 | `{ "error": "Invalid username or password" }` |

---

## 摄像头配置

### GET /api/cameras

获取所有摄像头及其完整配置。

| 状态码 | 说明 | Response Body |
|--------|------|--------------|
| 200 | 成功，返回摄像头列表 | `[ { "id": "cam01", "name": "大堂入口", ... } ]` |
| 401 | 未认证或 token 过期 | `{ "error": "Not authenticated" }` |

**Response 200:**

```json
[
  {
    "id": "cam01",
    "name": "大堂入口",
    "url": "rtsp://192.168.1.100:554/stream1",
    "online": true,
    "detect": { "fps": 5, "confidence": 0.5 },
    "rules": {
      "crowd": {
        "enabled": true,
        "schedule": { "enabled": false, "periods": [] },
        "zones": [
          {
            "roi": [[0.1, 0.2], [0.4, 0.2], [0.4, 0.6], [0.1, 0.6]],
            "name": "入口区域",
            "max_count": 5,
            "radius": 200,
            "confirm_frames": 5,
            "cooldown": 60
          },
          {
            "roi": [[0.5, 0.3], [0.9, 0.3], [0.9, 0.9], [0.5, 0.9]],
            "name": "通道区域",
            "max_count": 8,
            "radius": 200,
            "confirm_frames": 5,
            "cooldown": 60
          }
        ]
      },
      "fight": {
        "enabled": true,
        "schedule": { "enabled": false, "periods": [] },
        "zones": [
          {
            "roi": [[0.1, 0.2], [0.9, 0.2], [0.9, 0.9], [0.1, 0.9]],
            "name": "主区域",
            "proximity_radius": 150,
            "min_speed": 80,
            "min_persons": 2,
            "confirm_frames": 6,
            "cooldown": 30,
            "co_move_cos_threshold": 0.7,
            "min_relative_speed": 40.0,
            "min_distance_variance": 10.0,
            "joint_overlap_threshold": 1
          }
        ]
      },
      "fall": {
        "enabled": false,
        "schedule": { "enabled": false, "periods": [] },
        "zones": []
      },
      "loiter": {
        "enabled": false,
        "schedule": { "enabled": false, "periods": [] },
        "zones": []
      }
    },
    "mqtt_publish": { "enabled": true, "crowd": true, "fight": true, "fall": true, "loiter": false }
  }
]
```

> **说明:** 当 `zones` 非空时，引擎使用各 Zone 的独立 ROI 和参数进行检测。`zones` 为空时该规则不执行区域检测（向后兼容模式可使用规则顶层参数）。

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

| 状态码 | 说明 | Response Body |
|--------|------|--------------|
| 200 | 添加成功 | `{ "message": "Camera 'cam01' created", "id": "cam01" }` |
| 400 | 请求体格式错误或缺少必填字段 | `{ "error": "Missing required field: url" }` |
| 401 | 未认证或 token 过期 | `{ "error": "Not authenticated" }` |
| 409 | 摄像头 ID 已存在 | `{ "error": "Camera 'cam01' already exists" }` |

---

### PUT /api/cameras/{camera_id}

更新摄像头配置。所有字段可选，仅传需要修改的。更新后自动重启检测。

| 状态码 | 说明 | Response Body |
|--------|------|--------------|
| 200 | 更新成功 | `{ "message": "Camera 'cam01' updated" }` |
| 400 | 请求体格式错误 | `{ "error": "Invalid JSON body" }` |
| 401 | 未认证或 token 过期 | `{ "error": "Not authenticated" }` |
| 404 | 摄像头不存在 | `{ "error": "Camera 'cam01' not found" }` |
| 422 | 参数校验失败（如 ROI 顶点数不合法） | `{ "error": "ROI must have 0 or >= 3 vertices" }` |

```json
// Request
{
  "name": "大堂入口",
  "url": "rtsp://192.168.1.100:554/stream1",
  "detect": {
    "fps": 3,
    "confidence": 0.6
  },
  "rules": {
    "crowd": {
      "enabled": true,
      "schedule": { "enabled": false, "periods": [] },
      "zones": [
        {
          "roi": [[0.1, 0.1], [0.4, 0.1], [0.4, 0.5], [0.1, 0.5]],
          "name": "入口",
          "max_count": 5,
          "radius": 200,
          "confirm_frames": 5,
          "cooldown": 60
        }
      ]
    },
    "fight": {
      "enabled": true,
      "schedule": { "enabled": false, "periods": [] },
      "zones": [
        {
          "roi": [[0.1, 0.2], [0.9, 0.2], [0.9, 0.9], [0.1, 0.9]],
          "name": "主区域",
          "proximity_radius": 150,
          "min_speed": 80,
          "min_persons": 2,
          "confirm_frames": 6,
          "cooldown": 30,
          "co_move_cos_threshold": 0.7,
          "min_relative_speed": 40.0,
          "min_distance_variance": 10.0,
          "joint_overlap_threshold": 1
        }
      ]
    },
    "fall": {
      "enabled": true,
      "schedule": { "enabled": false, "periods": [] },
      "zones": [
        {
          "roi": [],
          "name": "全画面",
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
        }
      ]
    },
    "loiter": {
      "enabled": false,
      "schedule": { "enabled": false, "periods": [] }
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

| 状态码 | 说明 | Response Body |
|--------|------|--------------|
| 200 | 删除成功 | `{ "message": "Camera 'cam01' deleted" }` |
| 401 | 未认证或 token 过期 | `{ "error": "Not authenticated" }` |
| 404 | 摄像头不存在 | `{ "error": "Camera 'cam01' not found" }` |

---

### PUT /api/cameras/{camera_id}/rules/{rule_type}

按摄像头和算法类型保存检测规则配置。仅更新传入的字段，未传的字段保持原值。更新后自动重启检测。

**路径参数：**

| 参数 | 说明 |
|------|------|
| camera_id | 摄像头 ID |
| rule_type | 算法类型：`crowd`、`fight`、`fall`、`loiter` |

**Request Body（仅传需要修改的字段）：**

```json
// 示例：更新 cam01 的聚集检测配置
PUT /api/cameras/cam01/rules/crowd

{
  "enabled": true,
  "zones": [
    {
      "roi": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.6], [0.1, 0.6]],
      "name": "入口",
      "max_count": 3,
      "radius": 180,
      "confirm_frames": 5,
      "cooldown": 60,
    }
  ]
}
```

```json
// 示例：更新 cam01 的打架检测配置
PUT /api/cameras/cam01/rules/fight

{
  "enabled": true,
  "zones": [
    {
      "roi": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.6], [0.1, 0.6]],
      "name": "入口",
      "max_count": 3,
      "radius": 180,
      "confirm_frames": 5,
      "cooldown": 60,
    }
  ]
}
```

| 状态码 | 说明 | Response Body |
|--------|------|--------------|
| 200 | 更新成功 | `{ "message": "Rule 'crowd' updated for camera 'cam01'", "camera_id": "cam01", "rule_type": "crowd", "config": { ... } }` |
| 400 | rule_type 无效或请求体格式错误 | `{ "error": "Invalid rule_type 'xxx'. Must be one of: crowd, fight, fall, loiter" }` |
| 401 | 未认证或 token 过期 | `{ "error": "Not authenticated" }` |
| 404 | 摄像头不存在 | `{ "error": "Camera 'cam01' not found" }` |
| 422 | 参数校验失败 | `{ "error": "Parameter validation failed: ..." }` |

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
| zones | array | 区域级参数配置列表，见下方 Zone 配置 |

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

## Zone 配置（区域级参数）

每条规则可包含一个 `zones` 数组，为不同区域设置独立的检测参数。

### 行为逻辑

- `zones` 为空或不存在：使用规则顶层 `roi` + 参数（向后兼容）
- `zones` 非空：忽略规则顶层 `roi`，为每个 Zone 独立执行检测
- 每个 Zone 的参数未设置时，继承规则顶层默认值
- 每个 Zone 维护独立的状态（confirm 计数、cooldown 等）
- Zone 产生的告警事件包含 `zone_name` 字段

### Zone 对象结构

```json
{
  "roi": [[0.1, 0.1], [0.4, 0.1], [0.4, 0.5], [0.1, 0.5]],
  "name": "入口区域",
  "max_count": 3,
  "confirm_frames": 3
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| roi | array | ✅ | 单多边形，归一化坐标。空 `[]` = 全画面，≥3 顶点 = 有效多边形 |
| name | string | - | 区域名称，出现在告警事件的 `zone_name` 字段 |
| _(检测参数)_ | number | - | 该规则类型的任意参数，设置则覆盖规则默认值，不设置则继承 |

### 支持的覆盖参数

Zone 可覆盖对应规则的所有数值参数，例如：

- crowd: `max_count`, `radius`, `confirm_frames`, `cooldown`
- fight: `proximity_radius`, `min_speed`, `min_persons`, `co_move_cos_threshold`, ...
- fall: `ratio_threshold`, `min_ratio_change`, `min_y_drop`, `min_hip_velocity`, ...
- loiter: `min_duration`, `max_distance`, `max_displacement_ratio`, `min_total_path`, ...

### 验证规则

- `roi` 长度为 0（全画面）或 ≥ 3（有效多边形），1-2 个顶点返回 422
- 数值参数执行与规则顶层相同的范围约束
- 不允许未定义的额外字段（`extra="forbid"`）

### 示例：同一规则不同区域不同灵敏度

```json
{
  "crowd": {
    "enabled": true,
    "zones": [
      {
        "roi": [[0.0, 0.0], [0.5, 0.0], [0.5, 1.0], [0.0, 1.0]],
        "name": "入口",
        "max_count": 5,
        "radius": 200,
        "confirm_frames": 5,
        "cooldown": 60
      },
      {
        "roi": [[0.5, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 1.0]],
        "name": "通道",
        "max_count": 8
      },
      {
        "roi": [],
        "name": "全画面兜底",
        "max_count": 10
      }
    ]
  }
}
```

> Zone 中未设置的参数自动继承规则顶层默认值（如 `max_count`=5, `radius`=200 等）。上例中"通道"和"全画面兜底"仅覆盖了 `max_count`，其余参数均从顶层继承。

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

## 错误响应

```json
{ "error": "Error description" }
```

| 状态码 | 说明 | Response Body |
|--------|------|--------------|
| 400 | 参数错误 | `{ "error": "具体错误描述" }` |
| 401 | 未认证 | `{ "error": "Not authenticated" }` |
| 404 | 资源不存在 | `{ "error": "Camera '{id}' not found" }` |
| 409 | ID 冲突 | `{ "error": "Camera '{id}' already exists" }` |
| 422 | 参数校验失败 | `{ "error": "具体校验错误描述" }` |
| 503 | 服务不可用 | `{ "error": "Service unavailable" }` |

---

## 集成示例

### Shell (curl)

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
    "rules": {
      "crowd": {"enabled":true,"max_count":3},
      "fight": {"enabled":true},
      "fall":  {"enabled":true},
      "loiter":{"enabled":false}
    },
    "mqtt_publish": {"enabled":true,"crowd":true,"fight":true,"fall":true}
  }'
```

### Java (HttpClient)

```java
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

public class BehaviorDetectionClient {

    private static final String BASE_URL = "http://75.50.58.28:18000";
    private final HttpClient client = HttpClient.newHttpClient();
    private final ObjectMapper mapper = new ObjectMapper();
    private String token;

    /**
     * 登录获取 token
     */
    public void login(String username, String password) throws Exception {
        String body = mapper.writeValueAsString(
            Map.of("username", username, "password", password)
        );

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(BASE_URL + "/api/auth/login"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

        switch (response.statusCode()) {
            case 200:
                JsonNode json = mapper.readTree(response.body());
                this.token = json.get("token").asText();
                break;
            case 401:
                throw new RuntimeException("认证失败: 用户名或密码错误");
            default:
                throw new RuntimeException("登录失败, HTTP " + response.statusCode() + ": " + response.body());
        }
    }

    /**
     * 获取所有摄像头配置
     */
    public String getCameras() throws Exception {
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(BASE_URL + "/api/cameras"))
            .header("Authorization", "Bearer " + token)
            .GET()
            .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

        switch (response.statusCode()) {
            case 200:
                return response.body();
            case 401:
                throw new RuntimeException("Token 无效或已过期，请重新登录");
            default:
                throw new RuntimeException("获取摄像头失败, HTTP " + response.statusCode());
        }
    }

    /**
     * 添加摄像头
     */
    public void addCamera(String id, String name, String rtspUrl) throws Exception {
        String body = mapper.writeValueAsString(
            Map.of("id", id, "name", name, "url", rtspUrl)
        );

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(BASE_URL + "/api/cameras"))
            .header("Authorization", "Bearer " + token)
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

        switch (response.statusCode()) {
            case 200:
                System.out.println("摄像头添加成功: " + id);
                break;
            case 400:
                throw new RuntimeException("参数错误: " + response.body());
            case 401:
                throw new RuntimeException("Token 无效或已过期");
            case 409:
                throw new RuntimeException("摄像头 ID 已存在: " + id);
            default:
                throw new RuntimeException("添加失败, HTTP " + response.statusCode() + ": " + response.body());
        }
    }

    /**
     * 更新摄像头配置
     */
    public void updateCamera(String cameraId, String configJson) throws Exception {
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(BASE_URL + "/api/cameras/" + cameraId))
            .header("Authorization", "Bearer " + token)
            .header("Content-Type", "application/json")
            .PUT(HttpRequest.BodyPublishers.ofString(configJson))
            .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

        switch (response.statusCode()) {
            case 200:
                System.out.println("摄像头配置更新成功: " + cameraId);
                break;
            case 400:
                throw new RuntimeException("请求格式错误: " + response.body());
            case 401:
                throw new RuntimeException("Token 无效或已过期");
            case 404:
                throw new RuntimeException("摄像头不存在: " + cameraId);
            case 422:
                throw new RuntimeException("参数校验失败: " + response.body());
            default:
                throw new RuntimeException("更新失败, HTTP " + response.statusCode() + ": " + response.body());
        }
    }

    /**
     * 删除摄像头
     */
    public void deleteCamera(String cameraId) throws Exception {
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(BASE_URL + "/api/cameras/" + cameraId))
            .header("Authorization", "Bearer " + token)
            .DELETE()
            .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

        switch (response.statusCode()) {
            case 200:
                System.out.println("摄像头删除成功: " + cameraId);
                break;
            case 401:
                throw new RuntimeException("Token 无效或已过期");
            case 404:
                throw new RuntimeException("摄像头不存在: " + cameraId);
            default:
                throw new RuntimeException("删除失败, HTTP " + response.statusCode() + ": " + response.body());
        }
    }

    /**
     * 按摄像头+算法类型保存规则配置
     * @param cameraId 摄像头ID
     * @param ruleType 算法类型: crowd, fight, fall, loiter
     * @param ruleConfigJson 规则配置JSON（仅传需要修改的字段）
     */
    public String saveRuleConfig(String cameraId, String ruleType, String ruleConfigJson) throws Exception {
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(BASE_URL + "/api/cameras/" + cameraId + "/rules/" + ruleType))
            .header("Authorization", "Bearer " + token)
            .header("Content-Type", "application/json")
            .PUT(HttpRequest.BodyPublishers.ofString(ruleConfigJson))
            .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

        switch (response.statusCode()) {
            case 200:
                System.out.println("规则配置保存成功: " + cameraId + "/" + ruleType);
                return response.body();
            case 400:
                throw new RuntimeException("参数错误(rule_type无效或JSON格式错误): " + response.body());
            case 401:
                throw new RuntimeException("Token 无效或已过期");
            case 404:
                throw new RuntimeException("摄像头不存在: " + cameraId);
            case 422:
                throw new RuntimeException("参数校验失败: " + response.body());
            default:
                throw new RuntimeException("保存失败, HTTP " + response.statusCode() + ": " + response.body());
        }
    }
}
```
