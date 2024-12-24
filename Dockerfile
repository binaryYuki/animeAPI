# Start from the base image
ARG PYTHON_VERSION=3.12.4
FROM python:${PYTHON_VERSION}-slim AS base

# Define build arguments and environment variables
ARG COMMIT_ID
ENV COMMIT_ID=${COMMIT_ID}

ARG BUILD_AT
ENV BUILD_AT=${BUILD_AT}

# 防止 Python 生成 pyc 文件
ENV PYTHONDONTWRITEBYTECODE=1

# 防止 Python 缓存 stdout 和 stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create a non-privileged user for the app.
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/home/appuser" \
    --shell "/sbin/nologin" \
    --uid "${UID}" \
    appuser

# Install required packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmariadb-dev-compat \
    libmariadb-dev \
    pkg-config && \
    rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装 Python 依赖
COPY requirements.txt .

# 安装依赖时禁用缓存以减少镜像体积
RUN uv venv -p 3.12 && \
    . .venv/bin/activate && \
    uv pip install --no-cache-dir --upgrade pip && \
    uv pip sync requirements.txt --no-cache-dir

# Set working directory
WORKDIR /app

# Copy the prepared virtual environment and source code
COPY --from=builder /app/.venv /app/.venv
COPY . .

# Change ownership to the appuser
RUN chown -R appuser:appuser /app

# Switch to the non-privileged user to run the application.
USER appuser

# Expose the port that the application listens on.
EXPOSE 8000

# Run the application
CMD [".venv/bin/gunicorn", "app:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
