import json
import os
from typing import Optional

import dotenv
from redis import asyncio as redis

dotenv.load_dotenv()

# Configuration
if os.getenv("REDIS_CONN") is not None:
    REDIS_CONN = os.getenv("REDIS_CONN")
else:
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
    # 在集群环境下，使用 redis:// 连接字符串 并且 tcp()包裹
    REDIS_CONN = f"redis://default:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Initialize Redis client
redis_client = redis.from_url(REDIS_CONN)
# set max size of redis connection pool
redis_client.connection_pool.max_connections = 3


async def test_redis():
    try:
        await redis_client.ping()
        await redis_client.delete("InstanceRegister")
        return True
    except redis.RedisError as e:
        print(f"Error connecting to Redis: {e}")
        return False


async def get_keys_by_pattern(pattern: str) -> list:
    """
    Get a list of keys matching a pattern.
    """
    maxAttempts = 3
    try:
        keys = []
        async for key in redis_client.scan_iter(match=pattern):
            keys.append(key.decode())
        return keys
    except redis.ConnectionError as e:
        if maxAttempts > 0:
            data = await get_keys_by_pattern(pattern)
            maxAttempts -= 1
            return data
        else:
            print(f"Error connecting to Redis: {e}")
            return []
    except Exception as e:
        if maxAttempts > 0:
            data = await get_keys_by_pattern(pattern)
            maxAttempts -= 1
            return data
        else:
            print(f"Error getting keys by pattern from Redis: {e}")
            return []


# Set a key-value pair in Redis
async def set_key(key: str, value: str, ex: Optional[int] = None) -> bool:
    """
    Set a value in Redis with an optional expiration time (in seconds).
    """
    try:
        if type(value) is dict:
            value = json.dumps(value)
        await redis_client.set(name=key, value=value, ex=ex)
        return True
    except redis.RedisError as e:
        print(f"Error setting key in Redis: {e}")
        return False


# Get a value from Redis by key
async def get_key(key: str) -> Optional[str]:
    """
    Get a value from Redis by key. Returns None if the key does not exist.
    """
    # 返回 string
    try:
        data = await redis_client.get(key)
        if data:
            return data.decode()
        else:
            return None
    except redis.RedisError as e:
        print(f"Error getting key from Redis: {e}")
        return None


# Delete a key from Redis
async def delete_key(key: str) -> bool:
    """
    Delete a key from Redis.
    """
    try:
        await redis_client.delete(key)
        return True
    except redis.RedisError as e:
        print(f"Error deleting key from Redis: {e}")
        return False


# Check if a key exists in Redis
async def key_exists(key: str) -> bool:
    """
    Check if a key exists in Redis.
    """
    try:
        return await redis_client.exists(key) == 1
    except redis.RedisError as e:
        print(f"Error checking key in Redis: {e}")
        return False
