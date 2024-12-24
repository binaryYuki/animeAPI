# Anime API Project

THIS PROJECT IS ONLY FOR EDUCATIONAL PURPOSES. DO NOT USE IT FOR COMMERCIAL PURPOSES.

## Overview

This project is a Python-based web application with a framework of video player's backend that uses FastAPI for the
backend. It includes health checks for Redis and MySQL, middleware for processing time, and session management. The
application is containerized using Docker.

## Features

- FastAPI backend
- Health checks for Redis and MySQL
- Middleware for processing time
- Session management
- CORS support
- GZip compression

## Requirements

- Python 3.12.4
- Docker
- Redis
- MySQL

## Installation

### Prerequisites

1. Install Python 3.12.4:
    ```sh
    sudo apt update
    sudo apt install python3.12
    ```

2. Install Docker:
    ```sh
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    ```

### Using Docker

1. Clone the repository:
    ```sh
    git clone https://github.com/binaryYuki/oleapi.git
    cd oleapi.git
    ```

2. Build the Docker image:
    ```sh
    docker build --build-arg COMMIT_ID=$(git rev-parse HEAD) --build-arg BUILD_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ") -t oleapi:latest .
    ```

3. Run the Docker container:
    ```sh
    docker run -p 8000:8000 -e SESSION_SECRET=$(python -c 'import binascii, os; print(binascii.hexlify(os.urandom(16)).decode()') oleapi:latest
    ```

### Without Docker

1. Clone the repository:
    ```sh
    git clone https://github.com/binaryYuki/oleapi.git
    cd oleapi
    ```

2. Create a virtual environment and activate it:
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install the dependencies:
    ```sh
    pip install -r requirements.txt
    ```

4. Set environment variables:
    ```sh
    export COMMIT_ID=$(git rev-parse HEAD)
    export BUILD_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    export SESSION_SECRET=$(python -c 'import binascii, os; print(binascii.hexlify(os.urandom(16)).decode())')
    ```

5. Run the application:
    ```sh
    uvicorn app:app --host 0.0.0.0 --port 8000
    ```

## Endpoints

### Health Check

- **GET** `/healthz`
    - Checks the status of Redis and MySQL connections.
    - Response:
        ```json
        {
            "status": "ok",
            "redis": true,
            "mysql": true,
            "live_servers": []
        }
        ```

## Middleware

- **Process Time Header**: Adds the processing time to the response headers.
- **Session Middleware**: Manages user sessions.
- **Trusted Host Middleware**: Allows requests from all hosts.
- **GZip Middleware**: Compresses responses larger than 1000 bytes.
- **CORS Middleware**: Configures CORS settings based on the environment.

## Environment Variables

- `COMMIT_ID`: The current commit ID.
- `BUILD_AT`: The build timestamp.
- `SESSION_SECRET`: The secret key for session management.
- `DEBUG`: Set to `true` or `false` to enable or disable debug mode.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.
