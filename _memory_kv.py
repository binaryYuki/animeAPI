"""
内存 KV 存储模块 - 用于替代 Redis 的轻量级内存存储
支持键值对存储和过期时间管理
"""
import asyncio
import time
from typing import Optional, Dict, Any, List


class MemoryKV:
    """内存 KV 存储，支持过期时间"""

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task = None

    async def start(self):
        """启动后台清理任务"""
        self._cleanup_task = asyncio.create_task(self._cleanup_expired())

    async def stop(self):
        """停止后台清理任务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_expired(self):
        """定期清理过期键"""
        while True:
            try:
                await asyncio.sleep(60)  # 每60秒清理一次
                async with self._lock:
                    current_time = time.time()
                    expired_keys = [
                        key for key, data in self._store.items()
                        if data.get('expires_at') and data['expires_at'] < current_time
                    ]
                    for key in expired_keys:
                        del self._store[key]
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in cleanup task: {e}")

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """
        设置键值对
        :param key: 键
        :param value: 值
        :param ex: 过期时间（秒），None 表示永不过期
        :return: 是否成功
        """
        try:
            async with self._lock:
                expires_at = None
                if ex is not None:
                    expires_at = time.time() + ex

                self._store[key] = {
                    'value': value,
                    'expires_at': expires_at,
                    'created_at': time.time()
                }
                return True
        except Exception as e:
            print(f"Error setting key {key}: {e}")
            return False

    async def get(self, key: str) -> Optional[str]:
        """
        获取键的值
        :param key: 键
        :return: 值，如果不存在或已过期返回 None
        """
        try:
            async with self._lock:
                if key not in self._store:
                    return None

                data = self._store[key]

                # 检查是否过期
                if data.get('expires_at') and data['expires_at'] < time.time():
                    del self._store[key]
                    return None

                return data['value']
        except Exception as e:
            print(f"Error getting key {key}: {e}")
            return None

    async def delete(self, key: str) -> bool:
        """
        删除键
        :param key: 键
        :return: 是否成功
        """
        try:
            async with self._lock:
                if key in self._store:
                    del self._store[key]
                    return True
                return True  # 键不存在也返回成功
        except Exception as e:
            print(f"Error deleting key {key}: {e}")
            return False

    async def exists(self, key: str) -> int:
        """
        检查键是否存在
        :param key: 键
        :return: 1 表示存在，0 表示不存在或已过期
        """
        try:
            async with self._lock:
                if key not in self._store:
                    return 0

                data = self._store[key]
                if data.get('expires_at') and data['expires_at'] < time.time():
                    del self._store[key]
                    return 0

                return 1
        except Exception as e:
            print(f"Error checking key {key}: {e}")
            return 0

    async def scan_iter(self, match: str = "*") -> List[str]:
        """
        扫描匹配模式的键（简单通配符支持）
        :param match: 匹配模式，支持 * 通配符
        :return: 匹配的键列表
        """
        try:
            async with self._lock:
                current_time = time.time()
                pattern = match.replace("*", ".*")
                import re

                result = []
                for key, data in self._store.items():
                    # 跳过过期的键
                    if data.get('expires_at') and data['expires_at'] < current_time:
                        continue

                    # 检查是否匹配
                    if re.match(f"^{pattern}$", key):
                        result.append(key)

                return result
        except Exception as e:
            print(f"Error scanning keys with pattern {match}: {e}")
            return []

    async def ping(self) -> bool:
        """
        健康检查
        :return: 总是返回 True
        """
        return True

    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        try:
            current_time = time.time()
            total_keys = len(self._store)
            expired_keys = sum(
                1 for data in self._store.values()
                if data.get('expires_at') and data['expires_at'] < current_time
            )

            return {
                'total_keys': total_keys,
                'expired_keys': expired_keys,
                'active_keys': total_keys - expired_keys
            }
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {}


# 全局实例
_memory_kv = MemoryKV()


async def get_memory_kv() -> MemoryKV:
    """获取内存 KV 存储实例"""
    return _memory_kv

