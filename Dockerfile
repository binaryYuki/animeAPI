# Start from the base image
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base

# Define build arguments and environment variables
ARG COMMIT_ID
ENV COMMIT_ID=${COMMIT_ID}

ARG BUILD_AT
ENV BUILD_AT=${BUILD_AT}

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
    curl \
    pkg-config && \
    rm -rf /var/lib/apt/lists/* \
    && apt-get clean


# Copy the source code into the container in the final stage
FROM base AS final

# Set working directory
WORKDIR /app

# Copy the source code into the container
COPY . .

RUN chown -R appuser:appuser /app
# Switch to the non-privileged user to run the application.
USER appuser

# Expose the port that the application listens on.
EXPOSE 8000

RUN uv sync

# Run the application
CMD ["uv", "run", "--with", "gunicorn", "gunicorn", "app:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
