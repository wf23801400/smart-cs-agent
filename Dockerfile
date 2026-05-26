# ============================================
# Smart CS Agent — 生产级 Docker 镜像
# ============================================

# ── 阶段 1: 构建依赖 ──────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装构建工具（先换阿里云源，国内加速）
RUN sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# 先装依赖（利用 Docker 层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# ── 阶段 2: 运行时 ────────────────────────────
FROM python:3.11-slim

# 安全：非 root 运行
RUN groupadd -r csagent && useradd -r -g csagent csagent && \
    mkdir -p /home/csagent && chown -R csagent:csagent /home/csagent

WORKDIR /app

# 从构建阶段复制已安装的包
COPY --from=builder /root/.local /home/csagent/.local

# 复制项目代码
COPY backend/ ./backend/

# 创建数据目录并赋权
RUN mkdir -p /app/data/qdrant_db /app/data/mem0_qdrant /app/data/knowledge /app/logs && \
    chown -R csagent:csagent /app

# 确保 pip 包在 PATH 中
ENV PATH="/home/csagent/.local/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=prod

USER csagent

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

EXPOSE 8000

# Gunicorn + Uvicorn workers（生产级）
CMD ["gunicorn", "backend.main:app", \
     "--workers", "2", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "60"]
