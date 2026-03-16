# ============================================================
# AgentsOffice - 多阶段构建
# Stage 1: Node.js 构建前端
# Stage 2: Python 运行后端（含构建好的前端）
# ============================================================

# --- Stage 1: 构建前端 ---
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
# 构建产物在 /build/../app/static/office/ → 实际是 /app/static/office/

# --- Stage 2: Python 后端 ---
FROM python:3.11-slim
WORKDIR /app

# 安装系统依赖（psycopg2 需要 libpq）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY app/ ./app/
COPY scripts/ ./scripts/

# 复制构建好的前端到 app/static/office/
COPY --from=frontend-build /app/static/office/ ./app/static/office/

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
