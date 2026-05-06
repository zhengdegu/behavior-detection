FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# ── 系统依赖：ffmpeg + OpenCV 运行时 ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libglib2.0-0 libgl1-mesa-glx curl \
    && rm -rf /var/lib/apt/lists/*

# ── go2rtc 二进制（RTSP 流代理 + WebRTC/MSE 播放器）──
ARG TARGETARCH=amd64
ARG GO2RTC_VERSION=1.9.14
ADD --chmod=755 \
    https://github.com/AlexxIT/go2rtc/releases/download/v${GO2RTC_VERSION}/go2rtc_linux_${TARGETARCH} \
    /app/data/go2rtc

WORKDIR /app

# ── PyTorch GPU（可选，CPU 版去掉 --index-url 行）──
RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cu124

# ── Python 依赖 ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 应用代码 ──
COPY src/ src/
COPY configs/ configs/

# ── 数据目录（模型、数据库、事件截图等）──
RUN mkdir -p data/models data/events data/uploads data/outputs

# Ports: 18000(FastAPI) + 1984(go2rtc API) + 8555(go2rtc RTSP)
EXPOSE 18000 1984 8555

ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

CMD ["python", "-m", "src.main"]
