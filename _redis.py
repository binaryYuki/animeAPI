import json
import os
from typing import Optional

import dotenv
from redis import asyncio as redis

from _memory_kv import get_memory_kv

dotenv.load_dotenv()

# 配置：是否使用 Redis，默认优先尝试 Redis，失败则降级到内存存储
USE_REDIS = os.getenv("USE_REDIS", "true").lower() == "true"
FALLBACK_TO_MEMORY = os.getenv("FALLBACK_TO_MEMORY", "true").lower() == "true"

# Configuration
redis_client = None
use_memory_kv = False

if USE_REDIS:
    try:
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

        # 测试连接
        import asyncio
        try:
            asyncio.run(redis_client.ping())
            print("✓ Redis connection successful")
        except Exception as e:
            print(f"✗ Redis connection failed: {e}")
            if FALLBACK_TO_MEMORY:
                print("! Falling back to memory KV storage")
                redis_client = None
                use_memory_kv = True
            else:
                raise
    except Exception as e:
        print(f"✗ Redis initialization failed: {e}")
        if FALLBACK_TO_MEMORY:
            print("! Using memory KV storage instead")
            use_memory_kv = True
        else:
            raise
else:
    print("! Redis is disabled, using memory KV storage")
    use_memory_kv = True


async def test_redis():
    """测试 Redis 或内存 KV 连接"""
    try:
        if use_memory_kv:
            memory_kv = await get_memory_kv()
            return await memory_kv.ping()
        else:
            await redis_client.ping()
            await redis_client.delete("InstanceRegister")
            return True
    except Exception as e:
        print(f"Error connecting to storage backend: {e}")
        return False


async def get_keys_by_pattern(pattern: str) -> list:
    """
    Get a list of keys matching a pattern.
    支持 Redis 和内存 KV 存储
    """
    maxAttempts = 3
    try:
        if use_memory_kv:
            memory_kv = await get_memory_kv()
            keys = await memory_kv.scan_iter(match=pattern)
            return keys
        else:
            keys = []
            async for key in redis_client.scan_iter(match=pattern):
                keys.append(key.decode())
            return keys
    except Exception as e:
        if maxAttempts > 0:
            data = await get_keys_by_pattern(pattern)
            maxAttempts -= 1
            return data
        else:
            print(f"Error getting keys by pattern: {e}")
            return []


# Set a key-value pair
async def set_key(key: str, value: str, ex: Optional[int] = None) -> bool:
    """
    Set a value with an optional expiration time (in seconds).
    支持 Redis 和内存 KV 存储
    """
    try:
        if type(value) is dict:
            value = json.dumps(value)

        if use_memory_kv:
            memory_kv = await get_memory_kv()
            return await memory_kv.set(key, value, ex=ex)
        else:
            await redis_client.set(name=key, value=value, ex=ex)
            return True
    except Exception as e:
        print(f"Error setting key: {e}")
        return False


# Get a value by key
async def get_key(key: str) -> Optional[str]:
    """
    Get a value by key. Returns None if the key does not exist.
    支持 Redis 和内存 KV 存储
    """
    try:
        if use_memory_kv:
            memory_kv = await get_memory_kv()
            return await memory_kv.get(key)
        else:
            data = await redis_client.get(key)
            if data:
                return data.decode()
            else:
                return None
    except Exception as e:
        print(f"Error getting key: {e}")
        return None


# Delete a key
async def delete_key(key: str) -> bool:
    """
    Delete a key.
    支持 Redis 和内存 KV 存储
    """
    try:
        if use_memory_kv:
            memory_kv = await get_memory_kv()
            return await memory_kv.delete(key)
        else:
            await redis_client.delete(key)
            return True
    except Exception as e:
        print(f"Error deleting key: {e}")
        return False


# Check if a key exists
async def key_exists(key: str) -> bool:
    """
    Check if a key exists.
    支持 Redis 和内存 KV 存储
    """
    try:
        if use_memory_kv:
            memory_kv = await get_memory_kv()
            return await memory_kv.exists(key) == 1
        else:
            return await redis_client.exists(key) == 1
    except Exception as e:
        print(f"Error checking key: {e}")
        return False
