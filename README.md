# Behavior Detection — 行为异常检测系统

实时视频行为异常检测系统，支持 **聚集检测**、**打架检测**、**跌倒检测**，前后端打包为单一 Docker 镜像，支持 MQTT 事件推送到第三方系统。

## 功能

| 功能 | 说明 |
|------|------|
| 聚集检测 (Crowd) | 基于连通分量聚类，区域内人数超过阈值告警 |
| 打架检测 (Fight) | 多人近距离 + 高速运动 + Pose 姿态增强（手腕挥拳特征） |
| 跌倒检测 (Fall) | bbox 宽高比突变 + Pose 姿态增强（头低于臀部） |
| 视频分析 | 上传视频文件离线分析，生成标注视频和事件报告 |
| MQTT 推送 | 事件生命周期（triggered → updating → resolved）推送到外部系统 |
| 实时预览 | 通过 go2rtc WebRTC/MSE 低延迟预览摄像头画面 |

## 技术栈

**后端：** Python 3.12 · FastAPI · YOLO (Ultralytics) · ByteTrack · YOLO Pose · OpenCV · SQLite · paho-mqtt

**前端：** React 19 · TypeScript · Vite · Tailwind CSS v4

**基础设施：** Docker 多阶段构建 · go2rtc (RTSP 代理) · NVIDIA GPU 支持

## 快速开始

### Docker 部署（推荐）

```bash
# 克隆仓库
git clone https://github.com/zhengdegu/behavior-detection.git
cd behavior-detection

# 启动（需要 NVIDIA GPU + nvidia-container-toolkit）
docker compose up -d --build

# 访问 http://localhost:8000
```

### 拉取预构建镜像

```bash
docker pull ghcr.io/zhengdegu/behavior-detection:latest
```

使用 docker-compose 运行预构建镜像：

```yaml
# docker-compose.yml
services:
  behavior-detection:
    image: ghcr.io/zhengdegu/behavior-detection:latest
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./configs:/app/configs
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    restart: unless-stopped
```

```bash
docker compose up -d
```

### 本地开发

```bash
# 后端
cd backend
pip install -r requirements.txt
python -m src.main
# API 运行在 http://localhost:8000

# 前端（另一个终端）
cd frontend
npm install
npm run dev
# 开发服务器运行在 http://localhost:5173，自动代理 API 到 8000
```

## 使用说明

### 1. 添加摄像头

打开 `http://localhost:8000`，进入 **Config** 页面：

1. 点击 **+ Add** 按钮
2. 填写 Camera ID、名称、RTSP URL
3. 点击 **Create**

摄像头添加后会自动开始拉流和检测。

### 2. 配置检测规则

在 Config 页面选择一个摄像头：

- **ROI 区域**：在左侧画布上点击绘制检测区域（多边形），只有区域内的人员才会触发告警
- **Detection Rules**：在右侧配置三种检测规则的参数和开关
  - **Crowd**：`max_count`（触发人数阈值）、`radius`（聚集半径 px）、`cooldown`（冷却时间 s）
  - **Fight**：`proximity_radius`（近距离阈值 px）、`min_speed`（最小运动速度 px/s）
  - **Fall**：`ratio_threshold`（宽高比阈值）、`min_y_drop`（最小下移距离 px）

点击 **Save Configuration** 保存，摄像头会自动重启应用新配置。

### 3. 实时监控

进入 **Live** 页面：

- 左侧：摄像头网格，通过 go2rtc WebRTC 低延迟预览，检测框实时叠加
- 右侧：Event Feed，实时显示告警事件（聚集/打架/跌倒）

### 4. 事件查看

进入 **Events** 页面：

- 按事件类型过滤（All / Crowd / Fight / Fall）
- 查看事件截图、时间、摄像头、详情
- 点击截图可放大查看

### 5. 视频分析

进入 **Analyze** 页面：

1. 上传视频文件
2. 配置 ROI 和检测规则（可选）
3. 点击开始分析
4. 分析完成后可查看事件列表和下载标注视频

### 6. MQTT 事件推送

#### 全局配置

进入 **System** 页面底部的 MQTT Configuration 区域：

1. 填写 Broker 地址和端口
2. 填写第三方指定的 Topic
3. 填写用户名/密码（如需要）
4. 设置 updating 消息间隔（默认 30 秒）
5. 勾选 **Enable MQTT Publishing**
6. 点击 **Save MQTT Config**

#### 摄像头级别配置

在 **Config** 页面选择摄像头，在 Detection Rules 下方的 MQTT Publishing 区域：

1. 勾选 **Enable MQTT for this camera**
2. 选择要推送的事件类型（Crowd / Fight / Fall）
3. 保存配置

