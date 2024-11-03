import binascii
import logging
import os
import random
import subprocess
import time
import uuid
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
from asgi_correlation_id import CorrelationIdMiddleware
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi_limiter import FastAPILimiter
from fastapi_utils.tasks import repeat_every
from starlette.middleware.sessions import SessionMiddleware

from _auth import authRoute
from _cronjobs import keepMySQLAlive, keerRedisAlive, pushTaskExecQueue
from _crypto import cryptoRouter, init_crypto
from _db import init_db, test_db_connection
from _redis import get_keys_by_pattern, redis_client, set_key as redis_set_key
from _search import searchRouter
from _trend import trendingRoute
from _user import userRoute

load_dotenv()
loglevel = os.getenv("LOG_LEVEL", "ERROR")
logging.basicConfig(level=logging.getLevelName(loglevel))
logger = logging.getLogger(__name__)

instanceID = uuid.uuid4().hex


@repeat_every(seconds=60 * 3, wait_first=True)
async def registerInstance():
    """
    注册实例
    :return:
    """
    try:
        await redis_set_key(f"node:{instanceID}", str(int(time.time())), 60 * 3)  # re-register every 3 minutes
    except Exception as e:
        logger.error(f"Failed to register instance: {e}", exc_info=True)
        exit(-1)
    return True


def is_valid_uuid4(uuid_string: str) -> bool:
    """
    检查是否是有效的 UUID4
    """
    try:
        uuid.UUID(uuid_string, version=4)
    except ValueError:
        return False
    return True


async def getLiveInstances():
    """
    获取活跃实例
    :return:
    """
    try:
        f = await get_keys_by_pattern("node:*")
        return f
    except Exception as e:
        logger.error(f"Failed to get live instances: {e}", exc_info=True)
        return []


