# Start from the base image
ARG PYTHON_VERSION=3.12.4
FROM python:${PYTHON_VERSION}-slim AS base

# Define build arguments and environment variables
ARG COMMIT_ID
ENV COMMIT_ID=${COMMIT_ID}

ARG BUILD_AT
ENV BUILD_AT=${BUILD_AT}

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr.
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

# Setup Python environment in a distinct build stage
FROM base AS builder

WORKDIR /app

# Install uv package
RUN pip install uv

# Create a virtual environment and install dependencies
RUN uv venv -p 3.12 && \
    uv pip install --upgrade pip

# Leverage a cache mount to speed up subsequent builds
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    . .venv/bin/activate && uv pip sync requirements.txt && \
    uv pip install gunicorn

# Copy the source code into the container in the final stage
FROM base AS final

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