#### MQTT 消息格式

事件遵循生命周期模型，同一事件只发送一次 triggered，持续期间按间隔发送 updating，消失后发送 resolved：

```json
{
  "event_id": "evt_cam01_crowd_20260429_143052",
  "status": "triggered",
  "type": "crowd",
  "camera_id": "cam01",
  "camera_name": "大厅入口",
  "timestamp": "2026-04-29T14:30:52+08:00",
  "detail": "聚集告警：6人在半径200px内聚集",
  "data": {
    "count": 6,
    "track_ids": [1, 3, 5, 7, 9, 12],
    "bbox": [120, 80, 580, 420],
    "confidence": 0.85
  },
  "image_url": "events/cam01_crowd_t1_20260429_143052_123.jpg",
  "duration": 0.0
}
```

| status | 说明 | 发送时机 |
|--------|------|----------|
| `triggered` | 首次检测到异常 | 立即发送 |
| `updating` | 异常持续中 | 每 N 秒发送一次（可配置） |
| `resolved` | 异常消失 | 检测到异常消失时发送 |

## YOLO 模型

系统需要 YOLO 模型文件，放置在 `data/models/` 目录下：

- `yolo26m.pt` — 目标检测模型（必需）
- `yolo26m-pose.pt` — 姿态估计模型（可选，增强打架/跌倒检测精度）

首次启动前需要手动下载模型文件到 `data/models/` 目录。

## API 参考

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/cameras` | 摄像头列表 |
| POST | `/api/cameras` | 添加摄像头 |
| PUT | `/api/cameras/{id}` | 更新摄像头配置 |
| DELETE | `/api/cameras/{id}` | 删除摄像头 |
| GET | `/api/cameras/{id}/snapshot` | 获取摄像头快照 |
| GET | `/api/events` | 事件列表（支持 sub_type、camera_id、limit 过滤） |
| GET | `/api/status` | 系统状态 |
| POST | `/api/video-analysis/upload` | 上传视频 |
| GET | `/api/video-analysis/tasks` | 分析任务列表 |
| POST | `/api/video-analysis/tasks/{id}/start` | 启动分析 |
| GET | `/api/mqtt/config` | 获取 MQTT 配置 |
| PUT | `/api/mqtt/config` | 更新 MQTT 配置 |
| GET | `/api/mqtt/status` | MQTT 连接状态 |
| WS | `/ws/events` | 实时事件推送 |
| WS | `/ws/detections/{camera_id}` | 实时检测框推送 |

## 项目结构

```
behavior-detection/
├── backend/
│   ├── src/
│   │   ├── main.py              # 主入口
│   │   ├── server.py            # FastAPI Web 服务 + REST API
│   │   ├── config.py            # Pydantic 配置模型
│   │   ├── database.py          # SQLite 数据库 + Repository
│   │   ├── analyzer.py          # 视频分析管线（每路摄像头一个线程）
│   │   ├── detector.py          # YOLO 检测器 + Pose 检测器
│   │   ├── detection.py         # Detection 数据类
│   │   ├── geometry.py          # 几何工具（点在多边形内判定）
│   │   ├── go2rtc.py            # go2rtc 流管理（RTSP 代理）
│   │   ├── mqtt_publisher.py    # MQTT 发布器（paho-mqtt v2）
│   │   ├── event_session.py     # 事件会话管理器（生命周期 + 合并）
│   │   └── rules/               # 行为规则引擎
│   │       ├── engine.py        # 规则聚合
│   │       ├── base.py          # 规则基类（confirm + cooldown）
│   │       ├── crowd.py         # 聚集检测
│   │       ├── fight.py         # 打架检测
│   │       └── fall.py          # 跌倒检测
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/               # Live / Events / Config / Analyze / System
│   │   ├── components/          # CameraGrid / Go2RTCPlayer / RoiEditor / ...
│   │   ├── hooks/               # useWebSocket / useDetectionWebSocket
│   │   ├── api.ts               # API 客户端
│   │   └── types.ts             # TypeScript 类型定义
│   └── package.json
├── Dockerfile                    # 多阶段构建（Node.js + Python）
├── docker-compose.yml
└── .github/workflows/
    └── build-image.yml           # GitHub Actions 自动构建镜像
```

## 端口说明

系统仅对外暴露一个端口：

| 端口 | 说明 |
|------|------|
| 8000 | FastAPI（前端 + 后端 API + go2rtc 代理） |

go2rtc 的 1984（API）和 8555（RTSP）端口仅在容器内部使用，所有请求通过 FastAPI 反向代理转发。
