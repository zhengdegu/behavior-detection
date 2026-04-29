# Behavior Detection — 行为异常检测系统

从 warehouse-vision 项目中拆分出的独立行为检测子系统，专注于 **聚集检测**、**打架检测**、**跌倒检测** 三项核心能力。

## 功能

| 功能 | 说明 |
|------|------|
| 聚集检测 (Crowd) | 基于连通分量聚类，区域内人数超过阈值告警 |
| 打架检测 (Fight) | 多人近距离 + 高速运动 + Pose 姿态增强（手腕挥拳特征） |
| 跌倒检测 (Fall) | bbox 宽高比突变 + Pose 姿态增强（头低于臀部） |

## 技术栈

- Python 3.12 + FastAPI + Uvicorn
- YOLO (Ultralytics) 目标检测 + ByteTrack 跟踪
- YOLO Pose 姿态估计（增强打架/跌倒精度）
- OpenCV 运动检测预过滤
- React 19 + TypeScript + Vite + Tailwind CSS 前端
- Docker 部署

## 快速开始

```bash
# 后端：安装依赖 & 启动服务
pip install -r backend/requirements.txt
cd backend && python -m src.main

# 前端：安装依赖 & 启动开发服务器
cd frontend && npm install && npm run dev

# 访问 http://localhost:8000（后端 API）
# 访问 http://localhost:5173（前端开发服务器）
```

## Docker 部署

```bash
docker-compose up -d --build
```

## 项目结构

```
behavior-detection/
├── backend/                      # Python 后端
│   ├── src/
│   │   ├── main.py              # 主入口
│   │   ├── config.py            # 配置模型 (Pydantic)
│   │   ├── detection.py         # Detection 数据类
│   │   ├── detector.py          # YOLO 检测器 + Pose 检测器
│   │   ├── geometry.py          # 几何工具
│   │   ├── rules/               # 行为规则引擎
│   │   │   ├── base.py          # 规则基类
│   │   │   ├── crowd.py         # 聚集检测
│   │   │   ├── fight.py         # 打架检测
│   │   │   ├── fall.py          # 跌倒检测
│   │   │   └── engine.py        # 规则引擎聚合
│   │   ├── analyzer.py          # 视频分析管线
│   │   └── server.py            # FastAPI Web 服务
│   ├── configs/
│   │   └── default.yaml         # 默认配置
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                     # React 前端
│   ├── src/
│   │   ├── main.tsx             # 应用入口
│   │   ├── App.tsx              # 路由配置
│   │   ├── api.ts               # API 客户端
│   │   ├── types.ts             # TypeScript 类型
│   │   ├── utils.ts             # 工具函数
│   │   ├── components/          # UI 组件
│   │   ├── hooks/               # 自定义 Hooks
│   │   ├── pages/               # 页面组件
│   │   └── __tests__/           # 属性测试
│   ├── package.json
│   ├── vite.config.ts
│   └── index.html
├── docs/
├── docker-compose.yml
└── README.md
```

## 配置

编辑 `backend/configs/default.yaml`：

```yaml
cameras:
  - id: "cam01"
    name: "入口摄像头"
    url: "rtsp://admin:password@192.168.1.100:554/stream"
    detect:
      fps: 5
      confidence: 0.5
    rules:
      crowd:
        enabled: true
        max_count: 5
        radius: 200
      fight:
        enabled: true
        proximity_radius: 150
        min_speed: 60
      fall:
        enabled: true
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/cameras` | 摄像头列表 |
| GET | `/api/events` | 事件列表（分页、过滤） |
| GET | `/stream/{camera_id}` | MJPEG 实时视频流 |
| WS | `/ws/events` | 实时事件 WebSocket 推送 |
| GET | `/api/status` | 系统状态 |