@repeat_every(seconds=60 * 60, wait_first=True)
async def testPushServer():
    """
    测试推送服务器
    """
    baseURL = os.getenv("PUSH_SERVER_URL", "").replace("https://", "").replace("http://", "")
    if not baseURL:
        return
    async with httpx.AsyncClient() as client:
        f = await client.get(f"https://{baseURL}/healthz")
        if f.status_code == 200:
            await redis_set_key("server_status", "running")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    整个 FastAPI 生命周期的上下文管理器
    :param _: FastAPI 实例
    :return: None
    :param _:
    :return:
    """
    redis_connection = redis.from_url(
        f"redis://default:{os.getenv('REDIS_PASSWORD', '')}@{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}")
    await FastAPILimiter.init(redis_connection)
    test = await redis_connection.ping()
    if test:
        logger.info("Redis connection established")
    # await redis_connection.flush db()
    if os.getenv("MYSQL_CONN_STRING"):
        await init_db()
        logger.info("MySQL connection established")
    await testPushServer()
    await registerInstance()
    print("Instance registered", instanceID)
    await pushTaskExecQueue()
    await keerRedisAlive()
    await keepMySQLAlive()
    await init_crypto()
    yield
    await FastAPILimiter.close()
    await redis_client.connection_pool.disconnect()
    print("Instance unregistered", instanceID)
    print("graceful shutdown")


# 禁用 openapi.json
app = FastAPI(lifespan=lifespan, title="Anime API", version="1.1.4", openapi_url=None)

app.include_router(authRoute)
app.include_router(userRoute)
app.include_router(searchRouter)
app.include_router(trendingRoute)
app.include_router(cryptoRouter)


@app.middleware("http")
async def instance_id_header_middleware(request, call_next):
    """
    添加 Instance ID 到响应头
    :param request:
    :param call_next:
    :return:
    """
    response = await call_next(request)
    response.headers["X-Instance-ID"] = instanceID
    return response


@app.get('/test')
async def test():
    """
    测试接口
    :return:
    """
    f = await get_keys_by_pattern("node:*")
    return f


@app.get('/')
async def index():
    """
    首页
    :return:
    """
    version_suffix = os.getenv("COMMIT_ID", "")[:8]
    info = {
        "version": "v1.1.4-" + version_suffix,
        "build_at": os.environ.get("BUILD_AT", ""),
        "author": "binaryYuki <noreply.tzpro.xyz>",
        "arch": subprocess.run(['uname', '-m'], stdout=subprocess.PIPE).stdout.decode().strip(),
        "commit": os.getenv("COMMIT_ID", ""),
        "instance_id": instanceID,
    }

    # 转为 pre defined html
    html = """
    <pre>
    <code>
    Version: {version}
    Build At: {build_at}
    Author: {author}
    Arch: {arch}
    Commit: {commit}
    Instance ID: {instance_id}
    </code>
    </pre>
    """.format(**info)
    return HTMLResponse(content=html)


@app.api_route('/healthz', methods=['GET'])
async def healthz():
    """
    健康检查
    :return:
    """
    try:
        await redis_client.ping()
        redisStatus = True
    except Exception as e:
        redisStatus = False
        logging.error("Redis error: %s", str(e))
    # check mysql connection
    try:
        await test_db_connection()
        mysqlStatus = True
    except ConnectionError as e:
        mysqlStatus = False
        logging.error("MySQL connection error: %s", str(e))
    except Exception as e:
        mysqlStatus = False
        logging.error("MySQL error: %s", str(e))
    try:
        live_servers = await getLiveInstances()
    except Exception as e:
        print(f"Error getting live servers: {e}")
        live_servers = []
    if redisStatus and mysqlStatus and live_servers:
        return JSONResponse(content={"status": "ok", "redis": redisStatus, "mysql": mysqlStatus,
                                     "live_servers": live_servers})
    else:
        return JSONResponse(content={"status": "error", "redis": redisStatus, "mysql": mysqlStatus,
                                     "redis_hint": "An error occurred" if not redisStatus else "",
                                     "mysql_hint": "An error occurred" if not mysqlStatus else "",
                                     "live_servers": live_servers})


@app.middleware("http")
async def add_process_time_header(request, call_next):
    """
    添加处理时间到响应头
    :param request:
    :param call_next:
    :return:
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    # round it to 3 decimal places and add the unit which is seconds
    process_time = round(process_time, 3)
    response.headers["X-Process-Time"] = str(process_time) + "s"
    return response


secret_key = os.environ.get("SESSION_SECRET")
if not secret_key:
    secret_key = binascii.hexlify(random.randbytes(16)).decode('utf-8')

# noinspection PyTypeChecker
app.add_middleware(SessionMiddleware, secret_key=secret_key,
                   session_cookie='session', max_age=60 * 60 * 12, same_site='lax', https_only=True)
# noinspection PyTypeChecker
app.add_middleware(GZipMiddleware, minimum_size=1000)
if os.getenv("DEBUG", "false").lower() == "false":
    # noinspection PyTypeChecker
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r'^https?:\/\/(localhost:3000|.*\.tzpro\.xyz|.*\.tzpro\.uk)(\/.*)?$',
        allow_credentials=True,
        allow_methods=['GET', 'POST', 'OPTIONS'],  # options 请求是预检请求，需要单独处理
        allow_headers=['Authorization', 'Content-Type', 'Accept', 'Accept-Encoding', 'Accept-Language', 'Origin',
                       'Referer', 'Cookie', 'User-Agent'],
    )
    app.add_middleware(
        CorrelationIdMiddleware,
        header_name='X-Request-ID',
        update_request_header=True,
        generator=lambda: uuid.uuid4().hex,
        validator=is_valid_uuid4,
        transformer=lambda a: a,
    )
else:
    # noinspection PyTypeChecker
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['GET', 'POST', 'OPTIONS', 'PUT'],  # options 请求是预检请求，需要单独处理
        allow_headers=['Authorization', 'Content-Type', 'Accept', 'Accept-Encoding', 'Accept-Language', 'Origin',
                       'Referer', 'Cookie', 'User-Agent'],
    )

if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
